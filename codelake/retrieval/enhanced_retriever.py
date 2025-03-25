import logging
from typing import List, Dict, Any, Optional, Callable
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_openai import OpenAIEmbeddings
from langchain_deeplake.vectorstores import DeeplakeVectorStore
from codelake.retrieval.web_search import WebSearchRetriever
from codelake.config import settings

logger = logging.getLogger(__name__)

class SDKRetriever(BaseRetriever):
    """
    Enhanced retriever for SDK documentation with fallback to web search
    when confidence is low.
    """
    
    def __init__(
        self,
        vector_store: DeeplakeVectorStore,
        web_retriever: Optional[WebSearchRetriever] = None,
        confidence_threshold: float = 0.85,
        k: int = 5,
        filter_fn: Optional[Callable[[Document], bool]] = None
    ):
        """
        Initialize the SDKRetriever.
        
        Args:
            vector_store: DeepLake vector store containing SDK documentation
            web_retriever: Optional web search retriever for fallback
            confidence_threshold: Threshold below which to use web search fallback
            k: Number of documents to retrieve
            filter_fn: Optional function to filter results
        """
        super().__init__()
        self.vector_store = vector_store
        self.web_retriever = web_retriever
        self.confidence_threshold = confidence_threshold
        self.k = k
        self.filter_fn = filter_fn
        
    def _get_relevant_documents(self, query: str) -> List[Document]:
        """Get documents relevant to the query."""
        # First try vector store retrieval
        try:
            vector_results = self.vector_store.similarity_search_with_score(
                query, 
                k=self.k,
                distance_metric=settings.distance_metric,
                fetch_k=settings.fetch_k
            )
            
            # Extract documents and scores
            docs = [doc for doc, _ in vector_results]
            scores = [score for _, score in vector_results]
            
            # Calculate average confidence
            avg_confidence = sum(scores) / len(scores) if scores else 0
            max_confidence = max(scores) if scores else 0
            logger.debug(f"Vector search: avg_confidence={avg_confidence:.3f}, max_confidence={max_confidence:.3f}")
            
            # Apply filters if provided
            if self.filter_fn and docs:
                docs = [doc for doc in docs if self.filter_fn(doc)]
            
            # Check if confidence is sufficient
            if (not docs) or (max_confidence < self.confidence_threshold and settings.use_web_search):
                logger.info(f"Low confidence ({max_confidence:.3f} < {self.confidence_threshold}) or no results, trying web search")
                if self.web_retriever:
                    # Try web search fallback
                    web_docs = self.web_retriever.get_relevant_documents(
                        f"SDK documentation for {query}"
                    )
                    
                    # Combine results, prioritizing vector store results if they exist
                    if docs:
                        # Add web results with lower priority
                        combined = docs + [doc for doc in web_docs if doc.page_content not in [d.page_content for d in docs]]
                        return combined[:self.k]
                    else:
                        return web_docs[:self.k]
            
            return docs
            
        except Exception as e:
            logger.error(f"Error in vector retrieval: {e}", exc_info=True)
            if self.web_retriever:
                logger.info("Falling back to web search due to vector retrieval error")
                return self.web_retriever.get_relevant_documents(
                    f"SDK documentation for {query}"
                )[:self.k]
            return []

def setup_retriever(dataset_path: str) -> SDKRetriever:
    """
    Set up and return an enhanced SDK retriever.
    
    Args:
        dataset_path: Path to the Deep Lake dataset
    
    Returns:
        Configured SDKRetriever instance
    """
    # Initialize embeddings
    embeddings = OpenAIEmbeddings()
    
    # Initialize vector store
    vector_store = DeeplakeVectorStore(
        dataset_path=dataset_path,
        embedding_function=embeddings,
        read_only=True
    )
    
    # Initialize web search retriever if enabled
    web_retriever = WebSearchRetriever() if settings.use_web_search else None
    
    # Build enhanced retriever
    return SDKRetriever(
        vector_store=vector_store,
        web_retriever=web_retriever,
        confidence_threshold=settings.search_confidence_threshold,
        k=settings.fetch_k
    )
