from app.rag.rag_engine import get_rag_engine
from app.utils.llm import structured_call_llm

def search_rag(error_type: str, log_context: str = None):
    """
    Search knowledge base using vector similarity for relevant solutions.
    
    Args:
        error_type: Type of error to search for
        log_context: Original log for better context
    
    Returns:
        dict with relevant solutions and confidence scores
    """
    rag_engine = get_rag_engine()
    
    # Build search query
    query = error_type
    if log_context:
        query = f"{error_type}: {log_context[:500]}"
    
    # Vector search
    results = rag_engine.search(query, top_k=3)
    
    if not results:
        return {
            "found": False,
            "solutions": [],
            "confidence": 0.0,
            "message": "No similar issues found in knowledge base"
        }
    
    # Filter results by confidence threshold
    high_confidence_results = [r for r in results if r.get("similarity", 0) > 0.6]
    
    return {
        "found": len(high_confidence_results) > 0,
        "solutions": high_confidence_results,
        "total_results": len(results),
        "confidence": max([r.get("similarity", 0) for r in results]) if results else 0,
        "message": f"Found {len(results)} similar issues, {len(high_confidence_results)} high-confidence matches"
    }

def enrich_with_context(error_analysis: dict, rag_results: dict):
    """
    Use LLM to synthesize error analysis with RAG results for better decision making.
    """
    if not rag_results.get("found"):
        return error_analysis
    
    schema = {
        "error_type": {"type": "string"},
        "severity": {"type": "string"},
        "root_cause": {"type": "string"},
        "recommended_solutions": {"type": "array", "items": {"type": "string"}},
        "confidence_in_diagnosis": {"type": "number", "minimum": 0, "maximum": 1}
    }
    
    solutions_text = "\n".join([
        f"- Similarity: {s.get('similarity', 0):.2f}: {str(s.get('document', s))[:200]}"
        for s in rag_results.get("solutions", [])
    ])
    
    prompt = f"""Given the error analysis and similar issues from knowledge base, 
provide recommendations.

Error Type: {error_analysis.get('type')}
Severity: {error_analysis.get('severity')}
Root Cause: {error_analysis.get('root_cause')}

Similar Issues Found:
{solutions_text}

Provide a synthesized analysis with recommended solutions."""
    
    return structured_call_llm(prompt, schema=schema)