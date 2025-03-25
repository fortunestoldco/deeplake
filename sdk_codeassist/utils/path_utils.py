import re
import os
from urllib.parse import urlparse
from sdk_codeassist.config import settings

def is_valid_sdk_path(path: str) -> bool:
    """
    Check if a path is valid for SDK documentation ingestion.
    
    Args:
        path: The path to check
        
    Returns:
        True if the path is valid, False otherwise
    """
    # Check if it's a URL or local path
    if path.startswith("http://") or path.startswith("https://"):
        # Parse URL
        parsed_url = urlparse(path)
        hostname = parsed_url.netloc
        
        # Check if hostname is in allowed sources
        for allowed_source in settings.allowed_sdk_sources:
            if hostname.endswith(allowed_source.replace("https://", "").replace("http://", "")):
                return True
                
        return False
    else:
        # Check if local path exists
        return os.path.exists(path)

def extract_repo_name(repo_url: str) -> str:
    """
    Extract repository name from URL.
    
    Args:
        repo_url: Repository URL
        
    Returns:
        Repository name
    """
    # Remove .git extension
    repo_url = repo_url.rstrip(".git")
    
    # Extract the final part of the URL
    repo_name = repo_url.split("/")[-1]
    
    return repo_name
