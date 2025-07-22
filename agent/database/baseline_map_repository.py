"""
Repository pattern for baseline map operations
Provides high-level interface for traceability map management
"""

import logging
from typing import Dict, Any, List, Optional

from .supabase_client import SupabaseClient, create_supabase_client
from ..models.docureco_models import BaselineMapModel, TraceabilityLinkModel
from ..models.docureco_models import RequirementModel, DesignElementModel, CodeComponentModel

logger = logging.getLogger(__name__)

class BaselineMapRepository:
    """
    Repository for baseline map operations
    Provides high-level interface for traceability map CRUD operations
    """
    
    def __init__(self, supabase_client: Optional[SupabaseClient] = None):
        """
        Initialize repository
        
        Args:
            supabase_client: Optional Supabase client, creates default if not provided
        """
        self.client = supabase_client or create_supabase_client()
        logger.info("Initialized BaselineMapRepository")
    
    async def get_baseline_map(self, repository: str, branch: str = "main") -> Optional[BaselineMapModel]:
        """
        Get baseline map for repository
        
        Args:
            repository: Repository name (owner/repo)
            branch: Branch name
            
        Returns:
            Optional[BaselineMapModel]: Baseline map or None if not found
        """
        try:
            map_data = await self.client.get_baseline_map(repository, branch)
            if not map_data:
                return None
            
            # Convert to Pydantic model
            baseline_map = BaselineMapModel(
                repository=map_data["repository"],
                branch=map_data["branch"],
                requirements=[
                    RequirementModel(**req) for req in map_data.get("requirements", [])
                ],
                design_elements=[
                    DesignElementModel(**elem) for elem in map_data.get("design_elements", [])
                ],
                code_components=[
                    CodeComponentModel(**comp) for comp in map_data.get("code_components", [])
                ],
                traceability_links=[
                    TraceabilityLinkModel(**link) for link in map_data.get("traceability_links", [])
                ],
                created_at=map_data["created_at"],
                updated_at=map_data["updated_at"]
            )
            
            return baseline_map
            
        except Exception as e:
            logger.error(f"Error getting baseline map: {str(e)}")
            return None
    
    async def save_baseline_map(self, baseline_map: BaselineMapModel) -> bool:
        """
        Save baseline map
        
        Args:
            baseline_map: Baseline map to save
            
        Returns:
            bool: True if successful
        """
        try:
            # Convert Pydantic model to dict
            map_data = {
                "repository": baseline_map.repository,
                "branch": baseline_map.branch,
                "requirements": [req.dict() for req in baseline_map.requirements],
                "design_elements": [elem.dict() for elem in baseline_map.design_elements],
                "code_components": [comp.dict() for comp in baseline_map.code_components],
                "traceability_links": [link.dict() for link in baseline_map.traceability_links]
            }
            
            return await self.client.save_baseline_map(map_data)
            
        except Exception as e:
            logger.error(f"Error saving baseline map: {str(e)}")
            return False
    
    async def find_affected_elements(
        self, 
        code_component_path: str, 
        repository: str,
        branch: str = "main"
    ) -> List[Dict[str, Any]]:
        """
        Find elements affected by changes to a code component
        
        Args:
            code_component_path: Path of the changed code component
            repository: Repository name
            branch: Branch name
            
        Returns:
            List[Dict[str, Any]]: List of affected elements with traceability info
        """
        try:
            # Find code component ID
            baseline_map = await self.get_baseline_map(repository, branch)
            if not baseline_map:
                return []
            
            # Find matching code component
            code_component_id = None
            for component in baseline_map.code_components:
                if component.path == code_component_path:
                    code_component_id = component.id
                    break
            
            if not code_component_id:
                logger.debug(f"No code component found for path: {code_component_path}")
                return []
            
            # Find all links where this component is the source
            affected_elements = []
            for link in baseline_map.traceability_links:
                if link.source_type == "CodeComponent" and link.source_id == code_component_id:
                    # Find target element details
                    target_element = self._find_element_by_id(
                        baseline_map, link.target_type, link.target_id
                    )
                    if target_element:
                        affected_elements.append({
                            "element_type": link.target_type,
                            "element_id": link.target_id,
                            "element_details": target_element,
                            "relationship": link.relationship_type,
                            "trace_path": "Direct"
                        })
            
            # Find indirect links (2-hop)
            for direct_link in baseline_map.traceability_links:
                if direct_link.source_type == "CodeComponent" and direct_link.source_id == code_component_id:
                    # Find links from this target
                    for indirect_link in baseline_map.traceability_links:
                        if (indirect_link.source_type == direct_link.target_type and 
                            indirect_link.source_id == direct_link.target_id):
                            target_element = self._find_element_by_id(
                                baseline_map, indirect_link.target_type, indirect_link.target_id
                            )
                            if target_element:
                                affected_elements.append({
                                    "element_type": indirect_link.target_type,
                                    "element_id": indirect_link.target_id,
                                    "element_details": target_element,
                                    "relationship": f"{direct_link.relationship_type} -> {indirect_link.relationship_type}",
                                    "trace_path": "Indirect"
                                })
            
            logger.debug(f"Found {len(affected_elements)} affected elements for {code_component_path}")
            return affected_elements
            
        except Exception as e:
            logger.error(f"Error finding affected elements: {str(e)}")
            return []
    
    def _find_element_by_id(self, baseline_map: BaselineMapModel, element_type: str, element_id: str) -> Optional[Dict[str, Any]]:
        """Find element by type and ID in baseline map"""
        if element_type == "Requirement":
            for req in baseline_map.requirements:
                if req.id == element_id:
                    return req.dict()
        elif element_type == "DesignElement":
            for elem in baseline_map.design_elements:
                if elem.id == element_id:
                    return elem.dict()
        elif element_type == "CodeComponent":
            for comp in baseline_map.code_components:
                if comp.id == element_id:
                    return comp.dict()
        
        return None
    
    async def update_traceability_link(
        self, 
        repository: str, 
        link: TraceabilityLinkModel, 
        branch: str = "main"
    ) -> bool:
        """
        Update or add a traceability link
        
        Args:
            repository: Repository name
            link: Traceability link to update/add
            branch: Branch name
            
        Returns:
            bool: True if successful
        """
        try:
            baseline_map = await self.get_baseline_map(repository, branch)
            if not baseline_map:
                logger.error(f"No baseline map found for {repository}:{branch}")
                return False
            
            # Update or add link
            updated = False
            for i, existing_link in enumerate(baseline_map.traceability_links):
                if (existing_link.source_type == link.source_type and 
                    existing_link.source_id == link.source_id and
                    existing_link.target_type == link.target_type and
                    existing_link.target_id == link.target_id):
                    baseline_map.traceability_links[i] = link
                    updated = True
                    break
            
            if not updated:
                baseline_map.traceability_links.append(link)
            
            # Save updated map
            return await self.save_baseline_map(baseline_map)
            
        except Exception as e:
            logger.error(f"Error updating traceability link: {str(e)}")
            return False
    
    async def check_repository_exists(self, repository: str, branch: str = "main") -> bool:
        """
        Check if baseline map exists for repository
        
        Args:
            repository: Repository name
            branch: Branch name
            
        Returns:
            bool: True if exists
        """
        baseline_map = await self.get_baseline_map(repository, branch)
        return baseline_map is not None
    
    async def get_repository_statistics(self, repository: str, branch: str = "main") -> Dict[str, int]:
        """
        Get statistics for repository baseline map
        
        Args:
            repository: Repository name
            branch: Branch name
            
        Returns:
            Dict[str, int]: Statistics
        """
        try:
            baseline_map = await self.get_baseline_map(repository, branch)
            if not baseline_map:
                return {
                    "requirements_count": 0,
                    "design_elements_count": 0,
                    "code_components_count": 0,
                    "traceability_links_count": 0
                }
            
            return {
                "requirements_count": len(baseline_map.requirements),
                "design_elements_count": len(baseline_map.design_elements),
                "code_components_count": len(baseline_map.code_components),
                "traceability_links_count": len(baseline_map.traceability_links)
            }
            
        except Exception as e:
            logger.error(f"Error getting repository statistics: {str(e)}")
            return {}

# Export main class
__all__ = ["BaselineMapRepository"] 