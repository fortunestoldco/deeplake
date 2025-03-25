import os
import tempfile
import logging
import git
from typing import List, Dict, Any, Optional, Union
from langchain_community.document_loaders import (
    GitLoader, 
    DirectoryLoader, 
    TextLoader, 
    PythonLoader, 
    ReadTheDocsLoader,
    JSONLoader,
    CSVLoader,
    UnstructuredMarkdownLoader
)
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    PythonCodeTextSplitter,
    MarkdownHeaderTextSplitter
)
from langchain_openai import OpenAIEmbeddings
from langchain_deeplake.vectorstores import DeeplakeVectorStore
from codelake.utils.path_utils import is_valid_sdk_path

logger = logging.getLogger(__name__)

def get_appropriate_loader(file_path: str):
    """Get the appropriate document loader based on file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    
    # Map file extensions to loaders
    extension_map = {
        '.py': PythonLoader,
        '.json': JSONLoader,
        '.csv': CSVLoader,
        '.md': UnstructuredMarkdownLoader,
        '.rst': TextLoader,
        '.txt': TextLoader,
    }
    
    loader_class = extension_map.get(ext, TextLoader)
    try:
        if loader_class == JSONLoader and ext == '.json':
            return loader_class(file_path, jq_schema='.', text_content=False)
        return loader_class(file_path)
    except Exception as e:
        logger.warning(f"Failed to load {file_path} with {loader_class.__name__}: {e}")
        # Fallback to TextLoader
        try:
            return TextLoader(file_path, encoding='utf-8')
        except Exception:
            try:
                return TextLoader(file_path, encoding='latin-1')
            except Exception as e2:
                logger.error(f"Could not load {file_path} with any loader: {e2}")
                return None

def get_appropriate_splitter(doc_type: str):
    """Get the appropriate text splitter based on document type."""
    if doc_type == 'python':
        return PythonCodeTextSplitter(chunk_size=1000, chunk_overlap=100)
    elif doc_type == 'markdown':
        headers_to_split_on = [
            ("#", "header1"),
            ("##", "header2"),
            ("###", "header3"),
            ("####", "header4"),
        ]
        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        return RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100, separators=["\n## ", "\n### ", "\n#### ", "\n", " ", ""])
    else:
        return RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)

def extract_metadata(file_path: str, content: str) -> Dict[str, Any]:
    """Extract metadata from file content for better retrieval."""
    metadata = {
        "source": file_path,
        "file_type": os.path.splitext(file_path)[1],
        "file_name": os.path.basename(file_path),
        "directory": os.path.dirname(file_path)
    }
    
    # Extract more specific metadata
    if file_path.endswith('.py'):
        # Extract class and function names
        import ast
        try:
            tree = ast.parse(content)
            classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            
            if classes:
                metadata["classes"] = classes
            if functions:
                metadata["functions"] = functions
        except Exception as e:
            logger.warning(f"Failed to extract Python metadata from {file_path}: {e}")
    
    return metadata

def ingest_sdk_documentation(repo_url: str, dataset_path: str, branch: str = "main"):
    """
    Ingest SDK documentation from a repository into Deep Lake.
    
    Args:
        repo_url: URL of the SDK repository
        dataset_path: Path to the Deep Lake dataset
        branch: Branch to clone
    """
    if not is_valid_sdk_path(repo_url):
        logger.error(f"Invalid SDK repository URL: {repo_url}")
        return False
        
    logger.info(f"Starting ingestion from {repo_url}, branch {branch}")
    
    # Create a temporary directory for the repo
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Clone the repository
            logger.info(f"Cloning repository to {temp_dir}...")
            git.Repo.clone_from(repo_url, temp_dir, branch=branch, depth=1)
            
            # Load documents
            logger.info("Loading documents...")
            docs = []
            
            # Load Python files
            python_loader = DirectoryLoader(
                temp_dir, 
                glob="**/*.py", 
                loader_cls=PythonLoader, 
                recursive=True,
                show_progress=True
            )
            python_docs = python_loader.load()
            logger.info(f"Loaded {len(python_docs)} Python files")
            
            # Load Markdown documentation
            markdown_loader = DirectoryLoader(
                temp_dir, 
                glob="**/*.md", 
                loader_cls=UnstructuredMarkdownLoader, 
                recursive=True,
                show_progress=True
            )
            markdown_docs = markdown_loader.load()
            logger.info(f"Loaded {len(markdown_docs)} Markdown files")
            
            # Load other documentation files
            doc_loader = DirectoryLoader(
                temp_dir, 
                glob="**/*.rst", 
                loader_cls=TextLoader, 
                recursive=True,
                show_progress=True
            )
            other_docs = doc_loader.load()
            logger.info(f"Loaded {len(other_docs)} other documentation files")
            
            # Combine all documents
            all_docs = python_docs + markdown_docs + other_docs
            
            # Add metadata
            for doc in all_docs:
                doc.metadata.update(extract_metadata(doc.metadata['source'], doc.page_content))
                # Make paths relative to the repo
                doc.metadata['source'] = doc.metadata['source'].replace(temp_dir, '')
                doc.metadata['directory'] = doc.metadata['directory'].replace(temp_dir, '')
                
            logger.info(f"Total documents loaded: {len(all_docs)}")
            
            # Process chunks based on document type
            logger.info("Processing documents into chunks...")
            python_splitter = get_appropriate_splitter('python')
            markdown_splitter = get_appropriate_splitter('markdown')
            general_splitter = get_appropriate_splitter('general')
            
            python_chunks = python_splitter.split_documents([d for d in all_docs if d.metadata['file_type'] == '.py'])
            markdown_chunks = markdown_splitter.split_documents([d for d in all_docs if d.metadata['file_type'] in ['.md', '.markdown']])
            other_chunks = general_splitter.split_documents([d for d in all_docs if d.metadata['file_type'] not in ['.py', '.md', '.markdown']])
            
            all_chunks = python_chunks + markdown_chunks + other_chunks
            logger.info(f"Created {len(all_chunks)} chunks")
            
            # Initialize OpenAI embeddings
            embeddings = OpenAIEmbeddings()
            
            # Check if dataset already exists
            logger.info(f"Storing chunks in Deep Lake at {dataset_path}...")
            try:
                # Try to access existing dataset
                db = DeeplakeVectorStore(
                    dataset_path=dataset_path,
                    embedding_function=embeddings,
                    overwrite=False
                )
                # Update existing dataset
                db.add_documents(all_chunks)
            except:
                # Create new dataset
                db = DeeplakeVectorStore.from_documents(
                    documents=all_chunks,
                    embedding=embeddings,
                    dataset_path=dataset_path,
                    overwrite=True
                )
            
            logger.info(f"Successfully stored {len(all_chunks)} chunks in Deep Lake")
            return True
            
        except Exception as e:
            logger.error(f"Error during ingestion: {e}", exc_info=True)
            return False
