"""
GitHub Webhook Handler
Receives webhook events for PR merges and issues being closed
Extracts solutions and adds to knowledge base with feedback loop integration
"""

import json
import re
import logging
import hmac
import hashlib
import os
from datetime import datetime
from typing import Dict, Optional

from flask import request, jsonify, Blueprint

try:
    from google.cloud import secretmanager
    HAS_SECRET_MANAGER = True
except ImportError:
    HAS_SECRET_MANAGER = False

from app.rag.knowledge_manager import KnowledgeManager, rebuild_faiss_index

# Create Blueprint for webhook routes
webhook_bp = Blueprint('webhook', __name__)

logger = logging.getLogger(__name__)

def get_secret_from_manager(secret_id: str) -> Optional[str]:
    """Get secret from Secret Manager"""
    if not HAS_SECRET_MANAGER:
        logger.debug("Secret Manager not available")
        return None
    
    try:
        client = secretmanager.SecretManagerServiceClient()
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "auto-sre-ai-multi-agent-492710")
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        logger.warning(f"Could not fetch {secret_id} from Secret Manager: {e}")
        return None


def verify_github_signature(payload_body: bytes, signature_header: str, secret: str = None) -> bool:
    """
    Verify GitHub webhook signature
    
    Args:
        payload_body: Raw request body
        signature_header: X-Hub-Signature-256 header value
        secret: Webhook secret (optional, will fetch from Secret Manager if not provided)
    
    Returns:
        bool: True if signature is valid
    """
    if not signature_header:
        logger.warning("No signature provided")
        return False
    
    # Get secret from Secret Manager if not provided
    if not secret:
        try:
            secret = get_secret_from_manager("github-webhook-secret")
        except:
            pass
    
    # Fallback to environment variable
    if not secret:
        secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    
    if not secret:
        logger.warning("No webhook secret configured")
        return False
    
    try:
        hash_object = hmac.new(
            secret.encode('utf-8'),
            msg=payload_body,
            digestmod=hashlib.sha256
        )
        expected_signature = "sha256=" + hash_object.hexdigest()
        
        return hmac.compare_digest(expected_signature, signature_header)
    except Exception as e:
        logger.error(f"Error verifying signature: {e}")
        return False


def extract_error_type_from_title(title: str) -> Optional[str]:
    """Extract error type from PR title"""
    # Expected format: "fix: Increase JVM heap for MEMORY_EXCEEDED" or "[AUTO-FIX] MEMORY_EXCEEDED"
    
    # Try pattern: [AUTO-FIX] ERROR_TYPE
    match = re.search(r'\[AUTO-FIX\]\s+(\w+)', title)
    if match:
        return match.group(1)
    
    # Try to find UPPER_CASE_ERROR type in title
    match = re.search(r'\b([A-Z_]{3,})\b', title)
    if match:
        error_type = match.group(1)
        # Basic check - should have at least 2 underscores or all caps
        if error_type.isupper() and len(error_type) > 2:
            return error_type
    
    return None


