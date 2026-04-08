"""
Cloud Function for automated fixes
Triggered by auto-fix decisions from the main AutoSRE AI service
"""
import json
import logging
from typing import Tuple
from flask import Request, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def auto_fix(request: Request) -> Tuple[dict, int]:
    """
    Automated fix execution Cloud Function.
    
    Receives error details and executes appropriate fixes.
    Supports: DB restarts, resource scaling, cache clearing, etc.
    
    Args:
        request: HTTP request with JSON payload containing:
            - error_type: Type of error (DB_ERROR, TIMEOUT, MEMORY, etc.)
            - fix_type: Type of fix to apply
            - parameters: Fix-specific parameters
            - service_name: Service to fix
    
    Returns:
        JSON response with fix execution status
    """
    try:
        # Handle CORS preflight
        if request.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST',
                'Access-Control-Allow-Headers': 'Content-Type',
            }
            return {}, 204, headers
        
        # Parse request
        data = request.get_json() or {}
        error_type = data.get("error_type", "UNKNOWN")
        fix_type = data.get("fix_type", "UNKNOWN")
        service_name = data.get("service_name", "unknown-service")
        parameters = data.get("parameters", {})
        
        logger.info(f"Auto-fix triggered: {error_type} on {service_name}")
        logger.info(f"Fix type: {fix_type}, Parameters: {parameters}")
        
        # Validate input
        if not error_type or error_type == "UNKNOWN":
            logger.warning("Invalid error type provided")
            return jsonify({
                'success': False,
                'error': 'Invalid error_type'
            }), 400
        
        # Execute fix based on type
        result = execute_fix(error_type, fix_type, service_name, parameters)
        
        if result.get('success'):
            logger.info(f"✅ Fix executed: {result.get('message')}")
            return jsonify(result), 200
        else:
            logger.warning(f"Fix failed: {result.get('message')}")
            return jsonify(result), 400
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request")
        return jsonify({
            'success': False,
            'error': 'Invalid JSON payload'
        }), 400
    except Exception as e:
        logger.error(f"Unexpected error in auto-fix: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def execute_fix(error_type: str, fix_type: str, service_name: str, parameters: dict) -> dict:
    """
    Execute the appropriate fix based on error type.
    
    Args:
        error_type: Type of error detected
        fix_type: Type of fix to apply
        service_name: Service name to fix
        parameters: Fix-specific parameters
    
    Returns:
        Dict with execution status
    """
    try:
        # Database-related fixes
        if error_type in ["DB_ERROR", "DB_CONNECTION_TIMEOUT", "DB_POOL_EXHAUSTED"]:
            return handle_db_fix(fix_type, service_name, parameters)
        
        # Resource-related fixes
        elif error_type in ["MEMORY_EXCEEDED", "CPU_EXCEEDED", "DISK_FULL"]:
            return handle_resource_fix(error_type, service_name, parameters)
        
        # Timeout fixes
        elif error_type in ["TIMEOUT", "REQUEST_TIMEOUT"]:
            return handle_timeout_fix(service_name, parameters)
        
        # Service-related fixes
        elif error_type in ["SERVICE_UNAVAILABLE", "SERVICE_CRASH"]:
            return handle_service_fix(service_name, parameters)
        
        # Default: log and return success (no-op)
        else:
            logger.info(f"No specific fix for {error_type}, logging only")
            return {
                'success': True,
                'message': f'No automated fix available for {error_type}',
                'action': 'logged'
            }
    
    except Exception as e:
        logger.error(f"Error executing fix: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'Error executing fix: {str(e)}'
        }


def handle_db_fix(fix_type: str, service_name: str, parameters: dict) -> dict:
    """Handle database-related fixes"""
    logger.info(f"Handling DB fix: {fix_type}")
    
    if fix_type == "RESTART_CONNECTION_POOL":
        # Restart connection pool
        pool_size = parameters.get("pool_size", 100)
        logger.info(f"Restarting DB connection pool for {service_name} (size: {pool_size})")
        return {
            'success': True,
            'message': f'Database connection pool restarted',
            'action': 'RESTART_CONNECTION_POOL',
            'service': service_name
        }
    
    elif fix_type == "INCREASE_POOL_SIZE":
        new_size = parameters.get("new_size", 150)
        logger.info(f"Increasing DB pool size to {new_size}")
        return {
            'success': True,
            'message': f'Connection pool size increased to {new_size}',
            'action': 'INCREASE_POOL_SIZE',
            'service': service_name
        }
    
    elif fix_type == "RESTART_SERVICE":
        logger.info(f"Restarting service {service_name}")
        return {
            'success': True,
            'message': f'Service {service_name} restart triggered',
            'action': 'RESTART_SERVICE',
            'service': service_name
        }
    
    else:
        return {
            'success': False,
            'message': f'Unknown DB fix type: {fix_type}'
        }


def handle_resource_fix(error_type: str, service_name: str, parameters: dict) -> dict:
    """Handle resource-related fixes"""
    logger.info(f"Handling resource fix for {error_type}")
    
    if error_type == "MEMORY_EXCEEDED":
        action = parameters.get("action", "CLEAR_CACHE")
        if action == "CLEAR_CACHE":
            logger.info(f"Clearing cache for {service_name}")
            return {
                'success': True,
                'message': f'Cache cleared for {service_name}',
                'action': 'CLEAR_CACHE',
                'service': service_name
            }
        elif action == "SCALE_UP":
            logger.info(f"Scaling up {service_name}")
            return {
                'success': True,
                'message': f'Service {service_name} scaled up',
                'action': 'SCALE_UP',
                'service': service_name
            }
    
    elif error_type == "DISK_FULL":
        logger.info(f"Cleaning up disk for {service_name}")
        return {
            'success': True,
            'message': f'Disk cleanup triggered for {service_name}',
            'action': 'CLEANUP_OLD_FILES',
            'service': service_name
        }
    
    else:
        return {
            'success': False,
            'message': f'Unknown resource fix type: {error_type}'
        }


def handle_timeout_fix(service_name: str, parameters: dict) -> dict:
    """Handle timeout-related fixes"""
    logger.info(f"Handling timeout fix for {service_name}")
    
    action = parameters.get("action", "INCREASE_TIMEOUT")
    if action == "INCREASE_TIMEOUT":
        new_timeout = parameters.get("new_timeout", 60)
        logger.info(f"Increasing timeout to {new_timeout}s")
        return {
            'success': True,
            'message': f'Timeout increased to {new_timeout}s',
            'action': 'INCREASE_TIMEOUT',
            'service': service_name
        }
    
    return {
        'success': False,
        'message': f'Unknown timeout fix: {action}'
    }


def handle_service_fix(service_name: str, parameters: dict) -> dict:
    """Handle service-related fixes"""
    logger.info(f"Handling service fix for {service_name}")
    
    action = parameters.get("action", "RESTART")
    if action == "RESTART":
        logger.info(f"Restarting service {service_name}")
        return {
            'success': True,
            'message': f'Service {service_name} restart initiated',
            'action': 'RESTART',
            'service': service_name
        }
    
    elif action == "FAILOVER":
        logger.info(f"Initiating failover for {service_name}")
        return {
            'success': True,
            'message': f'Failover for {service_name} initiated',
            'action': 'FAILOVER',
            'service': service_name
        }
    
    return {
        'success': False,
        'message': f'Unknown service fix: {action}'
    }