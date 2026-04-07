"""
Scheduled Knowledge Base Sync Job
Syncs knowledge base from GitHub every 6 hours
Finds merged PRs with 'auto-detected-fix' label and learns solutions
"""

import os
import logging
import schedule
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from threading import Thread

from github import Github
from app.rag.knowledge_manager import KnowledgeManager, rebuild_faiss_index
from app.api.webhook_handler import extract_solution_from_pr

logger = logging.getLogger(__name__)


class KnowledgeBaseSyncJob:
    """Scheduled job for syncing KB from GitHub"""
    
    def __init__(self, github_token: str = None, interval_hours: int = 6):
        """
        Initialize sync job
        
        Args:
            github_token: GitHub API token
            interval_hours: How often to run sync (default 6 hours)
        """
        self.github_token = github_token or os.getenv('GITHUB_TOKEN', '')
        self.interval_hours = interval_hours
        self.auto_fix_repos: List[str] = []
        self.is_running = False
        self.scheduler_thread = None
    
    def add_repo(self, repo_path: str):
        """Add repository to sync list"""
        if repo_path not in self.auto_fix_repos:
            self.auto_fix_repos.append(repo_path)
            logger.info(f"Added repo to sync: {repo_path}")
    
    def set_repos(self, repos: List[str]):
        """Set list of repositories to sync"""
        self.auto_fix_repos = repos
        logger.info(f"Set repos for sync: {repos}")
    
    def sync_kb_from_github(self):
        """
        Sync knowledge base from GitHub
        Finds merged PRs and learns solutions from them
        This is the main job function
        """
        logger.info(f"🔄 Starting KB sync from GitHub ({len(self.auto_fix_repos)} repos)...")
        
        if not self.github_token:
            logger.error("GitHub token not configured - sync failed")
            return False
        
        if not self.auto_fix_repos:
            logger.warning("No repositories configured for sync")
            return False
        
        try:
            # Initialize GitHub client
            g = Github(self.github_token)
            
            solutions_added = 0
            solutions_updated = 0
            solutions_failed = 0
            
            # Sync each repository
            for repo_path in self.auto_fix_repos:
                try:
                    logger.info(f"Syncing repo: {repo_path}")
                    repo = g.get_repo(repo_path)
                    
                    # Find merged PRs with auto-detected-fix label in last 6 hours
                    merged_prs = repo.get_pulls(
                        state='closed',
                        base='main',
                        label='auto-detected-fix'
                    )
                    
                    pr_count = 0
                    for pr in merged_prs:
                        pr_count += 1
                        if pr_count > 50:  # Limit to prevent API abuse
                            break
                        
                        if not pr.merged:
                            continue
                        
                        # Check if recently merged (within last 6 hours)
                        if pr.merged_at:
                            age_hours = (datetime.utcnow() - pr.merged_at.replace(tzinfo=None)).total_seconds() / 3600
                            if age_hours > self.interval_hours:
                                continue  # Older than interval
                        
                        # Check if already in KB
                        from app.api.webhook_handler import extract_error_type_from_title
                        error_type = extract_error_type_from_title(pr.title)
                        
                        if not error_type:
                            logger.warning(f"PR #{pr.number}: Could not extract error type")
                            solutions_failed += 1
                            continue
                        
                        if KnowledgeManager.get_solution(error_type):
                            logger.info(f"PR #{pr.number}: Solution already in KB")
                            solutions_updated += 1
                            continue
                        
                        # Extract solution from PR
                        pr_data = {
                            'title': pr.title,
                            'body': pr.body or '',
                            'html_url': pr.html_url,
                            'number': pr.number,
                            'merged_by': {'login': pr.merged_by.login if pr.merged_by else 'unknown'}
                        }
                        
                        solution = extract_solution_from_pr(pr_data)
                        
                        if not solution:
                            logger.warning(f"PR #{pr.number}: Failed to parse solution")
                            solutions_failed += 1
                            continue
                        
                        # Validate quality
                        valid, issues = KnowledgeManager.validate_solution_quality(solution)
                        if not valid:
                            logger.warning(f"PR #{pr.number}: Validation failed: {issues}")
                            solutions_failed += 1
                            continue
                        
                        # Add to KB
                        if KnowledgeManager.add_solution(solution):
                            solutions_added += 1
                            logger.info(f"✅ Added: {error_type} from PR #{pr.number}")
                        else:
                            solutions_failed += 1
                            logger.warning(f"Failed to add solution from PR #{pr.number}")
                    
                except Exception as e:
                    logger.error(f"Error syncing repo {repo_path}: {e}")
                    continue
            
            # Rebuild FAISS index if we added anything
            if solutions_added > 0:
                rebuild_faiss_index()
                logger.info(f"✅ KB sync complete: {solutions_added} added, {solutions_updated} updated, {solutions_failed} failed")
                return True
            else:
                logger.info(f"KB sync complete: No new solutions to add")
                return True
            
        except Exception as e:
            logger.error(f"❌ KB sync failed: {e}")
            return False
    
    def start_scheduler(self):
        """Start the scheduler in background thread"""
        if self.is_running:
            logger.warning("Scheduler already running")
            return
        
        logger.info(f"Starting KB sync scheduler (every {self.interval_hours} hours)")
        
        # Schedule the job
        schedule.every(self.interval_hours).hours.do(self.sync_kb_from_github)
        
        # Also run immediately on startup (after delay)
        schedule.at("00:00").do(self.sync_kb_from_github)
        
        self.is_running = True
        
        # Start background thread
        self.scheduler_thread = Thread(target=self._run_scheduler)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        
        logger.info("✅ KB sync scheduler started")
    
    def _run_scheduler(self):
        """Background scheduler loop"""
        logger.info("Scheduler loop starting...")
        
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)
    
    def stop_scheduler(self):
        """Stop the scheduler"""
        self.is_running = False
        logger.info("KB sync scheduler stopped")
    
    def get_status(self) -> dict:
        """Get scheduler status"""
        return {
            'is_running': self.is_running,
            'interval_hours': self.interval_hours,
            'repos_count': len(self.auto_fix_repos),
            'repos': self.auto_fix_repos
        }


# Global instance
_sync_job_instance: Optional[KnowledgeBaseSyncJob] = None


def get_sync_job() -> KnowledgeBaseSyncJob:
    """Get global sync job instance"""
    global _sync_job_instance
    if _sync_job_instance is None:
        _sync_job_instance = KnowledgeBaseSyncJob()
    return _sync_job_instance


def initialize_sync_job(repos: List[str] = None, interval_hours: int = 6):
    """
    Initialize and start the sync job
    
    Args:
        repos: List of repos to sync
        interval_hours: Sync interval
    """
    global _sync_job_instance
    
    _sync_job_instance = KnowledgeBaseSyncJob(interval_hours=interval_hours)
    
    if repos:
        _sync_job_instance.set_repos(repos)
    else:
        # Default repos
        default_repos = [
            'your-org/billing-service',
            'your-org/api-server',
            'your-org/database-service',
            'your-org/cache-service',
        ]
        _sync_job_instance.set_repos(default_repos)
    
    _sync_job_instance.start_scheduler()
    
    logger.info("KB sync job initialized and started")
