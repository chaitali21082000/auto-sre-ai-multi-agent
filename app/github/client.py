"""GitHub integration for AutoFix workflow"""
import requests
import json
from app.config.services import get_service_repo

class GitHubClient:
    """Handle GitHub API interactions"""
    
    def __init__(self, github_token: str = None):
        """
        Initialize GitHub client
        
        Args:
            github_token: GitHub Personal Access Token
                         If None, reads from GITHUB_TOKEN env var
        """
        import os
        self.token = github_token or os.getenv("GITHUB_TOKEN")
        self.api_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def create_issue(self, 
                    service_name: str,
                    title: str,
                    body: str,
                    labels: list = None,
                    assignee: str = None) -> dict:
        """
        Create GitHub issue in service repository
        
        Args:
            service_name: Service affected (e.g., "billing-service")
            title: Issue title
            body: Issue description with error details
            labels: List of labels (e.g., ["bug", "critical", "auto-detected"])
            assignee: GitHub username to assign
        
        Returns:
            Issue details or error
        """
        
        repo_info = get_service_repo(service_name)
        if not repo_info:
            return {"success": False, "error": f"Service {service_name} not found"}
        
        issue_data = {
            "title": title,
            "body": body,
            "labels": labels or ["bug", "auto-detected"],
            "assignee": assignee
        }
        
        # Remove None values
        issue_data = {k: v for k, v in issue_data.items() if v is not None}
        
        url = f"{self.api_url}/repos/{repo_info['owner']}/{repo_info['repo']}/issues"
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=issue_data,
                timeout=10
            )
            
            if response.status_code == 201:
                issue = response.json()
                return {
                    "success": True,
                    "issue_url": issue["html_url"],
                    "issue_number": issue["number"],
                    "message": f"Issue #{issue['number']} created"
                }
            else:
                return {
                    "success": False,
                    "error": f"GitHub API error: {response.status_code}",
                    "details": response.text
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_pull_request(self,
                           service_name: str,
                           pr_title: str,
                           pr_body: str,
                           branch_name: str,
                           fix_type: str) -> dict:
        """
        Create pull request with fixes
        
        Args:
            service_name: Service to fix
            pr_title: Pull request title
            pr_body: PR description
            branch_name: Feature branch name
            fix_type: Type of fix (e.g., "resource_restart", "connection_reset")
        
        Returns:
            PR details or error
        """
        
        repo_info = get_service_repo(service_name)
        if not repo_info:
            return {"success": False, "error": f"Service {service_name} not found"}
        
        pr_data = {
            "title": pr_title,
            "body": pr_body,
            "head": branch_name,
            "base": repo_info["branch"]
        }
        
        url = f"{self.api_url}/repos/{repo_info['owner']}/{repo_info['repo']}/pulls"
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=pr_data,
                timeout=10
            )
            
            if response.status_code == 201:
                pr = response.json()
                return {
                    "success": True,
                    "pr_url": pr["html_url"],
                    "pr_number": pr["number"],
                    "message": f"Pull request #{pr['number']} created"
                }
            else:
                return {
                    "success": False,
                    "error": f"GitHub API error: {response.status_code}",
                    "details": response.text
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_latest_commit(self, service_name: str) -> dict:
        """Get latest commit of main branch"""
        
        repo_info = get_service_repo(service_name)
        if not repo_info:
            return {"success": False, "error": f"Service {service_name} not found"}
        
        url = f"{self.api_url}/repos/{repo_info['owner']}/{repo_info['repo']}/commits/{repo_info['branch']}"
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                commit = response.json()
                return {
                    "success": True,
                    "sha": commit["sha"],
                    "message": commit["commit"]["message"],
                    "author": commit["commit"]["author"]["name"]
                }
            else:
                return {"success": False, "error": f"API error: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_repository_info(self, service_name: str, include_recent_commits: bool = True, include_file_structure: bool = True) -> dict:
        """
        Get detailed repository information including commits and file structure
        
        Args:
            service_name: Service name
            include_recent_commits: Include last 10 commits
            include_file_structure: Include directory structure
        
        Returns:
            Detailed repo information for context-aware fixes
        """
        
        repo_info = get_service_repo(service_name)
        if not repo_info:
            return {"success": False, "error": f"Service {service_name} not found"}
        
        result = {
            "success": True,
            "service": service_name,
            "repository": repo_info,
            "url": repo_info.get("url")
        }
        
        # Get recent commits for context
        if include_recent_commits:
            try:
                url = f"{self.api_url}/repos/{repo_info['owner']}/{repo_info['repo']}/commits?per_page=10"
                response = requests.get(url, headers=self.headers, timeout=10)
                
                if response.status_code == 200:
                    commits = response.json()
                    result["recent_commits"] = [
                        {
                            "sha": c["sha"][:7],
                            "message": c["commit"]["message"].split("\n")[0],
                            "author": c["commit"]["author"]["name"],
                            "date": c["commit"]["author"]["date"]
                        }
                        for c in commits[:10]
                    ]
            except Exception as e:
                result["commits_error"] = str(e)
        
        # Get file structure
        if include_file_structure:
            try:
                url = f"{self.api_url}/repos/{repo_info['owner']}/{repo_info['repo']}/contents"
                response = requests.get(url, headers=self.headers, timeout=10)
                
                if response.status_code == 200:
                    contents = response.json()
                    result["file_structure"] = [
                        {
                            "name": f["name"],
                            "type": f["type"],
                            "path": f["path"]
                        }
                        for f in contents if f["type"] in ["dir", "file"]
                    ]
            except Exception as e:
                result["structure_error"] = str(e)
        
        return result
    
    def generate_fix_from_context(self,
                                 service_name: str,
                                 error_type: str,
                                 root_cause: str,
                                 suggested_fix: str,
                                 affected_files: list = None,
                                 confidence: float = 0.7) -> dict:
        """
        Create PR with auto-generated fix based on GitHub repo context
        Used when RAG has no solution but we can infer fix from repo patterns
        
        Args:
            service_name: Service to fix
            error_type: Type of error
            root_cause: Analysis of root cause
            suggested_fix: LLM-generated fix suggestion
            affected_files: Files that should be modified
            confidence: Confidence in the fix (0-1)
        
        Returns:
            PR creation result
        """
        
        branch_name = f"autofix/{error_type.lower().replace('_', '-')}"
        
        # Generate PR body with detailed context
        pr_body = f"""## Auto-Generated Fix from Context Analysis

**Error Type:** {error_type}
**Root Cause:** {root_cause}
**Fix Confidence:** {confidence:.1%}

### Suggested Fix
{suggested_fix}

### Affected Files
{chr(10).join(f"- {f}" for f in (affected_files or ["TBD"]))}

### Context
- This fix was generated by analyzing your repository structure and recent commits
- Please review carefully before merging
- If confidence is low, expert review is strongly recommended

### Generated By
AutoSRE AI - No RAG match found, using context-aware fix generation
"""
        
        return self.create_pull_request(
            service_name=service_name,
            pr_title=f"[AUTO-FIX] {error_type}: {root_cause[:50]}",
            pr_body=pr_body,
            branch_name=branch_name,
            fix_type="context_based"
        )
