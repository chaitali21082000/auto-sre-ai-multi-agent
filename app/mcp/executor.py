"""Tool Executor - Executes MCP tool calls from LLM responses"""
import json
from app.gcp.firestore_client import store_incident
from app.gcp.pubsub_client import publish_alert
from app.gcp.function_client import trigger_fix
from app.rag.rag_engine import get_rag_engine
from app.github.client import GitHubClient

class ToolExecutor:
    def __init__(self):
        self.rag_engine = get_rag_engine()
        self.github_client = GitHubClient()
    
    def execute_tool(self, tool_name: str, parameters: dict) -> dict:
        """Execute a tool and return the result"""
        try:
            if tool_name == "store_incident":
                return self._store_incident(parameters)
            elif tool_name == "publish_alert":
                return self._publish_alert(parameters)
            elif tool_name == "trigger_auto_fix":
                return self._trigger_auto_fix(parameters)
            elif tool_name == "search_knowledge_base":
                return self._search_kb(parameters)
            elif tool_name == "create_github_issue":
                return self._create_github_issue(parameters)
            elif tool_name == "create_github_pr":
                return self._create_github_pr(parameters)
            elif tool_name == "get_repository_info":
                return self._get_repository_info(parameters)
            elif tool_name == "generate_fix_from_context":
                return self._generate_fix_from_context(parameters)
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _store_incident(self, params: dict) -> dict:
        """Store incident in Firestore"""
        store_incident(
            log=params.get("log"),
            parsed={
                "type": params.get("error_type"),
                "severity": params.get("severity"),
                "root_cause": params.get("root_cause")
            },
            decision={
                "recommendation": params.get("recommended_action")
            }
        )
        return {"success": True, "message": "Incident stored"}
    
    def _publish_alert(self, params: dict) -> dict:
        """Publish alert via Pub/Sub"""
        publish_alert(
            parsed={
                "type": params.get("error_type"),
                "severity": params.get("severity")
            },
            decision={
                "action": params.get("action", "ALERT"),
                "message": params.get("message", "")
            }
        )
        return {"success": True, "message": "Alert published"}
    
    def _trigger_auto_fix(self, params: dict) -> dict:
        """Trigger auto-fix through Cloud Functions"""
        trigger_fix({
            "error_type": params.get("error_type"),
            "fix_type": params.get("fix_type"),
            "parameters": params.get("parameters", {})
        })
        return {"success": True, "message": "Auto-fix triggered"}
    
    def _search_kb(self, params: dict) -> dict:
        """Search knowledge base"""
        results = self.rag_engine.search(
            query=params.get("query"),
            top_k=params.get("top_k", 3)
        )
        return {
            "success": True,
            "results": results,
            "count": len(results)
        }
    
    def _create_github_issue(self, params: dict) -> dict:
        """Create GitHub issue in service repository"""
        return self.github_client.create_issue(
            service_name=params.get("service_name"),
            title=params.get("title"),
            body=params.get("body"),
            labels=params.get("labels", ["bug", "auto-detected"]),
            assignee=params.get("assignee")
        )
    
    def _create_github_pr(self, params: dict) -> dict:
        """Create GitHub pull request"""
        return self.github_client.create_pull_request(
            service_name=params.get("service_name"),
            pr_title=params.get("pr_title"),
            pr_body=params.get("pr_body"),
            branch_name=params.get("branch_name"),
            fix_type=params.get("fix_type")
        )
    
    def _get_repository_info(self, params: dict) -> dict:
        """Get detailed repository information with commits and structure"""
        return self.github_client.get_repository_info(
            service_name=params.get("service_name"),
            include_recent_commits=params.get("include_recent_commits", True),
            include_file_structure=params.get("include_file_structure", True)
        )
    
    def _generate_fix_from_context(self, params: dict) -> dict:
        """Generate PR with fix based on GitHub repo context"""
        return self.github_client.generate_fix_from_context(
            service_name=params.get("service_name"),
            error_type=params.get("error_type"),
            root_cause=params.get("root_cause"),
            suggested_fix=params.get("suggested_fix"),
            affected_files=params.get("affected_files", []),
            confidence=params.get("confidence", 0.7)
        )

# Singleton instance
_executor = None

def get_tool_executor():
    """Get or create tool executor instance"""
    global _executor
    if _executor is None:
        _executor = ToolExecutor()
    return _executor
