from app.utils.llm import structured_call_llm, call_llm
import json

def analyze_log(log):
    """
    Analyze error log and extract structured information.
    Uses LLM with function calling for accurate classification.
    """
    
    schema = {
        "type": {"type": "string", "description": "Error type (DB_ERROR, TIMEOUT, MEMORY, CPU, AUTH, etc.)"},
        "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]},
        "root_cause": {"type": "string", "description": "Root cause analysis"},
        "services_affected": {"type": "array", "items": {"type": "string"}},
        "error_message": {"type": "string"}
    }
    
    system_instruction = """You are an expert SRE (Site Reliability Engineer) specializing in log analysis.
Your task is to analyze error logs and provide accurate classifications and root cause analysis.
Be precise and concise in your analysis.
Always return valid JSON matching the required schema."""
    
    prompt = f"""Analyze this error log and extract key information:

<log>
{log}
</log>

Classify the error type, determine severity level, identify root cause, and list affected services.
Return the analysis as JSON."""
    
    try:
        result = structured_call_llm(prompt, schema=schema, system_instruction=system_instruction)
        # Validate required fields
        if not result.get("type"):
            result["type"] = "UNKNOWN"
        if not result.get("severity"):
            result["severity"] = "MEDIUM"
        if not result.get("root_cause"):
            result["root_cause"] = "Unable to determine from log"
        return result
    except Exception as e:
        print(f"Error in log analysis: {e}")
        return {
            "type": "UNKNOWN",
            "severity": "MEDIUM",
            "root_cause": f"Error during analysis: {str(e)}",
            "services_affected": [],
            "error_message": log[:200]
        }