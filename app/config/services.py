"""Service to GitHub repository mapping"""

SERVICE_GITHUB_MAP = {
    "billing-service": {
        "owner": "your-org",
        "repo": "billing-service",
        "url": "https://github.com/your-org/billing-service",
        "branch": "main",
        "issues_enabled": True,
        "pull_requests_enabled": True
    },
    "api-server": {
        "owner": "your-org",
        "repo": "api-server",
        "url": "https://github.com/your-org/api-server",
        "branch": "main",
        "issues_enabled": True,
        "pull_requests_enabled": True
    },
    "database-service": {
        "owner": "your-org",
        "repo": "database-service",
        "url": "https://github.com/your-org/database-service",
        "branch": "main",
        "issues_enabled": True,
        "pull_requests_enabled": True
    },
    "auth-service": {
        "owner": "your-org",
        "repo": "auth-service",
        "url": "https://github.com/your-org/auth-service",
        "branch": "main",
        "issues_enabled": True,
        "pull_requests_enabled": True
    },
    "notification-service": {
        "owner": "your-org",
        "repo": "notification-service",
        "url": "https://github.com/your-org/notification-service",
        "branch": "main",
        "issues_enabled": True,
        "pull_requests_enabled": True
    }
}

def get_service_repo(service_name: str):
    """Get GitHub repo details for a service"""
    return SERVICE_GITHUB_MAP.get(service_name)

def get_all_services():
    """Get all registered services"""
    return list(SERVICE_GITHUB_MAP.keys())
