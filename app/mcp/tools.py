"""MCP Tool Definitions for GCP Services and GitHub Integration"""
import json
from typing import Any

# MCP Tool Schema Definitions
MCP_TOOLS = [
    {
        "name": "store_incident",
        "description": "Store incident analysis results in Firestore for audit and learning",
        "input_schema": {
            "type": "object",
            "properties": {
                "log": {
                    "type": "string",
                    "description": "Original error log"
                },
                "error_type": {
                    "type": "string",
                    "description": "Classified error type"
                },
                "severity": {
                    "type": "string",
                    "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
                    "description": "Error severity level"
                },
                "root_cause": {
                    "type": "string",
                    "description": "Identified root cause"
                },
                "recommended_action": {
                    "type": "string",
                    "description": "Recommended action"
                }
            },
            "required": ["log", "error_type", "severity", "root_cause"]
        }
    },
    {
        "name": "publish_alert",
        "description": "Publish alert to monitoring system via Pub/Sub",
        "input_schema": {
            "type": "object",
            "properties": {
                "error_type": {
                    "type": "string",
                    "description": "Type of error"
                },
                "severity": {
                    "type": "string",
                    "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
                },
                "message": {
                    "type": "string",
                    "description": "Alert message"
                },
                "action": {
                    "type": "string",
                    "enum": ["AUTO_FIX", "ALERT", "ESCALATE"],
                    "description": "Action to take"
                }
            },
            "required": ["error_type", "severity", "action"]
        }
    },
    {
        "name": "trigger_auto_fix",
        "description": "Trigger automated fix through Cloud Functions",
        "input_schema": {
            "type": "object",
            "properties": {
                "error_type": {
                    "type": "string",
                    "description": "Type of error to fix"
                },
                "fix_type": {
                    "type": "string",
                    "description": "Type of fix to apply"
                },
                "parameters": {
                    "type": "object",
                    "description": "Fix-specific parameters"
                }
            },
            "required": ["error_type", "fix_type"]
        }
    },
    {
        "name": "search_knowledge_base",
        "description": "Search knowledge base for similar incidents and solutions",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Query to search"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "default": 3
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "create_github_issue",
        "description": "Create a GitHub issue in the affected service repository for tracking",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the affected service (e.g., billing-service)"
                },
                "title": {
                    "type": "string",
                    "description": "Issue title describing the problem"
                },
                "body": {
                    "type": "string",
                    "description": "Detailed issue description with error logs and analysis"
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Labels for categorization (e.g., bug, critical, auto-detected)"
                },
                "assignee": {
                    "type": "string",
                    "description": "GitHub username to assign the issue to"
                }
            },
            "required": ["service_name", "title", "body"]
        }
    },
    {
        "name": "create_github_pr",
        "description": "Create a GitHub pull request with proposed fixes in the service repository",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the service repository"
                },
                "pr_title": {
                    "type": "string",
                    "description": "Pull request title"
                },
                "pr_body": {
                    "type": "string",
                    "description": "PR description explaining the fix"
                },
                "branch_name": {
                    "type": "string",
                    "description": "Feature branch name (e.g., fix/db-connection-pool)"
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
        "description": "Get detailed repository information including recent commits and file structure for context-aware fixes",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the service"
                },
                "include_recent_commits": {
                    "type": "boolean",
                    "description": "Include last 10 commits (default: true)"
                },
                "include_file_structure": {
                    "type": "boolean",
                    "description": "Include repository file structure (default: true)"
                }
            },
            "required": ["service_name"]
        }
    },
    {
        "name": "generate_fix_from_context",
        "description": "Generate a pull request with context-aware fix when RAG has no solution",
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

def get_tool_schema(tool_name: str) -> dict:
    """Get schema for a specific tool"""
    for tool in MCP_TOOLS:
        if tool["name"] == tool_name:
            return tool
    return None

def get_all_tools() -> list[dict]:
    """Get all available tools"""
    return MCP_TOOLS

def format_tools_for_prompt() -> str:
    """Format tools as text for LLM prompt"""
    tools_text = "AVAILABLE TOOLS:\n\n"
    for tool in MCP_TOOLS:
        tools_text += f"## {tool['name']}\n"
        tools_text += f"Description: {tool['description']}\n"
        tools_text += f"Parameters:\n"
        props = tool['input_schema']['properties']
        for param, details in props.items():
            required = param in tool['input_schema'].get('required', [])
            req_str = "(REQUIRED)" if required else "(OPTIONAL)"
            tools_text += f"  - {param} {req_str}: {details.get('description', '')}\n"
        tools_text += "\n"
    return tools_text