def extract_solution_from_pr(pr_data: dict) -> Optional[dict]:
    """
    Parse PR description and title to extract solution
    
    Args:
        pr_data: GitHub PR data from webhook
    
    Returns:
        Solution dict or None
    """
    title = pr_data.get('title', '')
    body = pr_data.get('body', '')
    html_url = pr_data.get('html_url', '')
    number = pr_data.get('number', 0)
    merged_by = pr_data.get('merged_by', {}).get('login', 'unknown')
    
    logger.info(f"Extracting solution from PR #{number}: {title}")
    
    solution_dict = {
        'source': 'feedback-loop',
        'learned_from': html_url,
        'date_added': datetime.now().isoformat(),
        'confidence': 0.80,  # Start lower for auto-learned
        'validation_count': 1,
        'is_auto_learned': True,
        'pr_number': number,
        'merged_by': merged_by,
    }
    
    try:
        # Parse error type from title
        error_type = extract_error_type_from_title(title)
        if not error_type:
            logger.warning(f"Could not extract error type from PR title: {title}")
            return None
        
        solution_dict['error_type'] = error_type
        
        # Parse description from PR body
        # Look for patterns like "**Error Type:** MEMORY_EXCEEDED" or "Error: ..."
        desc_patterns = [
            r'(?:Error Type:|Error:|**Error[:\s]+.*?\n\s*)(.*?)(?:\n|$)',
            r'**Description.*?\n(.*?)(?:\n\n|$)',
        ]
        
        description = None
        for pattern in desc_patterns:
            match = re.search(pattern, body, re.IGNORECASE | re.DOTALL)
            if match:
                description = match.group(1).strip()
                if description:
                    break
        
        if not description:
            description = f"Auto-detected: {error_type}"
        
        solution_dict['description'] = description
        
        # Parse root cause
        root_cause_patterns = [
            r'(?:Root Cause|Root cause|Cause):\s*(.*?)(?:\n|$)',
            r'**Root Cause[:\s]+.*?\n\s*(.*?)(?:\n\n|$)',
        ]
        
        root_cause = None
        for pattern in root_cause_patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                root_cause = match.group(1).strip()
                if root_cause:
                    break
        
        solution_dict['root_cause'] = root_cause or "See PR for details"
        
        # Parse fix type
        fix_patterns = [
            r'(?:Fix Type|Fix type):\s*(\w+)',
            r'**Fix[:\s]+.*?\n\s*([A-Z_]+)',
        ]
        
        fix_type = None
        for pattern in fix_patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                fix_type = match.group(1).strip().upper()
                if fix_type:
                    break
        
        if not fix_type:
            fix_type = f"FIX_{error_type}"
        
        solution_dict['fix_type'] = fix_type
        
        # Parse steps
        steps_patterns = [
            r'### Suggested Changes\n(.*?)(?:\n###|\Z)',
            r'### Steps\n(.*?)(?:\n###|\Z)',
            r'### Solution\n(.*?)(?:\n###|\Z)',
            r'### Fix\n(.*?)(?:\n###|\Z)',
        ]
        
        steps_text = None
        for pattern in steps_patterns:
            match = re.search(pattern, body, re.DOTALL)
            if match:
                steps_text = match.group(1)
                break
        
        if steps_text:
            # Extract numbered or bulleted steps
            step_lines = re.findall(r'^\s*(?:\d+\.|[-*])\s+(.+?)$', steps_text, re.MULTILINE)
            steps = [s.strip() for s in step_lines if s.strip()]
            
            if not steps:
                # Fallback: split by newlines
                steps = [s.strip() for s in steps_text.split('\n') if s.strip() and len(s.strip()) > 5]
        else:
            steps = ["See PR description for fix details"]
        
        if steps:
            solution_dict['steps'] = steps
        else:
            logger.warning("Could not extract steps from PR")
            solution_dict['steps'] = ["Refer to PR changes"]
        
        # Parse severity
        severity_match = re.search(r'(?:Severity|SEVERITY):\s*(HIGH|CRITICAL|MEDIUM|LOW)', body, re.IGNORECASE)
        if severity_match:
            solution_dict['severity'] = severity_match.group(1).upper()
        else:
            solution_dict['severity'] = 'HIGH'
        
        # Parse confidence if provided
        confidence_match = re.search(r'(?:Confidence|Confidence Score):\s*(\d+(?:\.\d+)?)', body, re.IGNORECASE)
        if confidence_match:
            conf = float(confidence_match.group(1))
            solution_dict['confidence'] = max(0.0, min(conf, 0.95)) if conf > 1 else min(conf, 0.95)
        
        logger.info(f"✅ Successfully extracted solution: {error_type}")
        return solution_dict
        
    except Exception as e:
        logger.error(f"Error extracting solution from PR: {e}")
        return None


