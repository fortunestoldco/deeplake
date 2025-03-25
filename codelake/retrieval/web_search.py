import logging
import requests
import time
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_community.utilities import GoogleSearchAPIWrapper, GoogleSerperAPIWrapper
from langchain_community.document_loaders import WebBaseLoader
from bs4 import BeautifulSoup
from codelake.config import settings

logger = logging.getLogger(__name__)

class WebSearchRetriever(BaseRetriever):
    """Retriever that searches the web for SDK documentation."""
    
    def __init__(
        self,
        search_wrapper: Optional[Any] = None,
        max_results: int = 3,
        sdk_name: Optional[str] = None
    ):
        """
        Initialize the web search retriever.
        
        Args:
            search_wrapper: Search API wrapper instance
            max_results: Maximum number of search results to process
            sdk_name: Optional SDK name to include in searches
        """
        super().__init__()
        self.max_results = max_results
        self.sdk_name = sdk_name
        
        # Initialize search wrapper if not provided
        if search_wrapper is None:
            if settings.google_api_key and settings.google_cse_id:
                self.search_wrapper = GoogleSearchAPIWrapper(
                    google_api_key=settings.google_api_key,
                    google_cse_id=settings.google_cse_id
                )
            else:
                # Fallback to direct searches
                self.search_wrapper = None
                logger.warning("No search API credentials provided. Using direct web requests for searches.")
        else:
            self.search_wrapper = search_wrapper
    
    def direct_search(self, query: str, num_results: int = 3) -> List[Dict[str, str]]:
        """
        Perform a direct web search without using API.
        This is a fallback method when API keys are not available.
        """
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            search_results = []
            
            for result in soup.select('div.g')[:num_results]:
                link_element = result.select_one('a')
                description_element = result.select_one('div.VwiC3b')
                
                if link_element and description_element:
                    link = link_element.get('href', '')
                    if link.startswith('/url?q='):
                        link = link.split('/url?q=')[1].split('&')[0]
                        
                    title = link_element.get_text()
                    description = description_element.get_text()
                    
                    if link and not link.startswith('/'):
                        search_results.append({
                            'link': link,
                            'title': title,
                            'snippet': description
                        })
                        
            return search_results
        except Exception as e:
            logger.error(f"Error in direct search: {e}")
            return []
    
    def _get_relevant_documents(self, query: str) -> List[Document]:
        """Search the web for SDK documentation related to the query."""
        
        # Construct search query
        search_query = query
        if self.sdk_name:
            search_query = f"{self.sdk_name} {search_query} documentation"
        else:
            search_query = f"{search_query} sdk documentation"
            
        logger.info(f"Performing web search for: '{search_query}'")
        
        # Get search results
        try:
            if self.search_wrapper:
                results = self.search_wrapper.results(search_query, self.max_results)
            else:
                results = self.direct_search(search_query, self.max_results)
                
            if not results:
                logger.warning(f"No web search results found for '{search_query}'")
                return []
                
            # Load web content
            docs = []
            for result in results:
                try:
                    link = result.get('link') or result.get('url') 
                    if not link:
                        continue
                        
                    logger.debug(f"Loading content from {link}")
                    loader = WebBaseLoader(link)
                    web_docs = loader.load()
                    
                    # Add metadata
                    for doc in web_docs:
                        doc.metadata['source'] = link
                        doc.metadata['title'] = result.get('title', '')
                        doc.metadata['snippet'] = result.get('snippet', '')
                        
                    docs.extend(web_docs)
                    
                    # Throttle requests to avoid rate limiting
                    time.sleep(1)
                    
                except Exception as e:
                    logger.warning(f"Error loading content from {link}: {e}")
                    continue
            
            return docs
            
        except Exception as e:
            logger.error(f"Web search error: {e}", exc_info=True)
            return []
