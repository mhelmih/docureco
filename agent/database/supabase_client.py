"""
Supabase client for Docureco Agent
Handles database connections and operations for traceability map storage
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
import postgrest

logger = logging.getLogger(__name__)

class SupabaseClient:
    """
    Supabase client wrapper for Docureco operations
    Handles traceability map storage and retrieval
    """
    
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        """
        Initialize Supabase client
        
        Args:
            url: Supabase project URL
            key: Supabase service role key
        """
        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables are required")
        
        # Configure client options for better performance
        options = ClientOptions(
            postgrest_client_timeout=30,
            storage_client_timeout=30
        )
        
        self.client: Client = create_client(self.url, self.key, options)
        self._test_connection()
        
        logger.info("Initialized Supabase client successfully")
    
    def _test_connection(self) -> None:
        """Test database connection"""
        try:
            # Simple query to test connection using baseline_maps table
            response = self.client.table("baseline_maps").select("id").limit(1).execute()
            logger.debug("Database connection test successful")
        except Exception as e:
            logger.warning(f"Database connection test failed: {str(e)}")
            # Don't raise here - let it fail on actual operations
    
    async def get_baseline_map(self, repository: str, branch: str = "main") -> Optional[Dict[str, Any]]:
        """
        Retrieve baseline traceability map for repository
        
        Args:
            repository: Repository full name (owner/repo)
            branch: Branch name
            
        Returns:
            Optional[Dict[str, Any]]: Baseline map data or None if not found
        """
        try:
            # Get baseline map record
            response = self.client.table("baseline_maps").select("""
                id, repository, branch, created_at, updated_at,
                requirements (id, title, description, type, priority, section),
                design_elements (id, name, description, type, section),
                code_components (id, path, type, name),
                traceability_links (id, source_type, source_id, target_type, target_id, relationship_type)
            """).eq("repository", repository).eq("branch", branch).order("updated_at", desc=True).limit(1).execute()
            
            if not response.data:
                logger.info(f"No baseline map found for {repository}:{branch}")
                return None
            
            baseline_map = response.data[0]
            logger.info(f"Retrieved baseline map for {repository}:{branch} (updated: {baseline_map['updated_at']})")
            
            return {
                "id": baseline_map["id"],
                "repository": baseline_map["repository"],
                "branch": baseline_map["branch"],
                "requirements": baseline_map.get("requirements", []),
                "design_elements": baseline_map.get("design_elements", []),
                "code_components": baseline_map.get("code_components", []),
                "traceability_links": baseline_map.get("traceability_links", []),
                "created_at": baseline_map["created_at"],
                "updated_at": baseline_map["updated_at"]
            }
            
        except Exception as e:
            logger.error(f"Error retrieving baseline map: {str(e)}")
            return None
    
    async def save_baseline_map(self, baseline_map: Dict[str, Any]) -> bool:
        """
        Save or update baseline traceability map
        
        Args:
            baseline_map: Baseline map data
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            repository = baseline_map["repository"]
            branch = baseline_map.get("branch", "main")
            
            # Check if baseline map already exists
            existing = await self.get_baseline_map(repository, branch)
            
            if existing:
                # Update existing
                baseline_map_id = existing["id"]
                await self._update_baseline_map(baseline_map_id, baseline_map)
            else:
                # Create new
                await self._create_baseline_map(baseline_map)
            
            logger.info(f"Successfully saved baseline map for {repository}:{branch}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving baseline map: {str(e)}")
            return False
    
    async def _create_baseline_map(self, baseline_map: Dict[str, Any]) -> str:
        """Create new baseline map"""
        # Insert baseline map record
        map_response = self.client.table("baseline_maps").insert({
            "repository": baseline_map["repository"],
            "branch": baseline_map.get("branch", "main"),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }).execute()
        
        baseline_map_id = map_response.data[0]["id"]
        
        # Insert related records
        await self._insert_requirements(baseline_map_id, baseline_map.get("requirements", []))
        await self._insert_design_elements(baseline_map_id, baseline_map.get("design_elements", []))
        await self._insert_code_components(baseline_map_id, baseline_map.get("code_components", []))
        await self._insert_traceability_links(baseline_map_id, baseline_map.get("traceability_links", []))
        
        return baseline_map_id
    
    async def _update_baseline_map(self, baseline_map_id: str, baseline_map: Dict[str, Any]) -> None:
        """Update existing baseline map"""
        # Update timestamp
        self.client.table("baseline_maps").update({
            "updated_at": datetime.now().isoformat()
        }).eq("id", baseline_map_id).execute()
        
        # Delete existing related records
        self.client.table("requirements").delete().eq("baseline_map_id", baseline_map_id).execute()
        self.client.table("design_elements").delete().eq("baseline_map_id", baseline_map_id).execute()
        self.client.table("code_components").delete().eq("baseline_map_id", baseline_map_id).execute()
        self.client.table("traceability_links").delete().eq("baseline_map_id", baseline_map_id).execute()
        
        # Insert updated records
        await self._insert_requirements(baseline_map_id, baseline_map.get("requirements", []))
        await self._insert_design_elements(baseline_map_id, baseline_map.get("design_elements", []))
        await self._insert_code_components(baseline_map_id, baseline_map.get("code_components", []))
        await self._insert_traceability_links(baseline_map_id, baseline_map.get("traceability_links", []))
    
    async def _insert_requirements(self, baseline_map_id: str, requirements: List[Dict[str, Any]]) -> None:
        """Insert requirements"""
        if not requirements:
            return
        
        records = []
        for req in requirements:
            records.append({
                "baseline_map_id": baseline_map_id,
                "id": req["id"],
                "title": req["title"],
                "description": req["description"],
                "type": req["type"],
                "priority": req.get("priority", "Medium"),
                "section": req["section"]
            })
        
        self.client.table("requirements").insert(records).execute()
    
    async def _insert_design_elements(self, baseline_map_id: str, design_elements: List[Dict[str, Any]]) -> None:
        """Insert design elements"""
        if not design_elements:
            return
        
        records = []
        for element in design_elements:
            records.append({
                "baseline_map_id": baseline_map_id,
                "id": element["id"],
                "name": element["name"],
                "description": element["description"],
                "type": element["type"],
                "section": element["section"]
            })
        
        self.client.table("design_elements").insert(records).execute()
    
    async def _insert_code_components(self, baseline_map_id: str, code_components: List[Dict[str, Any]]) -> None:
        """Insert code components"""
        if not code_components:
            return
        
        records = []
        for component in code_components:
            records.append({
                "baseline_map_id": baseline_map_id,
                "id": component["id"],
                "path": component["path"],
                "type": component["type"],
                "name": component.get("name")
            })
        
        self.client.table("code_components").insert(records).execute()
    
    async def _insert_traceability_links(self, baseline_map_id: str, links: List[Dict[str, Any]]) -> None:
        """Insert traceability links"""
        if not links:
            return
        
        records = []
        for link in links:
            records.append({
                "baseline_map_id": baseline_map_id,
                "id": link["id"],
                "source_type": link["source_type"],
                "source_id": link["source_id"],
                "target_type": link["target_type"],
                "target_id": link["target_id"],
                "relationship_type": link["relationship_type"]
            })
        
        self.client.table("traceability_links").insert(records).execute()
    
    async def find_traceability_links(
        self, 
        source_type: str, 
        source_id: str, 
        repository: str,
        branch: str = "main"
    ) -> List[Dict[str, Any]]:
        """
        Find traceability links for a specific source
        
        Args:
            source_type: Type of source artifact
            source_id: ID of source artifact
            repository: Repository name
            branch: Branch name
            
        Returns:
            List[Dict[str, Any]]: List of traceability links
        """
        try:
            # Get baseline map ID first
            map_response = self.client.table("baseline_maps").select("id").eq(
                "repository", repository
            ).eq("branch", branch).limit(1).execute()
            
            if not map_response.data:
                return []
            
            baseline_map_id = map_response.data[0]["id"]
            
            # Find links
            response = self.client.table("traceability_links").select("*").eq(
                "baseline_map_id", baseline_map_id
            ).eq("source_type", source_type).eq("source_id", source_id).execute()
            
            return response.data
            
        except Exception as e:
            logger.error(f"Error finding traceability links: {str(e)}")
            return []

def create_supabase_client(url: Optional[str] = None, key: Optional[str] = None) -> SupabaseClient:
    """
    Factory function to create Supabase client
    
    Args:
        url: Optional Supabase URL
        key: Optional service role key
        
    Returns:
        SupabaseClient: Configured client
    """
    return SupabaseClient(url, key)

# Export main classes
__all__ = ["SupabaseClient", "create_supabase_client"] 