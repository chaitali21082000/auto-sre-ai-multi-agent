"""GitHub MCP Tool for creating issues and PRs"""
import json
from typing import Optional

def get_github_tools() -> list:
    """Get GitHub-related MCP tools with enhanced repo analysis"""
    return [
        {
            "name": "create_github_issue",
            "description": "Create a GitHub issue in the affected service repository",
            "input_schema": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the affected service"
                    },
                    "title": {
                        "type": "string",
                        "description": "Issue title"
                    },
                    "body": {
                        "type": "string",
                        "description": "Issue description with error details"
                    },
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Labels for the issue (e.g., bug, critical, auto-fix)"
                    },
                    "assignee": {
                        "type": "string",
                        "description": "GitHub username to assign issue to"
                    }
                },
                "required": ["service_name", "title", "body"]
            }
        },
        {
            "name": "create_github_pr",
            "description": "Create a pull request with fix code",
            "input_schema": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the affected service"
                    },
                    "pr_title": {
                        "type": "string",
                        "description": "Pull request title"
                    },
                    "pr_body": {
                        "type": "string",
                        "description": "PR description with change details"
                    },
                    "branch_name": {
                        "type": "string",
                        "description": "Feature branch name"
                    },
                    "fix_type": {
                        "type": "string",
                        "description": "Type of fix applied"
                    }
                },
                "required": ["service_name", "pr_title", "pr_body", "branch_name"]
            }
        },
        {
            "name": "get_repository_info",
            "description": "Get detailed repository information including structure and recent commits for context-aware fixes",
            "input_schema": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service"
                    },
                    "include_recent_commits": {
                        "type": "boolean",
                        "description": "Include last 10 commits for context (default: true)"
                    },
                    "include_file_structure": {
                        "type": "boolean",
                        "description": "Include repo file structure (default: true)"
                    }
                },
                "required": ["service_name"]
            }
        },
        {
            "name": "generate_fix_from_context",
            "description": "Generate auto-fix PR with suggested changes based on GitHub repo context when RAG has no solution",
            "input_schema": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the affected service"
                    },
                    "error_type": {
                        "type": "string",
                        "description": "Type of error that occurred"
                    },
                    "root_cause": {
                        "type": "string",
                        "description": "Root cause analysis"
                    },
                    "suggested_fix": {
                        "type": "string",
                        "description": "LLM-generated suggested fix based on repo context"
                    },
                    "affected_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files that should be modified"
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence in the suggested fix (0-1)"
                    }
                },
                "required": ["service_name", "error_type", "root_cause", "suggested_fix"]
            }
        }
    ]
