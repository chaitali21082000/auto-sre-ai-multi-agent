"""
Orchestrator - Coordinates multi-agent incident response workflow
"""
from app.agents.log_agent import analyze_log
from app.agents.rag_agent import search_rag, enrich_with_context
from app.agents.decision_agent import decide_action, execute_decision
import logging

logger = logging.getLogger(__name__)

def handle_incident(log: str) -> dict:
    """
    Main incident handling orchestration.
    
    Workflow:
    1. Analyze log with AI to extract structured information
    2. Search knowledge base (RAG) for similar incidents
    3. Enrich analysis with RAG context
    4. Make decision on response action
    5. Execute decision (store, alert, auto-fix)
    
    Args:
        log: Raw error log string
    
    Returns:
        dict with analysis, decision, and execution results
    """
    
    logger.info("Starting incident analysis")
    
    # Phase 1: Analyze Log
    logger.info("Phase 1: Analyzing log with AI")
    try:
        parsed = analyze_log(log)
        logger.info(f"Log analysis complete. Error type: {parsed.get('type')}, Severity: {parsed.get('severity')}")
    except Exception as e:
        logger.error(f"Error analyzing log: {e}")
        return {
            "success": False,
            "error": f"Log analysis failed: {str(e)}",
            "phase": "log_analysis"
        }
    
    # Store original log for reference
    parsed["original_log"] = log
    
    # Phase 2: Search Knowledge Base (RAG)
    logger.info("Phase 2: Searching knowledge base")
    try:
        rag_result = search_rag(parsed["type"], log)
        logger.info(f"RAG search complete. Found: {rag_result.get('found')}, Confidence: {rag_result.get('confidence'):.2f}")
    except Exception as e:
        logger.error(f"Error in RAG search: {e}")
        rag_result = {
            "found": False,
            "solutions": [],
            "confidence": 0,
            "error": str(e)
        }
    
    # Phase 3: Enrich Analysis (optional - combine AI analysis with RAG)
    logger.info("Phase 3: Enriching analysis")
    try:
        enriched = enrich_with_context(parsed, rag_result)
        if enriched:
            parsed.update(enriched)
    except Exception as e:
        logger.warning(f"Could not enrich analysis: {e}")
    
    # Phase 4: Make Decision
    logger.info("Phase 4: Making incident response decision")
    try:
        decision = decide_action(parsed, rag_result)
        logger.info(f"Decision: {decision.get('action')}, Confidence: {decision.get('confidence', 'N/A')}")
    except Exception as e:
        logger.error(f"Error in decision making: {e}")
        decision = {"action": "ESCALATE", "error": str(e)}
    
    # Phase 5: Execute Decision
    logger.info("Phase 5: Executing decision")
    try:
        execution_result = execute_decision(decision, parsed, rag_result)
        logger.info(f"Decision execution complete. Success: {execution_result.get('success')}")
    except Exception as e:
        logger.error(f"Error executing decision: {e}")
        execution_result = {
            "success": False,
            "error": str(e)
        }
    
    # Compile final response
    response = {
        "success": True,
        "analysis": {
            "error_type": parsed.get("type"),
            "severity": parsed.get("severity"),
            "root_cause": parsed.get("root_cause"),
            "services_affected": parsed.get("services_affected", [])
        },
        "rag": {
            "found": rag_result.get("found"),
            "confidence": rag_result.get("confidence"),
            "solutions_count": len(rag_result.get("solutions", []))
        },
        "decision": {
            "action": decision.get("action"),
            "reasoning": decision.get("reasoning"),
            "confidence": decision.get("confidence")
        },
        "execution": execution_result
    }
    
    logger.info("Incident handling complete")
    return response