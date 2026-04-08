"""
Knowledge Base Manager - Handles KB operations including feedback loop learning
Manages adding solutions, validation, confidence updates, and FAISS index rebuilding
Supports both local and GCS storage with fallback
"""

import json
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

try:
    from google.cloud import storage
    HAS_GCS = True
except ImportError:
    HAS_GCS = False

try:
    from google.cloud import firestore
    HAS_FIRESTORE = True
except ImportError:
    HAS_FIRESTORE = False

logger = logging.getLogger(__name__)
if not HAS_GCS:
    logger.warning("Google Cloud Storage not available - will use local storage only")
if not HAS_FIRESTORE:
    logger.warning("Firestore not available")


class KnowledgeManager:
    """Manages knowledge base with feedback loop support"""
    
    KB_PATH = 'app/rag/knowledge_base.json'
    
    @staticmethod
    def load_kb() -> dict:
        """Load KB from Cloud Storage with fallback to local file"""
        # Try GCS first if available
        if HAS_GCS:
            try:
                storage_client = storage.Client()
                bucket_name = os.getenv("KB_BUCKET_NAME", "autosre-kb-default")
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob("knowledge_base.json")
                
                if blob.exists():
                    content = blob.download_as_string()
                    logger.info("Loaded KB from Cloud Storage")
                    return json.loads(content)
                logger.debug("KB blob not found in Cloud Storage")
            except Exception as e:
                logger.debug(f"Could not load KB from GCS: {e}")
        
        # Fallback to local file
        try:
            if os.path.exists(KnowledgeManager.KB_PATH):
                with open(KnowledgeManager.KB_PATH) as f:
                    logger.info("Loaded KB from local file")
                    return json.load(f)
        except Exception as local_err:
            logger.warning(f"Could not load KB from local file: {local_err}")
        
        return {"scenarios": []}
    
    @staticmethod
    def save_kb(kb: dict) -> bool:
        """Save KB to Cloud Storage with fallback to local file"""
        saved_to_gcs = False
        
        # Try GCS first if available
        if HAS_GCS:
            try:
                storage_client = storage.Client()
                bucket_name = os.getenv("KB_BUCKET_NAME", "autosre-kb-default")
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob("knowledge_base.json")
                
                blob.upload_from_string(
                    json.dumps(kb, indent=2),
                    content_type="application/json"
                )
                logger.info("KB saved to Cloud Storage")
                saved_to_gcs = True
            except Exception as e:
                logger.debug(f"Error saving KB to GCS: {e}")
        
        # Always try local backup
        try:
            os.makedirs("app/rag", exist_ok=True)
            with open(KnowledgeManager.KB_PATH, "w") as f:
                json.dump(kb, f, indent=2)
            logger.info("KB backed up to local file")
            return True
        except Exception as e:
            logger.error(f"Error saving KB to local file: {e}")
            return saved_to_gcs
    
    @staticmethod
    def add_solution(solution: dict) -> bool:
        """
        Add new solution to knowledge base
        
        Args:
            solution: Dictionary with error_type, description, fix_type, steps, etc.
        
        Returns:
            bool: True if added successfully
        """
        try:
            # Validate solution first
            valid, issues = KnowledgeManager.validate_solution_quality(solution)
            if not valid:
                logger.warning(f"Solution validation failed: {issues}")
                return False
            
            # Load existing KB
            kb = KnowledgeManager.load_kb()
            
            # Check if solution already exists
            existing = next(
                (s for s in kb['scenarios'] 
                 if s['error_type'] == solution['error_type']),
                None
            )
            
            if existing:
                # Solution exists - update it
                logger.info(f"Updating existing solution for {solution['error_type']}")
                
                # Update validation count
                existing['validation_count'] = existing.get('validation_count', 1) + 1
                
                # Increase confidence slightly (up to 0.95 max for learned)
                old_conf = existing.get('confidence', 0.80)
                new_conf = min(old_conf + 0.05, 0.95)
                existing['confidence'] = new_conf
                
                # Add to learned_from history
                if 'learned_from_history' not in existing:
                    existing['learned_from_history'] = [existing.get('learned_from', '')]
                existing['learned_from_history'].append(solution.get('learned_from', ''))
                
                # Update last updated timestamp
                existing['last_updated'] = datetime.now().isoformat()
                
                logger.info(f"Updated confidence: {old_conf:.2f} → {new_conf:.2f}")
                return KnowledgeManager.save_kb(kb)
            
            # Add new solution
            solution['added_at'] = datetime.now().isoformat()
            kb['scenarios'].append(solution)
            
            # Save updated KB
            success = KnowledgeManager.save_kb(kb)
            
            if success:
                logger.info(f"✅ Added solution for {solution['error_type']} to KB")
                logger.info(f"   Confidence: {solution.get('confidence', 0.80)}")
                logger.info(f"   Source: {solution.get('source', 'manual')}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error adding solution: {e}")
            return False
    
    @staticmethod
    def validate_solution_quality(solution: dict) -> Tuple[bool, List[str]]:
        """
        Validate solution before adding to KB
        
        Args:
            solution: Solution dict to validate
        
        Returns:
            Tuple (valid: bool, issues: list of validation issues)
        """
        issues = []
        
        # Check required fields
        required_fields = ['error_type', 'description', 'fix_type', 'steps']
        for field in required_fields:
            if not solution.get(field):
                issues.append(f"Missing required field: {field}")
        
        # Validate error_type format (should be UPPER_CASE)
        if solution.get('error_type'):
            if not solution['error_type'].isupper() or ' ' in solution['error_type']:
                issues.append(f"error_type should be UPPER_CASE with underscores")
        
        # Validate steps (must be list with at least 2 steps)
        if solution.get('steps'):
            if not isinstance(solution['steps'], list):
                issues.append("steps must be a list")
            elif len(solution['steps']) < 2:
                issues.append("steps should have at least 2 steps")
        
        # Validate confidence (should be 0-1)
        if solution.get('confidence'):
            if not isinstance(solution['confidence'], (int, float)):
                issues.append("confidence must be a number")
            elif not (0 <= solution['confidence'] <= 1):
                issues.append("confidence must be between 0 and 1")
        
        # Validate severity
        if solution.get('severity'):
            valid_severities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
            if solution['severity'] not in valid_severities:
                issues.append(f"severity must be one of: {valid_severities}")
        
        return (len(issues) == 0, issues)
    
    @staticmethod
    def get_solution(error_type: str) -> Optional[dict]:
        """
        Retrieve specific solution from KB
        
        Args:
            error_type: Error type to search for
        
        Returns:
            Solution dict or None if not found
        """
        try:
            kb = KnowledgeManager.load_kb()
            return next(
                (s for s in kb['scenarios'] 
                 if s['error_type'] == error_type),
                None
            )
        except Exception as e:
            logger.error(f"Error getting solution: {e}")
            return None
    
    @staticmethod
    def list_all_solutions() -> List[dict]:
        """List all solutions in KB"""
        try:
            kb = KnowledgeManager.load_kb()
            return kb.get('scenarios', [])
        except Exception as e:
            logger.error(f"Error listing solutions: {e}")
            return []
    
    @staticmethod
    def list_learned_solutions() -> List[dict]:
        """List only auto-learned solutions"""
        try:
            kb = KnowledgeManager.load_kb()
            learned = [s for s in kb['scenarios'] if s.get('is_auto_learned', False)]
            return learned
        except Exception as e:
            logger.error(f"Error listing learned solutions: {e}")
            return []
    
    @staticmethod
    def list_manual_solutions() -> List[dict]:
        """List only manually added solutions"""
        try:
            kb = KnowledgeManager.load_kb()
            manual = [s for s in kb['scenarios'] if not s.get('is_auto_learned', False)]
            return manual
        except Exception as e:
            logger.error(f"Error listing manual solutions: {e}")
            return []
    
    @staticmethod
    def update_confidence(error_type: str, event: str, value: Optional[float] = None) -> bool:
        """
        Update confidence for a solution based on event
        
        Args:
            error_type: Error type
            event: Event type - SUCCESS, FAILURE, MANUAL_REVIEW, PARTIAL_SUCCESS
            value: Optional specific confidence value
        
        Returns:
            bool: Success
        """
        try:
            kb = KnowledgeManager.load_kb()
            solution = next(
                (s for s in kb['scenarios'] if s['error_type'] == error_type),
                None
            )
            
            if not solution:
                logger.warning(f"Solution not found: {error_type}")
                return False
            
            old_conf = solution.get('confidence', 0.80)
            
            if value is not None:
                # Set specific value
                new_conf = max(0.0, min(value, 1.0))
            elif event == 'SUCCESS':
                # Bump up, but cap at 0.95
                new_conf = min(old_conf + 0.05, 0.95)
            elif event == 'FAILURE':
                # Significant drop
                new_conf = max(old_conf - 0.15, 0.40)
            elif event == 'MANUAL_REVIEW':
                # Expert boost
                new_conf = min(old_conf + 0.10, 0.98)
            elif event == 'PARTIAL_SUCCESS':
                # Minor bump
                new_conf = min(old_conf + 0.02, 0.95)
            else:
                logger.warning(f"Unknown event type: {event}")
                return False
            
            solution['confidence'] = new_conf
            solution['last_updated'] = datetime.now().isoformat()
            
            if 'confidence_history' not in solution:
                solution['confidence_history'] = []
            
            solution['confidence_history'].append({
                'old': old_conf,
                'new': new_conf,
                'event': event,
                'timestamp': datetime.now().isoformat()
            })
            
            success = KnowledgeManager.save_kb(kb)
            
            if success:
                logger.info(f"Updated confidence for {error_type}: {old_conf:.2f} → {new_conf:.2f} ({event})")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating confidence: {e}")
            return False
    
    @staticmethod
    def get_kb_statistics() -> dict:
        """Get knowledge base statistics"""
        try:
            kb = KnowledgeManager.load_kb()
            solutions = kb.get('scenarios', [])
            auto_learned = [s for s in solutions if s.get('is_auto_learned', False)]
            manual = [s for s in solutions if not s.get('is_auto_learned', False)]
            
            avg_conf = sum(s.get('confidence', 0.80) for s in solutions) / len(solutions) if solutions else 0
            auto_avg_conf = sum(s.get('confidence', 0.80) for s in auto_learned) / len(auto_learned) if auto_learned else 0
            manual_avg_conf = sum(s.get('confidence', 0.80) for s in manual) / len(manual) if manual else 0
            
            return {
                'total_solutions': len(solutions),
                'manual_solutions': len(manual),
                'auto_learned_solutions': len(auto_learned),
                'avg_confidence': round(avg_conf, 3),
                'manual_avg_confidence': round(manual_avg_conf, 3),
                'auto_learned_avg_confidence': round(auto_avg_conf, 3),
                'learning_rate': round(len(auto_learned) / len(solutions) * 100, 1) if solutions else 0,
                'kb_file_size_bytes': os.path.getsize(KnowledgeManager.KB_PATH)
            }
        except Exception as e:
            logger.error(f"Error getting KB stats: {e}")
            return {}
    
    @staticmethod
    def delete_solution(error_type: str) -> bool:
        """
        Delete a solution from KB (use carefully!)
        
        Args:
            error_type: Error type to remove
        
        Returns:
            bool: Success
        """
        try:
            kb = KnowledgeManager.load_kb()
            original_count = len(kb['scenarios'])
            
            kb['scenarios'] = [
                s for s in kb['scenarios']
                if s['error_type'] != error_type
            ]
            
            if len(kb['scenarios']) < original_count:
                success = KnowledgeManager.save_kb(kb)
                if success:
                    logger.warning(f"Deleted solution: {error_type}")
                return success
            else:
                logger.warning(f"Solution not found to delete: {error_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting solution: {e}")
            return False


def rebuild_faiss_index():
    """
    Rebuild FAISS index after KB changes
    This ensures new solutions are searchable immediately
    """
    try:
        from app.rag.rag_engine import get_rag_engine
        
        logger.info("🔄 Rebuilding FAISS index...")
        engine = get_rag_engine()
        engine.rebuild_index()
        logger.info("✅ FAISS index rebuilt successfully")
        return True
    except Exception as e:
        logger.error(f"Error rebuilding FAISS index: {e}")
        return False
