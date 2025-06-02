"""
Embedding Client for Docureco Agent
Generates vector embeddings for semantic search capabilities
"""

import os
import logging
from typing import List, Dict, Any, Optional
import asyncio

from langchain_openai import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

class DocurecoEmbeddingClient:
    """
    Embedding client for generating vector embeddings
    Supports both OpenAI and Grok embeddings (fallback to OpenAI for embeddings)
    """
    
    def __init__(self, 
                 model: str = "text-embedding-3-small",
                 api_key: Optional[str] = None,
                 batch_size: int = 100):
        """
        Initialize embedding client
        
        Args:
            model: Embedding model name
            api_key: API key for embedding service
            batch_size: Batch size for processing multiple texts
        """
        self.model = model
        self.batch_size = batch_size
        
        # Use OpenAI for embeddings (Grok doesn't have embedding endpoint yet)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for embeddings")
        
        # Initialize LangChain OpenAI embeddings
        self.embeddings = OpenAIEmbeddings(
            model=self.model,
            api_key=self.api_key,
            chunk_size=self.batch_size
        )
        
        logger.info(f"Initialized embedding client with model: {self.model}")
    
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text
        
        Args:
            text: Text to embed
            
        Returns:
            List[float]: Vector embedding (1536 dimensions for text-embedding-3-small)
        """
        try:
            if not text or not text.strip():
                # Return zero vector for empty text
                return [0.0] * 1536
            
            # Use LangChain's async method
            embedding = await self.embeddings.aembed_query(text.strip())
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding for text: {str(e)}")
            # Return zero vector as fallback
            return [0.0] * 1536
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List[List[float]]: List of vector embeddings
        """
        try:
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
            return [[0.0] * 1536 for _ in texts]
    
    async def embed_requirement(self, requirement: Dict[str, Any]) -> Dict[str, List[float]]:
        """
        Generate embeddings for a requirement
        
        Args:
            requirement: Requirement data with title and description
            
        Returns:
            Dict[str, List[float]]: Dictionary with title_embedding, description_embedding, combined_embedding
        """
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
        return {
            "model": self.model,
            "dimensions": 1536,  # text-embedding-3-small dimensions
            "batch_size": self.batch_size,
            "provider": "OpenAI"
        }

def create_embedding_client(model: str = "text-embedding-3-small", 
                          api_key: Optional[str] = None,
                          batch_size: int = 100) -> DocurecoEmbeddingClient:
    """
    Factory function to create embedding client
    
    Args:
        model: Embedding model name
        api_key: Optional API key
        batch_size: Batch size for processing
        
    Returns:
        DocurecoEmbeddingClient: Configured embedding client
    """
    return DocurecoEmbeddingClient(model, api_key, batch_size)

# Export main classes
__all__ = ["DocurecoEmbeddingClient", "create_embedding_client"] 