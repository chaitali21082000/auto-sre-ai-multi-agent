"""
Dummy service that runs on Cloud Run and generates error logs
This service simulates various real-world errors
"""
from flask import Flask, jsonify
import logging
import random
import datetime
import traceback

app = Flask(__name__)

# Setup logging to capture errors
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ServiceError:
    """Represents different types of service errors"""
    
    @staticmethod
    def database_connection_error():
        """Simulates DB connection pool exhaustion"""
        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "service": "billing-service",
            "error_type": "DB_CONNECTION_ERROR",
            "message": "Connection pool exhausted. Unable to acquire connection after 30s timeout.",
            "stack_trace": "com.mysql.jdbc.exceptions.jdbc4.CommunicationsException: Communications link failure",
            "details": {
                "pool_size": 50,
                "connections_active": 50,
                "queue_wait_time_ms": 45000
            }
        }
    
    @staticmethod
    def memory_leak_error():
        """Simulates high memory usage"""
        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "service": "api-server",
            "error_type": "MEMORY_LEAK",
            "message": f"Memory usage critical: {random.randint(85, 99)}% of {4}GB threshold",
            "stack_trace": "java.lang.OutOfMemoryError: Java heap space",
            "details": {
                "memory_used_gb": 3.8,
                "memory_limit_gb": 4,
                "process_pid": 2847,
                "rss_mb": 3840
            }
        }
    
    @staticmethod
    def api_timeout_error():
        """Simulates API request timeout"""
        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "service": "api-server",
            "error_type": "API_TIMEOUT",
            "message": "Request timeout after 60 seconds waiting for upstream service",
            "stack_trace": "java.net.SocketTimeoutException: Read timed out",
            "details": {
                "endpoint": "/api/v1/transactions",
                "method": "POST",
                "timeout_seconds": 60,
                "downstream_service": "payment-gateway"
            }
        }
    
    @staticmethod
    def authentication_failure():
        """Simulates auth token expiration"""
        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "service": "auth-service",
            "error_type": "AUTHENTICATION_FAILURE",
            "message": "Authentication failed: Invalid or expired service account token",
            "stack_trace": "com.google.auth.oauth2.OAuth2Exception: Invalid JWT",
            "details": {
                "service_account": "billing-worker@project.iam.gserviceaccount.com",
                "token_expired_at": "2024-04-07T16:00:00Z"
            }
        }
    
    @staticmethod
    def disk_space_full():
        """Simulates disk running out of space"""
        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "service": "database-service",
            "error_type": "DISK_SPACE_FULL",
            "message": "Disk space critical: /var/app is at 98% capacity",
            "stack_trace": "java.io.IOException: No space left on device",
            "details": {
                "path": "/var/app",
                "used_gb": 487,
                "total_gb": 500,
                "percentage": 98
            }
        }
    
    @staticmethod
    def cpu_high():
        """Simulates high CPU usage"""
        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "service": "notification-service",
            "error_type": "CPU_HIGH",
            "message": f"CPU usage critical: {random.randint(85, 99)}% sustained for 5 minutes",
            "stack_trace": "No exception - metric-based alert",
            "details": {
                "cpu_percentage": random.randint(85, 99),
                "process_name": "java",
                "thread_count": 256
            }
        }
    
    @staticmethod
    def network_latency():
        """Simulates high network latency"""
        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "service": "api-server",
            "error_type": "NETWORK_LATENCY",
            "message": "High network latency detected: 250ms p99 latency",
            "stack_trace": "No exception - performance metric",
            "details": {
                "p50_latency_ms": 50,
                "p95_latency_ms": 150,
                "p99_latency_ms": 250,
                "region": "us-central1"
            }
        }
    
    @staticmethod
    def permission_denied():
        """Simulates permission error"""
        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "service": "notification-service",
            "error_type": "PERMISSION_DENIED",
            "message": "Access denied: Service account lacks required permissions",
            "stack_trace": "com.google.api.gax.rpc.PermissionDeniedException: Permission denied",
            "details": {
                "service_account": "notifications@project.iam.gserviceaccount.com",
                "resource": "projects/project-id/topics/alerts",
                "required_role": "roles/pubsub.publisher"
            }
        }


class ErrorSimulator:
    """Randomly generates different service errors"""
    
    ERROR_TYPES = [
        ServiceError.database_connection_error,
        ServiceError.memory_leak_error,
        ServiceError.api_timeout_error,
        ServiceError.authentication_failure,
        ServiceError.disk_space_full,
        ServiceError.cpu_high,
        ServiceError.network_latency,
        ServiceError.permission_denied
    ]
    
    @staticmethod
    def get_random_error():
        """Get a random error"""
        error_generator = random.choice(ErrorSimulator.ERROR_TYPES)
        return error_generator()
    
    @staticmethod
    def get_specific_error(error_type: str):
        """Get specific error by type"""
        error_map = {
            "DB_CONNECTION_ERROR": ServiceError.database_connection_error,
            "MEMORY_LEAK": ServiceError.memory_leak_error,
            "API_TIMEOUT": ServiceError.api_timeout_error,
            "AUTHENTICATION_FAILURE": ServiceError.authentication_failure,
            "DISK_SPACE_FULL": ServiceError.disk_space_full,
            "CPU_HIGH": ServiceError.cpu_high,
            "NETWORK_LATENCY": ServiceError.network_latency,
            "PERMISSION_DENIED": ServiceError.permission_denied
        }
        generator = error_map.get(error_type)
        if generator:
            return generator()
        return None


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.route("/", methods=["GET"])
def home():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "service": "dummy-service",
        "version": "1.0"
    })


@app.route("/generate-error", methods=["GET"])
def generate_random_error():
    """
    Generate a random error log
    This simulates a service experiencing a real problem
    """
    error = ErrorSimulator.get_random_error()
    logger.error(f"Service Error: {error}")
    return jsonify(error)


@app.route("/generate-error/<error_type>", methods=["GET"])
def generate_specific_error(error_type):
    """
    Generate specific error by type
    
    Example: GET /generate-error/DB_CONNECTION_ERROR
    """
    error = ErrorSimulator.get_specific_error(error_type)
    if not error:
        return jsonify({"error": f"Unknown error type: {error_type}"}), 400
    
    logger.error(f"Service Error: {error}")
    return jsonify(error)


@app.route("/health", methods=["GET"])
def health():
    """Detailed health check"""
    return jsonify({
        "status": "ok",
        "service": "dummy-service",
        "timestamp": datetime.datetime.now().isoformat()
    })


@app.route("/errors", methods=["GET"])
def list_error_types():
    """List all available error types"""
    error_types = [
        "DB_CONNECTION_ERROR",
        "MEMORY_LEAK",
        "API_TIMEOUT",
        "AUTHENTICATION_FAILURE",
        "DISK_SPACE_FULL",
        "CPU_HIGH",
        "NETWORK_LATENCY",
        "PERMISSION_DENIED"
    ]
    return jsonify({
        "available_errors": error_types,
        "usage": "GET /generate-error/<error_type>"
    })


if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║         Dummy Service - Error Generator                   ║
    ╠════════════════════════════════════════════════════════════╣
    ║ GET /                  - Health check                      ║
    ║ GET /health            - Detailed health                   ║
    ║ GET /errors            - List available errors             ║
    ║ GET /generate-error    - Generate random error             ║
    ║ GET /generate-error/DB_CONNECTION_ERROR                    ║
    ║                        - Generate specific error           ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    app.run(host="0.0.0.0", port=8001, debug=False)
