"""
Vector Search Repository for Docureco Agent
Handles semantic search using vector embeddings
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import asyncio

from .supabase_client import SupabaseClient, create_supabase_client
from ..llm.embedding_client import DocurecoEmbeddingClient, create_embedding_client

logger = logging.getLogger(__name__)

class VectorSearchRepository:
    """
    Repository for vector-based semantic search operations
    Provides semantic similarity search for requirements, design elements, and code components
    """
    
    def __init__(self, 
                 supabase_client: Optional[SupabaseClient] = None,
                 embedding_client: Optional[DocurecoEmbeddingClient] = None):
        """
        Initialize vector search repository
        
        Args:
            supabase_client: Optional Supabase client
            embedding_client: Optional embedding client
        """
        self.supabase_client = supabase_client or create_supabase_client()
        self.embedding_client = embedding_client or create_embedding_client()
        
        logger.info("Initialized VectorSearchRepository")
    
    async def find_similar_requirements_by_text(self,
                                               query_text: str,
                                               repository: str,
                                               branch: str = "main",
                                               similarity_threshold: float = 0.7,
                                               max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Find requirements similar to query text using vector similarity
        
        Args:
            query_text: Text to search for
            repository: Repository name
            branch: Branch name
            similarity_threshold: Minimum similarity score (0.0 to 1.0)
            max_results: Maximum number of results
            
        Returns:
            List[Dict[str, Any]]: List of similar requirements with similarity scores
        """
        try:
            # Generate embedding for query text
            query_embedding = await self.embedding_client.embed_text(query_text)
            
            # Get baseline map ID
            baseline_map = await self.supabase_client.get_baseline_map(repository, branch)
            if not baseline_map:
                logger.warning(f"No baseline map found for {repository}:{branch}")
                return []
            
            baseline_map_id = baseline_map["id"]
            
            # Execute vector similarity search using SQL function
            response = self.supabase_client.client.rpc(
                "find_similar_requirements",
                {
                    "query_embedding": query_embedding,
                    "similarity_threshold": similarity_threshold,
                    "max_results": max_results,
                    "target_baseline_map_id": baseline_map_id
                }
            ).execute()
            
            results = response.data or []
            logger.info(f"Found {len(results)} similar requirements for query: '{query_text[:50]}...'")
            
            return results
            
        except Exception as e:
            logger.error(f"Error finding similar requirements: {str(e)}")
            return []
    
    async def find_similar_design_elements_by_text(self,
                                                  query_text: str,
                                                  repository: str,
                                                  branch: str = "main",
                                                  similarity_threshold: float = 0.7,
                                                  max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Find design elements similar to query text using vector similarity
        
        Args:
            query_text: Text to search for
            repository: Repository name
            branch: Branch name
            similarity_threshold: Minimum similarity score (0.0 to 1.0)
            max_results: Maximum number of results
            
        Returns:
            List[Dict[str, Any]]: List of similar design elements with similarity scores
        """
        try:
            # Generate embedding for query text
            query_embedding = await self.embedding_client.embed_text(query_text)
            
            # Get baseline map ID
            baseline_map = await self.supabase_client.get_baseline_map(repository, branch)
            if not baseline_map:
                logger.warning(f"No baseline map found for {repository}:{branch}")
                return []
            
            baseline_map_id = baseline_map["id"]
            
            # Execute vector similarity search using SQL function
            response = self.supabase_client.client.rpc(
                "find_similar_design_elements",
                {
                    "query_embedding": query_embedding,
                    "similarity_threshold": similarity_threshold,
                    "max_results": max_results,
                    "target_baseline_map_id": baseline_map_id
                }
            ).execute()
            
            results = response.data or []
            logger.info(f"Found {len(results)} similar design elements for query: '{query_text[:50]}...'")
            
            return results
            
        except Exception as e:
            logger.error(f"Error finding similar design elements: {str(e)}")
            return []
    
    async def find_similar_code_components_by_text(self,
                                                  query_text: str,
                                                  repository: str,
                                                  branch: str = "main",
                                                  similarity_threshold: float = 0.7,
                                                  max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Find code components similar to query text using vector similarity
        
        Args:
            query_text: Text to search for
            repository: Repository name
            branch: Branch name
            similarity_threshold: Minimum similarity score (0.0 to 1.0)
            max_results: Maximum number of results
            
        Returns:
            List[Dict[str, Any]]: List of similar code components with similarity scores
        """
        try:
            # Generate embedding for query text
            query_embedding = await self.embedding_client.embed_text(query_text)
            
            # Get baseline map ID
            baseline_map = await self.supabase_client.get_baseline_map(repository, branch)
            if not baseline_map:
                logger.warning(f"No baseline map found for {repository}:{branch}")
                return []
            
            baseline_map_id = baseline_map["id"]
            
            # Execute vector similarity search using SQL function
            response = self.supabase_client.client.rpc(
                "find_similar_code_components",
                {
                    "query_embedding": query_embedding,
                    "similarity_threshold": similarity_threshold,
                    "max_results": max_results,
                    "target_baseline_map_id": baseline_map_id
                }
            ).execute()
            
            results = response.data or []
            logger.info(f"Found {len(results)} similar code components for query: '{query_text[:50]}...'")
            
            return results
            
        except Exception as e:
            logger.error(f"Error finding similar code components: {str(e)}")
            return []
    
    async def find_related_elements_by_code_change(self,
                                                   filename: str,
                                                   patch: str,
                                                   commit_message: str,
                                                   repository: str,
                                                   branch: str = "main",
                                                   similarity_threshold: float = 0.6,
                                                   max_results_per_type: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """
        Find related documentation elements based on code change context
        
        Args:
            filename: Changed file name
            patch: Code diff/patch
            commit_message: Commit message
            repository: Repository name
            branch: Branch name
            similarity_threshold: Minimum similarity score
            max_results_per_type: Maximum results per element type
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: Dictionary with 'requirements', 'design_elements', 'code_components'
        """
        try:
            # Generate embedding for code change context
            change_embedding = await self.embedding_client.embed_code_change_context(
                filename, patch, commit_message
            )
            
            # Get baseline map ID
            baseline_map = await self.supabase_client.get_baseline_map(repository, branch)
            if not baseline_map:
                logger.warning(f"No baseline map found for {repository}:{branch}")
                return {"requirements": [], "design_elements": [], "code_components": []}
            
            baseline_map_id = baseline_map["id"]
            
            # Search across all element types in parallel
            tasks = [
                self.supabase_client.client.rpc(
                    "find_similar_requirements",
                    {
                        "query_embedding": change_embedding,
                        "similarity_threshold": similarity_threshold,
                        "max_results": max_results_per_type,
                        "target_baseline_map_id": baseline_map_id
                    }
                ).execute(),
                
                self.supabase_client.client.rpc(
                    "find_similar_design_elements",
                    {
                        "query_embedding": change_embedding,
                        "similarity_threshold": similarity_threshold,
                        "max_results": max_results_per_type,
                        "target_baseline_map_id": baseline_map_id
                    }
                ).execute(),
                
                self.supabase_client.client.rpc(
                    "find_similar_code_components",
                    {
                        "query_embedding": change_embedding,
                        "similarity_threshold": similarity_threshold,
                        "max_results": max_results_per_type,
                        "target_baseline_map_id": baseline_map_id
                    }
                ).execute()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            requirements = results[0].data if not isinstance(results[0], Exception) else []
            design_elements = results[1].data if not isinstance(results[1], Exception) else []
            code_components = results[2].data if not isinstance(results[2], Exception) else []
            
            logger.info(f"Found {len(requirements)} requirements, {len(design_elements)} design elements, "
                       f"{len(code_components)} code components related to {filename}")
            
            return {
                "requirements": requirements or [],
                "design_elements": design_elements or [],
                "code_components": code_components or []
            }
            
        except Exception as e:
            logger.error(f"Error finding related elements by code change: {str(e)}")
            return {"requirements": [], "design_elements": [], "code_components": []}
    
    async def generate_and_store_embeddings(self,
                                          baseline_map: Dict[str, Any]) -> bool:
        """
        Generate and store embeddings for all elements in a baseline map
        
        Args:
            baseline_map: Complete baseline map data
            
        Returns:
            bool: True if successful
        """
        try:
            logger.info("Starting embedding generation for baseline map")
            
            # Get baseline map ID from database
            db_baseline_map = await self.supabase_client.get_baseline_map(
                baseline_map["repository"], 
                baseline_map.get("branch", "main")
            )
            
            if not db_baseline_map:
                logger.error("Baseline map not found in database")
                return False
            
            baseline_map_id = db_baseline_map["id"]
            
            # Generate embeddings for requirements
            requirements = baseline_map.get("requirements", [])
            if requirements:
                await self._update_requirement_embeddings(baseline_map_id, requirements)
            
            # Generate embeddings for design elements
            design_elements = baseline_map.get("design_elements", [])
            if design_elements:
                await self._update_design_element_embeddings(baseline_map_id, design_elements)
            
            # Generate embeddings for code components
            code_components = baseline_map.get("code_components", [])
            if code_components:
                await self._update_code_component_embeddings(baseline_map_id, code_components)
            
            logger.info("Successfully generated and stored all embeddings")
            return True
            
        except Exception as e:
            logger.error(f"Error generating and storing embeddings: {str(e)}")
            return False
    
    async def _update_requirement_embeddings(self, baseline_map_id: str, requirements: List[Dict[str, Any]]) -> None:
        """Update embeddings for requirements"""
        for req in requirements:
            try:
                embeddings = await self.embedding_client.embed_requirement(req)
                
                self.supabase_client.client.table("requirements").update({
                    "title_embedding": embeddings["title_embedding"],
                    "description_embedding": embeddings["description_embedding"],
                    "combined_embedding": embeddings["combined_embedding"]
                }).eq("baseline_map_id", baseline_map_id).eq("id", req["id"]).execute()
                
            except Exception as e:
                logger.error(f"Error updating embeddings for requirement {req.get('id')}: {str(e)}")
    
    async def _update_design_element_embeddings(self, baseline_map_id: str, design_elements: List[Dict[str, Any]]) -> None:
        """Update embeddings for design elements"""
        for elem in design_elements:
            try:
                embeddings = await self.embedding_client.embed_design_element(elem)
                
                self.supabase_client.client.table("design_elements").update({
                    "name_embedding": embeddings["name_embedding"],
                    "description_embedding": embeddings["description_embedding"],
                    "combined_embedding": embeddings["combined_embedding"]
                }).eq("baseline_map_id", baseline_map_id).eq("id", elem["id"]).execute()
                
            except Exception as e:
                logger.error(f"Error updating embeddings for design element {elem.get('id')}: {str(e)}")
    
    async def _update_code_component_embeddings(self, baseline_map_id: str, code_components: List[Dict[str, Any]]) -> None:
        """Update embeddings for code components"""
        for comp in code_components:
            try:
                embeddings = await self.embedding_client.embed_code_component(comp)
                
                update_data = {"path_embedding": embeddings["path_embedding"]}
                if "name_embedding" in embeddings:
                    update_data["name_embedding"] = embeddings["name_embedding"]
                
                self.supabase_client.client.table("code_components").update(
                    update_data
                ).eq("baseline_map_id", baseline_map_id).eq("id", comp["id"]).execute()
                
            except Exception as e:
                logger.error(f"Error updating embeddings for code component {comp.get('id')}: {str(e)}")

def create_vector_search_repository(supabase_client: Optional[SupabaseClient] = None,
                                   embedding_client: Optional[DocurecoEmbeddingClient] = None) -> VectorSearchRepository:
    """
    Factory function to create vector search repository
    
    Args:
        supabase_client: Optional Supabase client
        embedding_client: Optional embedding client
        
    Returns:
        VectorSearchRepository: Configured repository
    """
    return VectorSearchRepository(supabase_client, embedding_client)

# Export main classes
__all__ = ["VectorSearchRepository", "create_vector_search_repository"] 