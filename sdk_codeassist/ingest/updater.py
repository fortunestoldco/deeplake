import threading
import time
import logging
import schedule
from datetime import datetime
from typing import List, Optional
from sdk_codeassist.ingest.documentation_ingestion import ingest_sdk_documentation
from sdk_codeassist.config import settings

logger = logging.getLogger(__name__)

class DocumentationUpdater:
    """Service to automatically update SDK documentation on a schedule."""
    
    def __init__(self, repo_urls: List[str], dataset_paths: List[str], cron_schedule: str = "0 2 * * *"):
        """
        Initialize the updater service.
        
        Args:
            repo_urls: List of repository URLs to monitor
            dataset_paths: List of Deep Lake dataset paths, corresponding to repo_urls
            cron_schedule: Cron schedule string for when to run updates
        """
        if len(repo_urls) != len(dataset_paths):
            raise ValueError("repo_urls and dataset_paths must have the same length")
            
        self.repo_urls = repo_urls
        self.dataset_paths = dataset_paths
        self.cron_schedule = cron_schedule
        self.running = False
        self.thread = None
        self.last_update = None
        
    def update_all(self):
        """Update all repositories."""
        logger.info(f"Starting scheduled documentation update of {len(self.repo_urls)} repositories")
        
        success_count = 0
        for i, (repo_url, dataset_path) in enumerate(zip(self.repo_urls, self.dataset_paths)):
            logger.info(f"Updating [{i+1}/{len(self.repo_urls)}]: {repo_url}")
            try:
                success = ingest_sdk_documentation(repo_url, dataset_path)
                if success:
                    success_count += 1
            except Exception as e:
                logger.error(f"Failed to update {repo_url}: {e}", exc_info=True)
        
        self.last_update = datetime.now()
        logger.info(f"Scheduled update completed. {success_count}/{len(self.repo_urls)} successful.")
        
    def _updater_thread(self):
        """Thread function for the updater service."""
        logger.info(f"Documentation updater service started with schedule: {self.cron_schedule}")
        
        # Parse cron schedule and set up schedule
        schedule.clear()
        schedule.every().day.at("02:00").do(self.update_all)
        
        while self.running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
            
        logger.info("Documentation updater service stopped")
    
    def start(self):
        """Start the updater service."""
        if self.thread and self.thread.is_alive():
            logger.warning("Updater service is already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._updater_thread, daemon=True)
        self.thread.start()
        
    def stop(self):
        """Stop the updater service."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=10)
            
    def force_update(self):
        """Force an immediate update."""
        logger.info("Manual update triggered")
        self.update_all()

# Singleton instance
updater = None

def get_updater(repo_urls: Optional[List[str]] = None, dataset_paths: Optional[List[str]] = None):
    """Get or create the updater service."""
    global updater
    
    if updater is None:
        if repo_urls is None:
            repo_urls = [settings.repo_url]
        if dataset_paths is None:
            dataset_paths = [settings.deeplake_dataset_path]
            
        updater = DocumentationUpdater(
            repo_urls=repo_urls,
            dataset_paths=dataset_paths,
            cron_schedule=settings.update_schedule
        )
        
        if settings.enable_auto_updates:
            updater.start()
            
    return updater
