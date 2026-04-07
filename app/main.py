from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.orchestrator import handle_incident
from app.rag.knowledge_manager import KnowledgeManager, rebuild_faiss_index
from app.jobs.sync_kb_from_github import initialize_sync_job
import logging
import os
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AutoSRE AI",
    description="AI-powered multi-agent incident detection and response system",
    version="2.0"
)

# Initialize feedback loop on startup
@app.on_event("startup")
async def startup_event():
    """Initialize feedback loop components on app startup"""
    try:
        logger.info("Initializing feedback loop system...")
        
        # Get repos from environment or use defaults
        repos_env = os.getenv('SYNC_REPOS', '').split(',')
        repos = [r.strip() for r in repos_env if r.strip()]
        
        if not repos:
            repos = []
            logger.info("No repos configured for KB sync - using manual mode only")
        else:
            # Initialize and start KB sync job
            sync_interval = int(os.getenv('KB_SYNC_INTERVAL_HOURS', '6'))
            initialize_sync_job(repos=repos, interval_hours=sync_interval)
            logger.info(f"✅ KB sync job initialized for {len(repos)} repos")
        
        # Log KB stats
        stats = KnowledgeManager.get_kb_statistics()
        logger.info(f"📚 Knowledge Base: {stats.get('total_solutions', 0)} solutions "
                   f"({stats.get('auto_learned_solutions', 0)} auto-learned)")
        
    except Exception as e:
        logger.error(f"Error initializing feedback loop: {e}", exc_info=True)

class LogRequest(BaseModel):
    log: str

class HealthResponse(BaseModel):
    status: str
    version: str

@app.get("/", response_model=HealthResponse)
def home():
    """Health check endpoint"""
    return {"status": "healthy", "version": "2.0"}

@app.post("/analyze")
def analyze(req: LogRequest) -> dict:
    """
    Analyze error log and trigger incident response.
    
    Uses multi-agent orchestration with:
    - AI log analysis
    - Vector-based RAG search
    - Intelligent decision making
    - Tool-based automation
    
    Args:
        req: LogRequest containing raw error log
    
    Returns:
        Analysis, decision, and execution results
    """
    logger.info(f"Received log analysis request (length: {len(req.log)})")
    try:
        result = handle_incident(req.log)
        logger.info("Log analysis completed successfully")
        return result
    except Exception as e:
        logger.error(f"Error processing incident: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "phase": "orchestration"
        }

@app.get("/health")
def health_check():
    """Detailed health check"""
    return {
        "status": "ok",
        "components": {
            "llm": "configured",
            "rag": "initialized",
            "mcp": "enabled"
        }
    }


# ==================== Knowledge Base Feedback Loop Endpoints ====================

@app.post("/api/webhooks/github")
async def github_webhook(request: Request):
    """
    GitHub webhook for learning from merged PRs
    Receives PR merge events with 'auto-detected-fix' label and adds to KB
    """
    try:
        from app.api.webhook_handler import (
            verify_github_signature, handle_pr_event, handle_issue_event
        )
        
        # Verify signature
        secret = os.getenv('GITHUB_WEBHOOK_SECRET', '')
        if secret:
            signature = request.headers.get('X-Hub-Signature-256', '')
            body = await request.body()
            
            if not verify_github_signature(body, signature, secret):
                logger.warning("Invalid webhook signature")
                return JSONResponse({'status': 'invalid-signature'}, status_code=401)
        
        # Parse payload
        payload = await request.json()
        event_type = request.headers.get('X-GitHub-Event')
        
        logger.info(f"GitHub webhook: {event_type}")
        
        if event_type == 'pull_request':
            result, status = handle_pr_event(payload)
            return JSONResponse(result, status_code=status)
        elif event_type == 'issues':
            result, status = handle_issue_event(payload)
            return JSONResponse(result, status_code=status)
        else:
            return JSONResponse({'status': 'ignored'}, status_code=200)
    
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)


# ==================== Knowledge Base Management API ====================

@app.get("/api/kb/solutions")
def get_all_solutions():
    """Get all solutions in KB"""
    try:
        solutions = KnowledgeManager.list_all_solutions()
        return {
            'status': 'success',
            'total': len(solutions),
            'solutions': solutions
        }
    except Exception as e:
        logger.error(f"Error getting solutions: {e}")
        return {'status': 'error', 'message': str(e)}


