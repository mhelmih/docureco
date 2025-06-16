"""
Free Embedding Client for Docureco Agent
Uses open source models instead of paid APIs
"""

import os
import logging
from typing import List, Dict, Any, Optional
import asyncio
from pathlib import Path

logger = logging.getLogger(__name__)

class FreeEmbeddingClient:
    """
    Free embedding client using Sentence Transformers
    No API keys required - runs locally
    """
    
    def __init__(self, 
                 model_name: str = "all-MiniLM-L6-v2",
                 cache_folder: Optional[str] = None,
                 device: str = "cpu"):
        """
        Initialize free embedding client
        
        Args:
            model_name: Sentence transformer model name
            cache_folder: Local cache folder for models
            device: Device to run on ('cpu' or 'cuda')
        """
        self.model_name = model_name
        self.device = device
        self.cache_folder = cache_folder or str(Path.home() / ".cache" / "sentence_transformers")
        
        # Initialize model lazily
        self._model = None
        self._embedding_dim = None
        
        logger.info(f"Initialized free embedding client with model: {self.model_name}")
    
    def _get_model(self):
        """Lazy load the sentence transformer model"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                
                logger.info(f"Loading sentence transformer model: {self.model_name}")
                self._model = SentenceTransformer(
                    self.model_name,
                    cache_folder=self.cache_folder,
                    device=self.device
                )
                
                # Get embedding dimension
                test_embedding = self._model.encode("test", convert_to_tensor=False)
                self._embedding_dim = len(test_embedding)
                
                logger.info(f"Model loaded successfully. Embedding dimension: {self._embedding_dim}")
                
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
            except Exception as e:
                logger.error(f"Failed to load model {self.model_name}: {str(e)}")
                raise
        
        return self._model
    
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text
        
        Args:
            text: Text to embed
            
        Returns:
            List[float]: Vector embedding
        """
        try:
            if not text or not text.strip():
                # Return zero vector for empty text
                dim = self._embedding_dim or 384  # Default for all-MiniLM-L6-v2
                return [0.0] * dim
            
            model = self._get_model()
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None, 
                lambda: model.encode(text.strip(), convert_to_tensor=False)
            )
            
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Error generating embedding for text: {str(e)}")
            # Return zero vector as fallback
            dim = self._embedding_dim or 384
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
            if not texts:
                return []
            
            # Filter out empty texts but keep track of positions
            filtered_texts = []
            text_indices = []
            
            for i, text in enumerate(texts):
                if text and text.strip():
                    filtered_texts.append(text.strip())
                    text_indices.append(i)
            
            if not filtered_texts:
                # All texts are empty
                dim = self._embedding_dim or 384
                return [[0.0] * dim for _ in texts]
            
            model = self._get_model()
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                lambda: model.encode(filtered_texts, convert_to_tensor=False, batch_size=32)
            )
            
            # Reconstruct full list with zero vectors for empty texts
            result = []
            embedding_idx = 0
            dim = len(embeddings[0]) if len(embeddings) > 0 else (self._embedding_dim or 384)
            
            for i, text in enumerate(texts):
                if i in text_indices:
                    result.append(embeddings[embedding_idx].tolist())
                    embedding_idx += 1
                else:
                    result.append([0.0] * dim)
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating embeddings for texts: {str(e)}")
            # Return zero vectors as fallback
            dim = self._embedding_dim or 384
            return [[0.0] * dim for _ in texts]
    
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
            List[float]: Combined embedding for the change context
        """
        # Combine all context into a single text
        context_text = f"File: {filename}\nCommit: {commit_message}\nChanges: {patch[:1000]}"  # Limit patch size
        
        return await self.embed_text(context_text)
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the embedding model
        
        Returns:
            Dict[str, Any]: Model information
        """
        return {
            "model_name": self.model_name,
            "embedding_dimension": self._embedding_dim or 384,
            "device": self.device,
            "is_local": True,
            "cost_per_token": 0.0,  # Free!
            "provider": "sentence-transformers"
        }

# Recommended models for different use cases
RECOMMENDED_MODELS = {
    "fast": "all-MiniLM-L6-v2",           # 384 dim, fast, good quality
    "balanced": "all-mpnet-base-v2",       # 768 dim, slower but better quality  
    "multilingual": "paraphrase-multilingual-MiniLM-L12-v2",  # 384 dim, supports many languages
    "code": "microsoft/codebert-base",     # 768 dim, specialized for code
    "large": "all-MiniLM-L12-v2"          # 384 dim, larger model, better quality
}

def create_free_embedding_client(
    model_type: str = "fast",
    custom_model: Optional[str] = None,
    device: str = "cpu"
) -> FreeEmbeddingClient:
    """
    Factory function to create free embedding client
    
    Args:
        model_type: Type of model ("fast", "balanced", "multilingual", "code", "large")
        custom_model: Custom model name (overrides model_type)
        device: Device to run on ("cpu" or "cuda")
        
    Returns:
        FreeEmbeddingClient: Configured embedding client
    """
    if custom_model:
        model_name = custom_model
    else:
        model_name = RECOMMENDED_MODELS.get(model_type, RECOMMENDED_MODELS["fast"])
    
    logger.info(f"Creating free embedding client with model: {model_name}")
    
    return FreeEmbeddingClient(
        model_name=model_name,
        device=device
    )

__all__ = ["FreeEmbeddingClient", "create_free_embedding_client", "RECOMMENDED_MODELS"] 