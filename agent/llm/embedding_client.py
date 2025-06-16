"""
Embedding Client for Docureco Agent
Generates vector embeddings for semantic search capabilities
Now supports both free (Sentence Transformers) and paid (OpenAI) options
"""

import os
import logging
from typing import List, Dict, Any, Optional
import asyncio

logger = logging.getLogger(__name__)

# Try to import free embedding client first
try:
    from .free_embedding_client import FreeEmbeddingClient, create_free_embedding_client
    FREE_EMBEDDINGS_AVAILABLE = True
except ImportError:
    FREE_EMBEDDINGS_AVAILABLE = False

# Try to import OpenAI embeddings as fallback
try:
    from langchain_openai import OpenAIEmbeddings
    from langchain_core.embeddings import Embeddings
    OPENAI_EMBEDDINGS_AVAILABLE = True
except ImportError:
    OPENAI_EMBEDDINGS_AVAILABLE = False

class DocurecoEmbeddingClient:
    """
    Embedding client for generating vector embeddings
    Supports both free (Sentence Transformers) and paid (OpenAI) options
    Defaults to free embeddings to avoid API costs
    """
    
    def __init__(self, 
                 use_free: bool = True,
                 model: str = None,
                 api_key: Optional[str] = None,
                 batch_size: int = 100,
                 embedding_type: str = "fast"):
        """
        Initialize embedding client
        
        Args:
            use_free: Whether to use free embeddings (default: True)
            model: Embedding model name (auto-selected if None)
            api_key: API key for paid services (only needed if use_free=False)
            batch_size: Batch size for processing multiple texts
            embedding_type: Type of free embedding ("fast", "balanced", "code", etc.)
        """
        self.use_free = use_free
        self.batch_size = batch_size
        self.embedding_type = embedding_type
        
        if self.use_free:
            if not FREE_EMBEDDINGS_AVAILABLE:
                logger.warning("Free embeddings not available, falling back to OpenAI")
                self.use_free = False
            else:
                # Use free embeddings
                self.client = create_free_embedding_client(
                    model_type=embedding_type,
                    custom_model=model
                )
                logger.info(f"Initialized FREE embedding client with model: {self.client.model_name}")
                return
        
        # Fallback to OpenAI embeddings
        if not OPENAI_EMBEDDINGS_AVAILABLE:
            raise ImportError("Neither free nor OpenAI embeddings are available. Install sentence-transformers or langchain-openai")
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for paid embeddings")
        
        self.model = model or "text-embedding-3-small"
        
        # Initialize LangChain OpenAI embeddings
        self.embeddings = OpenAIEmbeddings(
            model=self.model,
            api_key=self.api_key,
            chunk_size=self.batch_size
        )
        
        logger.info(f"Initialized PAID embedding client with model: {self.model}")
    
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text
        
        Args:
            text: Text to embed
            
        Returns:
            List[float]: Vector embedding
        """
        try:
            if self.use_free:
                return await self.client.embed_text(text)
            else:
                if not text or not text.strip():
                    # Return zero vector for empty text
                    return [0.0] * 1536
                
                # Use LangChain's async method
                embedding = await self.embeddings.aembed_query(text.strip())
                return embedding
                
        except Exception as e:
            logger.error(f"Error generating embedding for text: {str(e)}")
            # Return zero vector as fallback
            dim = 384 if self.use_free else 1536
            return [0.0] * dim
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List[List[float]]: List of vector embeddings
        """
        try:
            if self.use_free:
                return await self.client.embed_texts(texts)
            else:
                if not texts:
                    return []
                
                # Process texts in batches
                embeddings = []
                for i in range(0, len(texts), self.batch_size):
                    batch = texts[i:i + self.batch_size]
                    # Filter out empty texts
                    filtered_batch = [text.strip() for text in batch if text and text.strip()]
                    
                    if filtered_batch:
                        batch_embeddings = await self.embeddings.aembed_documents(filtered_batch)
                        embeddings.extend(batch_embeddings)
                    else:
                        # Add zero vectors for empty texts
                        embeddings.extend([[0.0] * 1536 for _ in batch])
                
                return embeddings
            
        except Exception as e:
            logger.error(f"Error generating embeddings for texts: {str(e)}")
            # Return zero vectors as fallback
            dim = 384 if self.use_free else 1536
            return [[0.0] * dim for _ in texts]
    
    async def embed_requirement(self, requirement: Dict[str, Any]) -> Dict[str, List[float]]:
        """
        Generate embeddings for a requirement
        
        Args:
            requirement: Requirement data with title and description
            
        Returns:
            Dict[str, List[float]]: Dictionary with title_embedding, description_embedding, combined_embedding
        """
        if self.use_free:
            return await self.client.embed_requirement(requirement)
        else:
            title = requirement.get("title", "")
            description = requirement.get("description", "")
            combined = f"{title}. {description}".strip()
            
            # Generate embeddings for all variants
            embeddings = await self.embed_texts([title, description, combined])
            
            return {
                "title_embedding": embeddings[0],
                "description_embedding": embeddings[1],
                "combined_embedding": embeddings[2]
            }
    
    async def embed_design_element(self, design_element: Dict[str, Any]) -> Dict[str, List[float]]:
        """
        Generate embeddings for a design element
        
        Args:
            design_element: Design element data with name and description
            
        Returns:
            Dict[str, List[float]]: Dictionary with name_embedding, description_embedding, combined_embedding
        """
        if self.use_free:
            return await self.client.embed_design_element(design_element)
        else:
            name = design_element.get("name", "")
            description = design_element.get("description", "")
            element_type = design_element.get("type", "")
            combined = f"{name} ({element_type}). {description}".strip()
            
            # Generate embeddings for all variants
            embeddings = await self.embed_texts([name, description, combined])
            
            return {
                "name_embedding": embeddings[0],
                "description_embedding": embeddings[1],
                "combined_embedding": embeddings[2]
            }
    
    async def embed_code_component(self, code_component: Dict[str, Any]) -> Dict[str, List[float]]:
        """
        Generate embeddings for a code component
        
        Args:
            code_component: Code component data with path and name
            
        Returns:
            Dict[str, List[float]]: Dictionary with path_embedding, name_embedding
        """
        if self.use_free:
            return await self.client.embed_code_component(code_component)
        else:
            path = code_component.get("path", "")
            name = code_component.get("name", "")
            
            embeddings = []
            texts_to_embed = []
            
            # Always embed path
            texts_to_embed.append(path)
            
            # Embed name if available
            if name:
                texts_to_embed.append(name)
            else:
                texts_to_embed.append("")  # Empty for consistency
            
            embeddings = await self.embed_texts(texts_to_embed)
            
            result = {"path_embedding": embeddings[0]}
            if name:
                result["name_embedding"] = embeddings[1]
            
            return result
    
    async def embed_code_change_context(self, 
                                       filename: str, 
                                       patch: str, 
                                       commit_message: str) -> List[float]:
        """
        Generate embedding for code change context
        
        Args:
            filename: Name of changed file
            patch: Code diff/patch
            commit_message: Commit message
            
        Returns:
            List[float]: Vector embedding for the code change context
        """
        if self.use_free:
            return await self.client.embed_code_change_context(filename, patch, commit_message)
        else:
            # Create a comprehensive context string
            context_parts = []
            
            if filename:
                context_parts.append(f"File: {filename}")
            
            if commit_message:
                context_parts.append(f"Change: {commit_message}")
            
            if patch:
                # Extract meaningful parts from patch (avoid noise)
                patch_lines = patch.split('\n')
                meaningful_lines = []
                for line in patch_lines[:20]:  # Limit to first 20 lines
                    if line.startswith(('+', '-')) and not line.startswith(('+++', '---')):
                        meaningful_lines.append(line[1:].strip())  # Remove +/- prefix
                
                if meaningful_lines:
                    context_parts.append(f"Code changes: {' '.join(meaningful_lines[:10])}")  # First 10 lines
            
            context = ". ".join(context_parts)
            return await self.embed_text(context)
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the embedding model
        
        Returns:
            Dict[str, Any]: Model information
        """
        if self.use_free:
            return self.client.get_model_info()
        else:
            return {
                "model": self.model,
                "dimensions": 1536,  # text-embedding-3-small dimensions
                "batch_size": self.batch_size,
                "provider": "OpenAI",
                "is_local": False,
                "cost_per_token": 0.00002  # Approximate cost
            }

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this client"""
        if self.use_free:
            return 384  # Sentence Transformers default
        else:
            return 1536  # OpenAI text-embedding-3-small

def create_embedding_client(
    use_free: bool = True,
    embedding_type: str = "fast",
    model: str = None,
    api_key: Optional[str] = None,
    batch_size: int = 100
) -> DocurecoEmbeddingClient:
    """
    Factory function to create embedding client
    
    Args:
        use_free: Whether to use free embeddings (default: True)
        embedding_type: Type of free embedding ("fast", "balanced", "code", etc.)
        model: Embedding model name (for paid services)
        api_key: Optional API key (for paid services)
        batch_size: Batch size for processing
        
    Returns:
        DocurecoEmbeddingClient: Configured embedding client
    """
    return DocurecoEmbeddingClient(
        use_free=use_free,
        model=model,
        api_key=api_key,
        batch_size=batch_size,
        embedding_type=embedding_type
    )

# Export main classes
__all__ = ["DocurecoEmbeddingClient", "create_embedding_client"]

# Also export free embedding classes if available
if FREE_EMBEDDINGS_AVAILABLE:
    __all__.extend(["FreeEmbeddingClient", "create_free_embedding_client", "RECOMMENDED_MODELS"]) 