@app.get("/api/kb/solutions/{error_type}")
def get_solution(error_type: str):
    """Get specific solution by error type"""
    try:
        solution = KnowledgeManager.get_solution(error_type)
        if not solution:
            return JSONResponse({
                'status': 'not_found',
                'error_type': error_type
            }, status_code=404)
        
        return {'status': 'success', 'solution': solution}
    except Exception as e:
        logger.error(f"Error getting solution: {e}")
        return {'status': 'error', 'message': str(e)}


@app.get("/api/kb/solutions/auto-learned")
def get_auto_learned_solutions():
    """Get only auto-learned solutions (from feedback loop)"""
    try:
        solutions = KnowledgeManager.list_learned_solutions()
        avg_conf = round(sum(s.get('confidence', 0.80) for s in solutions) / len(solutions), 3) if solutions else 0
        
        return {
            'status': 'success',
            'count': len(solutions),
            'avg_confidence': avg_conf,
            'solutions': solutions
        }
    except Exception as e:
        logger.error(f"Error getting auto-learned solutions: {e}")
        return {'status': 'error', 'message': str(e)}


@app.post("/api/kb/solutions")
def add_solution(solution_data: dict):
    """Add a new solution to KB (manual)"""
    try:
        # Validate solution
        valid, issues = KnowledgeManager.validate_solution_quality(solution_data)
        if not valid:
            return JSONResponse({
                'status': 'validation_failed',
                'issues': issues
            }, status_code=400)
        
        # Set defaults for manual additions
        if 'source' not in solution_data:
            solution_data['source'] = 'manual'
        if 'confidence' not in solution_data:
            solution_data['confidence'] = 0.90
        if 'is_auto_learned' not in solution_data:
            solution_data['is_auto_learned'] = False
        
        # Add solution
        success = KnowledgeManager.add_solution(solution_data)
        
        if success:
            # Rebuild FAISS for immediate search capability
            rebuild_faiss_index()
            
            return JSONResponse({
                'status': 'success',
                'error_type': solution_data.get('error_type'),
                'confidence': solution_data.get('confidence')
            }, status_code=201)
        else:
            return JSONResponse({
                'status': 'failed',
                'message': 'Failed to add solution'
            }, status_code=500)
    
    except Exception as e:
        logger.error(f"Error adding solution: {e}")
        return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)


@app.post("/api/kb/solutions/{error_type}/confidence")
def update_confidence(error_type: str, event: str, value: float = None):
    """Update confidence for a solution"""
    try:
        success = KnowledgeManager.update_confidence(error_type, event, value)
        
        if success:
            solution = KnowledgeManager.get_solution(error_type)
            return {
                'status': 'success',
                'error_type': error_type,
                'new_confidence': solution.get('confidence'),
                'event': event
            }
        else:
            return JSONResponse({
                'status': 'failed',
                'message': f'Solution not found: {error_type}'
            }, status_code=404)
    
    except Exception as e:
        logger.error(f"Error updating confidence: {e}")
        return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)


@app.get("/api/kb/stats")
def get_kb_statistics():
    """Get knowledge base statistics"""
    try:
        stats = KnowledgeManager.get_kb_statistics()
        return {'status': 'success', 'statistics': stats}
    except Exception as e:
        logger.error(f"Error getting KB stats: {e}")
        return {'status': 'error', 'message': str(e)}


@app.get("/api/kb/health")
def kb_health():
    """Check KB health and integrity"""
    try:
        stats = KnowledgeManager.get_kb_statistics()
        solutions = KnowledgeManager.list_all_solutions()
        
        # Check for issues
        issues = []
        
        for sol in solutions:
            conf = sol.get('confidence', 0.80)
            val_count = sol.get('validation_count', 1)
            
            if val_count > 5 and conf < 0.60:
                issues.append(f"{sol['error_type']}: Low confidence ({conf}) after {val_count} validations")
        
        health_status = 'healthy' if not issues else 'warning'
        
        return {
            'status': 'success',
            'health': health_status,
            'statistics': stats,
            'issues': issues
        }
    except Exception as e:
        logger.error(f"Error checking KB health: {e}")
        return {'status': 'error', 'message': str(e)}