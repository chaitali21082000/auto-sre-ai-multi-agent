"""
Knowledge Base Management API Endpoints
Provides REST API for KB operations, stats, and validation
"""

import logging
from flask import Blueprint, request, jsonify
from app.rag.knowledge_manager import KnowledgeManager

logger = logging.getLogger(__name__)

kb_api_bp = Blueprint('kb_api', __name__, url_prefix='/api/kb')


@kb_api_bp.route('/solutions', methods=['GET'])
def get_all_solutions():
    """Get all solutions in KB"""
    try:
        solutions = KnowledgeManager.list_all_solutions()
        return jsonify({
            'status': 'success',
            'total': len(solutions),
            'solutions': solutions
        }), 200
    except Exception as e:
        logger.error(f"Error getting solutions: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@kb_api_bp.route('/solutions/<error_type>', methods=['GET'])
def get_solution(error_type):
    """Get specific solution by error type"""
    try:
        solution = KnowledgeManager.get_solution(error_type)
        if not solution:
            return jsonify({
                'status': 'not_found',
                'error_type': error_type
            }), 404
        
        return jsonify({
            'status': 'success',
            'solution': solution
        }), 200
    except Exception as e:
        logger.error(f"Error getting solution: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@kb_api_bp.route('/solutions/auto-learned', methods=['GET'])
def get_auto_learned_solutions():
    """Get only auto-learned solutions"""
    try:
        solutions = KnowledgeManager.list_learned_solutions()
        
        return jsonify({
            'status': 'success',
            'count': len(solutions),
            'solutions': solutions,
            'avg_confidence': round(sum(s.get('confidence', 0.80) for s in solutions) / len(solutions), 3) if solutions else 0
        }), 200
    except Exception as e:
        logger.error(f"Error getting auto-learned solutions: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@kb_api_bp.route('/solutions/manual', methods=['GET'])
def get_manual_solutions():
    """Get only manually added solutions"""
    try:
        solutions = KnowledgeManager.list_manual_solutions()
        
        return jsonify({
            'status': 'success',
            'count': len(solutions),
            'solutions': solutions,
            'avg_confidence': round(sum(s.get('confidence', 0.80) for s in solutions) / len(solutions), 3) if solutions else 0
        }), 200
    except Exception as e:
        logger.error(f"Error getting manual solutions: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@kb_api_bp.route('/solutions', methods=['POST'])
def add_solution():
    """Add a new solution to KB (manual or via API)"""
    try:
        data = request.json
        
        # Validate solution
        valid, issues = KnowledgeManager.validate_solution_quality(data)
        if not valid:
            return jsonify({
                'status': 'validation_failed',
                'issues': issues
            }), 400
        
        # Set defaults for manual additions
        if 'source' not in data:
            data['source'] = 'manual'
        if 'confidence' not in data:
            data['confidence'] = 0.90  # Higher confidence for manual
        if 'is_auto_learned' not in data:
            data['is_auto_learned'] = False
        
        # Add solution
        success = KnowledgeManager.add_solution(data)
        
        if success:
            return jsonify({
                'status': 'success',
                'error_type': data.get('error_type'),
                'confidence': data.get('confidence')
            }), 201
        else:
            return jsonify({
                'status': 'failed',
                'message': 'Failed to add solution'
            }), 500
    
    except Exception as e:
        logger.error(f"Error adding solution: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@kb_api_bp.route('/solutions/<error_type>/confidence', methods=['POST'])
def update_confidence(error_type):
    """
    Update confidence for a solution
    
    POST body:
    {
        "event": "SUCCESS|FAILURE|MANUAL_REVIEW|PARTIAL_SUCCESS",
        "value": 0.85  # Optional: specific value
    }
    """
    try:
        data = request.json
        event = data.get('event')
        value = data.get('value')
        
        if not event:
            return jsonify({
                'status': 'error',
                'message': 'Missing event field'
            }), 400
        
        success = KnowledgeManager.update_confidence(error_type, event, value)
        
        if success:
            solution = KnowledgeManager.get_solution(error_type)
            return jsonify({
                'status': 'success',
                'error_type': error_type,
                'new_confidence': solution.get('confidence'),
                'event': event
            }), 200
        else:
            return jsonify({
                'status': 'failed',
                'message': f'Solution not found: {error_type}'
            }), 404
    
    except Exception as e:
        logger.error(f"Error updating confidence: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@kb_api_bp.route('/solutions/<error_type>/validate', methods=['POST'])
def validate_solution_endpoint(error_type):
    """
    Mark solution as validated after successful use
    Increases validation count and bumps confidence
    """
    try:
        solution = KnowledgeManager.get_solution(error_type)
        if not solution:
            return jsonify({
                'status': 'not_found',
                'error_type': error_type
            }), 404
        
        # Increment validation count
        solution['validation_count'] = solution.get('validation_count', 1) + 1
        
        # Bump confidence
        old_conf = solution['confidence']
        new_conf = min(old_conf + 0.03, 0.95)
        solution['confidence'] = new_conf
        
        # Save
        kb = KnowledgeManager.load_kb()
        idx = next((i for i, s in enumerate(kb['scenarios']) 
                   if s['error_type'] == error_type), None)
        if idx is not None:
            kb['scenarios'][idx] = solution
            KnowledgeManager.save_kb(kb)
        
        return jsonify({
            'status': 'success',
            'error_type': error_type,
            'validation_count': solution['validation_count'],
            'old_confidence': old_conf,
            'new_confidence': new_conf
        }), 200
    
    except Exception as e:
        logger.error(f"Error validating solution: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@kb_api_bp.route('/solutions/<error_type>', methods=['DELETE'])
def delete_solution(error_type):
    """
    Delete a solution from KB
    Use carefully! This cannot be undone without backup
    """
    try:
        # Confirm deletion
        confirm = request.args.get('confirm', 'false').lower() == 'true'
        if not confirm:
            return jsonify({
                'status': 'error',
                'message': 'Must confirm deletion with ?confirm=true'
            }), 400
        
        success = KnowledgeManager.delete_solution(error_type)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'Deleted solution: {error_type}'
            }), 200
        else:
            return jsonify({
                'status': 'not_found',
                'error_type': error_type
            }), 404
    
    except Exception as e:
        logger.error(f"Error deleting solution: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@kb_api_bp.route('/stats', methods=['GET'])
def get_kb_statistics():
    """Get knowledge base statistics"""
    try:
        stats = KnowledgeManager.get_kb_statistics()
        
        return jsonify({
            'status': 'success',
            'statistics': stats
        }), 200
    except Exception as e:
        logger.error(f"Error getting KB stats: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@kb_api_bp.route('/health', methods=['GET'])
def kb_health():
    """Check KB health and integrity"""
    try:
        stats = KnowledgeManager.get_kb_statistics()
        solutions = KnowledgeManager.list_all_solutions()
        
        # Check for issues
        issues = []
        
        # Check for low-confidence solutions that have many validations
        for sol in solutions:
            conf = sol.get('confidence', 0.80)
            val_count = sol.get('validation_count', 1)
            
            if val_count > 5 and conf < 0.60:
                issues.append(f"{sol['error_type']}: Too many validations ({val_count}) but low confidence ({conf})")
        
        health_status = 'healthy' if not issues else 'warning'
        
        return jsonify({
            'status': 'success',
            'health': health_status,
            'statistics': stats,
            'issues': issues
        }), 200
    except Exception as e:
        logger.error(f"Error checking KB health: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