@webhook_bp.route('/github', methods=['POST'])
def github_webhook():
    """
    Receives GitHub webhook events
    Events: PR merged with label "auto-detected-fix", Issue closed with label "error-fixed"
    """
    
    try:
        # Verify signature
        secret = os.getenv('GITHUB_WEBHOOK_SECRET', '')
        if secret:
            signature = request.headers.get('X-Hub-Signature-256', '')
            if not verify_github_signature(request.get_data(), signature, secret):
                logger.warning("Invalid webhook signature")
                return jsonify({'status': 'invalid-signature'}), 401
        
        payload = request.json
        event_type = request.headers.get('X-GitHub-Event')
        
        logger.info(f"Received GitHub webhook: {event_type}")
        
        if event_type == 'pull_request':
            return handle_pr_event(payload)
        elif event_type == 'issues':
            return handle_issue_event(payload)
        else:
            logger.info(f"Ignoring event type: {event_type}")
            return jsonify({'status': 'ignored'}), 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


def handle_pr_event(payload: dict) -> tuple:
    """Process PR merge event"""
    
    action = payload.get('action')
    pr = payload.get('pull_request', {})
    
    pr_number = pr.get('number', 0)
    
    # Only process merged PRs
    if action != 'closed' or not pr.get('merged'):
        logger.info(f"PR #{pr_number}: Ignoring (not merged)")
        return jsonify({'status': 'not-merged'}), 200
    
    # Check for auto-detected-fix label
    labels = [label['name'] for label in pr.get('labels', [])]
    
    if 'auto-detected-fix' not in labels:
        logger.info(f"PR #{pr_number}: Missing 'auto-detected-fix' label")
        return jsonify({'status': 'not-autofix'}), 200
    
    logger.info(f"PR #{pr_number}: Processing auto-detected-fix")
    
    # Extract solution from PR
    solution = extract_solution_from_pr(pr)
    
    if not solution:
        logger.error(f"PR #{pr_number}: Failed to parse solution")
        return jsonify({'status': 'parse-failed', 'message': 'Could not extract solution'}), 400
    
    # Validate solution quality
    valid, issues = KnowledgeManager.validate_solution_quality(solution)
    if not valid:
        logger.warning(f"PR #{pr_number}: Solution validation failed: {issues}")
        return jsonify({'status': 'validation-failed', 'issues': issues}), 400
    
    # Add to knowledge base
    success = KnowledgeManager.add_solution(solution)
    
    if success:
        # Rebuild FAISS index
        rebuild_faiss_index()
        
        logger.info(f"✅ PR #{pr_number}: Learned solution for {solution['error_type']}")
        
        return jsonify({
            'status': 'learned',
            'error_type': solution['error_type'],
            'confidence': solution.get('confidence', 0.80),
            'pr_number': pr_number
        }), 200
    else:
        logger.error(f"PR #{pr_number}: Failed to add solution to KB")
        return jsonify({'status': 'failed', 'message': 'Failed to add to KB'}), 500


def handle_issue_event(payload: dict) -> tuple:
    """Process issue closed event"""
    
    action = payload.get('action')
    issue = payload.get('issue', {})
    issue_number = issue.get('number', 0)
    
    # Only process closed issues
    if action != 'closed':
        logger.info(f"Issue #{issue_number}: Ignoring (not closed)")
        return jsonify({'status': 'not-closed'}), 200
    
    # Check for error-fixed label
    labels = [label['name'] for label in issue.get('labels', [])]
    
    if 'error-fixed' not in labels:
        logger.info(f"Issue #{issue_number}: Missing 'error-fixed' label")
        return jsonify({'status': 'not-error-fixed'}), 200
    
    logger.info(f"Issue #{issue_number}: Error marked as fixed (currently not processing)")
    
    # Future: Could extract solution from closed issue if needed
    return jsonify({'status': 'issue-closed'}), 200
