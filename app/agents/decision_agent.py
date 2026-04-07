from app.utils.llm import structured_call_llm, call_llm_with_functions
from app.mcp.executor import get_tool_executor
import json
import re

def decide_action(parsed: dict, rag_results: dict):
    """
    Make intelligent incident response decision using error analysis and RAG results.
    Enhanced to use GitHub context when RAG confidence is low.
    Returns both decision and triggered tools.
    """
    
    schema = {
        "action": {"type": "string", "enum": ["AUTO_FIX", "ALERT", "ESCALATE", "AUTO_FIX_FROM_CONTEXT"]},
        "reasoning": {"type": "string"},
        "severity_adjusted": {"type": "string", "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "recommended_tools": {"type": "array", "items": {"type": "string"}},
        "use_github_context": {"type": "boolean"},
        "suggested_fix": {"type": "string"}
    }
    
    system_instruction = """You are an expert incident response system.
Your role is to analyze errors and make appropriate response decisions.
Consider error severity, availability of solutions, and organizational SLAs.

NEW: If no solution found in knowledge base but severity is not critical,
you can return AUTO_FIX_FROM_CONTEXT to generate a fix using GitHub repo context.

Return structured JSON with decision and confidence level."""
    
    # Prepare context
    rag_info = ""
    rag_confidence = rag_results.get('confidence', 0)
    
    if rag_results.get("found") and rag_results.get("solutions"):
        rag_info = "Similar issues found with solutions"
    else:
        rag_info = "No similar issues found - new or unique error. Can use repo context for fix generation."
    
    severity = parsed.get('severity', 'MEDIUM')
    
    prompt = f"""Analyze this incident and decide on response action:

Error Type: {parsed.get('type', 'UNKNOWN')}
Severity: {severity}
Root Cause: {parsed.get('root_cause', 'Unknown')}
Services Affected: {', '.join(parsed.get('services_affected', []))}

Knowledge Base Results: {rag_info}
Confidence in KB solutions: {rag_confidence:.2f}

Decision Options:
1. AUTO_FIX - Use if RAG confidence > 0.8 and solution exists
2. AUTO_FIX_FROM_CONTEXT - Use if no KB match but severity NOT critical (analyze repo to generate fix)
3. ALERT - Use if medium confidence (0.6-0.8) or unsure
4. ESCALATE - Use only if CRITICAL severity or very low confidence

Recommended Strategy:
- If KB confidence > 0.8 → AUTO_FIX
- If KB confidence 0.6-0.8 → ALERT
- If KB confidence < 0.6 AND severity < CRITICAL → AUTO_FIX_FROM_CONTEXT
- If CRITICAL → ESCALATE

For AUTO_FIX_FROM_CONTEXT, provide a suggested_fix description."""
    
    try:
        decision = structured_call_llm(prompt, schema=schema, system_instruction=system_instruction)
        return decision
    except Exception as e:
        print(f"Error in decision making: {e}")
        return {
            "action": "ALERT",
            "reasoning": f"Decision error: {str(e)}",
            "severity_adjusted": parsed.get("severity", "MEDIUM"),
            "confidence": 0,
            "recommended_tools": [],
            "use_github_context": False
        }

def execute_decision(decision: dict, parsed: dict, rag_results: dict):
    """
    Execute the decision by calling appropriate MCP tools.
    Enhanced to handle AUTO_FIX_FROM_CONTEXT when RAG has no solution.
    """
    executor = get_tool_executor()
    tool_results = []
    
    try:
        # Always store the incident
        store_result = executor.execute_tool("store_incident", {
            "log": parsed.get("original_log", ""),
            "error_type": parsed.get("type", "UNKNOWN"),
            "severity": decision.get("severity_adjusted", parsed.get("severity")),
            "root_cause": parsed.get("root_cause"),
            "recommended_action": decision.get("action")
        })
        tool_results.append({"tool": "store_incident", "result": store_result})
        
        # Publish alert based on decision
        publish_result = executor.execute_tool("publish_alert", {
            "error_type": parsed.get("type"),
            "severity": decision.get("severity_adjusted"),
            "action": decision.get("action"),
            "message": decision.get("reasoning", "")
        })
        tool_results.append({"tool": "publish_alert", "result": publish_result})
        
        # Get affected service for GitHub operations
        affected_service = parsed.get("services_affected", ["unknown"])[0]
        
        # Trigger auto-fix if decided with KB solution
        if decision.get("action") == "AUTO_FIX":
            if rag_results.get("solutions"):
                best_solution = rag_results["solutions"][0]
                fix_result = executor.execute_tool("trigger_auto_fix", {
                    "error_type": parsed.get("type"),
                    "fix_type": best_solution.get("document", {}).get("fix_type", "generic"),
                    "parameters": best_solution.get("document", {}).get("parameters", {})
                })
                tool_results.append({"tool": "trigger_auto_fix", "result": fix_result})
                
                # Create GitHub issue for tracking
                issue_result = executor.execute_tool("create_github_issue", {
                    "service_name": affected_service,
                    "title": f"[AUTO-FIXED] {parsed.get('type')}",
                    "body": f"Error: {parsed.get('root_cause')}\n\nFix applied: {best_solution.get('document', {}).get('fix_type')}",
                    "labels": ["bug", "auto-fixed"]
                })
                tool_results.append({"tool": "create_github_issue", "result": issue_result})
                
                # Create GitHub PR with fix code
                pr_result = executor.execute_tool("create_github_pr", {
                    "service_name": affected_service,
                    "pr_title": f"fix: {parsed.get('type')}",
                    "pr_body": f"Automated fix for: {parsed.get('root_cause')}",
                    "branch_name": "autofix/" + parsed.get("type", "fix").lower()
                })
                tool_results.append({"tool": "create_github_pr", "result": pr_result})
        
        # NEW: Generate fix from GitHub context when RAG has no match
        elif decision.get("action") == "AUTO_FIX_FROM_CONTEXT":
            # Get repository context
            repo_context_result = executor.execute_tool("get_repository_info", {
                "service_name": affected_service,
                "include_recent_commits": True,
                "include_file_structure": True
            })
            tool_results.append({"tool": "get_repository_info", "result": repo_context_result})
            
            # Generate fix based on repo context using LLM
            suggested_fix = decision.get("suggested_fix", "Based on repo analysis, consider the following fix")
            
            # Create PR with context-based fix suggestion
            fix_from_context_result = executor.execute_tool("generate_fix_from_context", {
                "service_name": affected_service,
                "error_type": parsed.get("type"),
                "root_cause": parsed.get("root_cause"),
                "suggested_fix": suggested_fix,
                "affected_files": [],
                "confidence": decision.get("confidence", 0.7)
            })
            tool_results.append({"tool": "generate_fix_from_context", "result": fix_from_context_result})
            
            # Create high-priority GitHub issue
            issue_result = executor.execute_tool("create_github_issue", {
                "service_name": affected_service,
                "title": f"[AUTO-DETECTED] {parsed.get('type')} - Context-Based Fix Generated",
                "body": f"""Error Type: {parsed.get('type')}
Root Cause: {parsed.get('root_cause')}

## Analysis
No exact match found in knowledge base.
Using repository context analysis to suggest fix.

## Suggested Fix
{suggested_fix}

Confidence: {decision.get('confidence', 0.7):.1%}

Related PR: Check pull requests for automated fix suggestion.""",
                "labels": ["bug", "auto-detected", "context-based-fix"]
            })
            tool_results.append({"tool": "create_github_issue", "result": issue_result})
        
        # ESCALATE for critical issues
        elif decision.get("action") == "ESCALATE":
            # Create high-priority GitHub issue
            issue_result = executor.execute_tool("create_github_issue", {
                "service_name": affected_service,
                "title": f"[CRITICAL] {parsed.get('type')} - Manual Intervention Required",
                "body": f"""CRITICAL ERROR DETECTED

Error Type: {parsed.get('type')}
Root Cause: {parsed.get('root_cause')}
Severity: {decision.get('severity_adjusted')}

No automated fix available. Expert investigation required.""",
                "labels": ["critical", "escalated", "auto-detected"]
            })
            tool_results.append({"tool": "create_github_issue", "result": issue_result})
        
        return {
            "decision": decision,
            "tools_executed": tool_results,
            "success": all(r["result"].get("success", False) for r in tool_results if r["result"] is not None)
        }
    except Exception as e:
        print(f"Error executing decision: {e}")
        return {
            "decision": decision,
            "tools_executed": tool_results,
            "success": False,
            "error": str(e)
        }