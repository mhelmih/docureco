"""
Initial Baseline Map Creator for Docureco Agent
Creates initial traceability maps by scanning repository documentation and code
"""

import asyncio
import logging
import os
import re
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
from dataclasses import dataclass

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..llm.llm_client import DocurecoLLMClient, create_llm_client
from ..llm.embedding_client import DocurecoEmbeddingClient, create_embedding_client
from ..database import BaselineMapRepository, VectorSearchRepository
from ..models.docureco_models import (
    BaselineMapModel, RequirementModel, DesignElementModel, 
    CodeComponentModel, TraceabilityLinkModel
)

logger = logging.getLogger(__name__)

@dataclass
class BaselineMapCreatorState:
    """State for baseline map creation workflow"""
    repository: str
    branch: str
    
    # Repository content
    srs_content: Dict[str, str] = None
    sdd_content: Dict[str, str] = None
    code_files: List[Dict[str, Any]] = None
    
    # Extracted elements
    requirements: List[RequirementModel] = None
    design_elements: List[DesignElementModel] = None
    code_components: List[CodeComponentModel] = None
    traceability_links: List[TraceabilityLinkModel] = None
    
    # Workflow metadata
    current_step: str = "initializing"
    errors: List[str] = None
    processing_stats: Dict[str, int] = None

class BaselineMapCreatorWorkflow:
    """
    LangGraph workflow for creating initial baseline traceability maps
    Implements the Initial Baseline Map Creator component
    """
    
    def __init__(self, 
                 llm_client: Optional[DocurecoLLMClient] = None,
                 embedding_client: Optional[DocurecoEmbeddingClient] = None,
                 baseline_map_repo: Optional[BaselineMapRepository] = None,
                 vector_search_repo: Optional[VectorSearchRepository] = None):
        """
        Initialize baseline map creator workflow
        
        Args:
            llm_client: Optional LLM client
            embedding_client: Optional embedding client
            baseline_map_repo: Optional baseline map repository
            vector_search_repo: Optional vector search repository
        """
        self.llm_client = llm_client or create_llm_client()
        self.embedding_client = embedding_client or create_embedding_client()
        self.baseline_map_repo = baseline_map_repo or BaselineMapRepository()
        self.vector_search_repo = vector_search_repo or VectorSearchRepository()
        
        self.workflow = self._build_workflow()
        self.memory = MemorySaver()
        
        logger.info("Initialized BaselineMapCreatorWorkflow")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(BaselineMapCreatorState)
        
        # Add nodes for each major process step
        workflow.add_node("scan_repository", self._scan_repository)
        workflow.add_node("extract_requirements", self._extract_requirements)
        workflow.add_node("extract_design_elements", self._extract_design_elements)
        workflow.add_node("extract_code_components", self._extract_code_components)
        workflow.add_node("create_traceability_links", self._create_traceability_links)
        workflow.add_node("generate_embeddings", self._generate_embeddings)
        workflow.add_node("save_baseline_map", self._save_baseline_map)
        
        # Define workflow edges
        workflow.set_entry_point("scan_repository")
        workflow.add_edge("scan_repository", "extract_requirements")
        workflow.add_edge("extract_requirements", "extract_design_elements")
        workflow.add_edge("extract_design_elements", "extract_code_components")
        workflow.add_edge("extract_code_components", "create_traceability_links")
        workflow.add_edge("create_traceability_links", "generate_embeddings")
        workflow.add_edge("generate_embeddings", "save_baseline_map")
        workflow.add_edge("save_baseline_map", END)
        
        return workflow
    
    async def execute(self, repository: str, branch: str = "main") -> BaselineMapCreatorState:
        """
        Execute baseline map creation workflow
        
        Args:
            repository: Repository name (owner/repo)
            branch: Branch name
            
        Returns:
            BaselineMapCreatorState: Final workflow state
        """
        # Initialize state
        initial_state = BaselineMapCreatorState(
            repository=repository,
            branch=branch,
            requirements=[],
            design_elements=[],
            code_components=[],
            traceability_links=[],
            errors=[],
            processing_stats={}
        )
        
        try:
            # Check if baseline map already exists
            existing_map = await self.baseline_map_repo.get_baseline_map(repository, branch)
            if existing_map:
                logger.warning(f"Baseline map already exists for {repository}:{branch}")
                choice = input("Baseline map exists. Overwrite? (y/N): ").strip().lower()
                if choice != 'y':
                    logger.info("Baseline map creation cancelled")
                    return initial_state
            
            # Compile and run workflow
            app = self.workflow.compile(checkpointer=self.memory)
            config = {"configurable": {"thread_id": f"baseline_{repository.replace('/', '_')}_{branch}"}}
            
            final_state = await app.ainvoke(initial_state, config=config)
            
            logger.info(f"Baseline map creation completed for {repository}:{branch}")
            return final_state
            
        except Exception as e:
            logger.error(f"Baseline map creation failed: {str(e)}")
            initial_state.errors.append(str(e))
            raise
    
    async def _scan_repository(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Scan repository for documentation and code files
        """
        logger.info(f"Scanning repository {state.repository}:{state.branch}")
        state.current_step = "scanning_repository"
        
        try:
            # In a full implementation, this would use GitHub API to fetch files
            # For now, we'll simulate the repository scanning
            
            # Look for SRS files (common patterns)
            srs_patterns = [
                "requirements.md", "srs.md", "software-requirements.md",
                "docs/requirements.md", "docs/srs.md", "documentation/requirements.md"
            ]
            
            # Look for SDD files (common patterns)
            sdd_patterns = [
                "design.md", "sdd.md", "software-design.md", "architecture.md",
                "docs/design.md", "docs/sdd.md", "docs/architecture.md"
            ]
            
            # Look for code files (common patterns)
            code_patterns = ["*.py", "*.java", "*.js", "*.ts", "*.cpp", "*.h"]
            
            # Simulate scanning (in real implementation, would fetch from GitHub)
            state.srs_content = await self._fetch_documentation_files(state.repository, srs_patterns, state.branch)
            state.sdd_content = await self._fetch_documentation_files(state.repository, sdd_patterns, state.branch)
            state.code_files = await self._fetch_code_files(state.repository, code_patterns, state.branch)
            
            logger.info(f"Found {len(state.srs_content)} SRS files, {len(state.sdd_content)} SDD files, {len(state.code_files)} code files")
            
        except Exception as e:
            error_msg = f"Error scanning repository: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _extract_requirements(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Extract requirements from SRS documentation using LLM
        """
        logger.info("Extracting requirements from SRS")
        state.current_step = "extracting_requirements"
        
        try:
            requirements = []
            req_counter = 1
            
            for file_path, content in state.srs_content.items():
                if not content.strip():
                    continue
                
                # Use LLM to extract requirements
                extracted_reqs = await self._llm_extract_requirements(content, file_path)
                
                for req_data in extracted_reqs:
                    requirement = RequirementModel(
                        id=f"REQ-{req_counter:03d}",
                        title=req_data.get("title", f"Requirement {req_counter}"),
                        description=req_data.get("description", ""),
                        type=req_data.get("type", "Functional"),
                        priority=req_data.get("priority", "Medium"),
                        section=req_data.get("section", file_path)
                    )
                    requirements.append(requirement)
                    req_counter += 1
            
            state.requirements = requirements
            state.processing_stats["requirements_count"] = len(requirements)
            logger.info(f"Extracted {len(requirements)} requirements")
            
        except Exception as e:
            error_msg = f"Error extracting requirements: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _extract_design_elements(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Extract design elements from SDD documentation using LLM
        """
        logger.info("Extracting design elements from SDD")
        state.current_step = "extracting_design_elements"
        
        try:
            design_elements = []
            elem_counter = 1
            
            for file_path, content in state.sdd_content.items():
                if not content.strip():
                    continue
                
                # Use LLM to extract design elements
                extracted_elements = await self._llm_extract_design_elements(content, file_path)
                
                for elem_data in extracted_elements:
                    design_element = DesignElementModel(
                        id=f"DE-{elem_counter:03d}",
                        name=elem_data.get("name", f"DesignElement{elem_counter}"),
                        description=elem_data.get("description", ""),
                        type=elem_data.get("type", "Component"),
                        section=elem_data.get("section", file_path)
                    )
                    design_elements.append(design_element)
                    elem_counter += 1
            
            state.design_elements = design_elements
            state.processing_stats["design_elements_count"] = len(design_elements)
            logger.info(f"Extracted {len(design_elements)} design elements")
            
        except Exception as e:
            error_msg = f"Error extracting design elements: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _extract_code_components(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Extract code components from source code
        """
        logger.info("Extracting code components")
        state.current_step = "extracting_code_components"
        
        try:
            code_components = []
            comp_counter = 1
            
            for file_info in state.code_files:
                file_path = file_info.get("path", "")
                content = file_info.get("content", "")
                
                if not content.strip():
                    continue
                
                # Extract components using static analysis + LLM
                extracted_components = await self._extract_code_components_from_file(file_path, content)
                
                for comp_data in extracted_components:
                    code_component = CodeComponentModel(
                        id=f"CC-{comp_counter:03d}",
                        path=file_path,
                        type=comp_data.get("type", "File"),
                        name=comp_data.get("name", Path(file_path).stem)
                    )
                    code_components.append(code_component)
                    comp_counter += 1
            
            state.code_components = code_components
            state.processing_stats["code_components_count"] = len(code_components)
            logger.info(f"Extracted {len(code_components)} code components")
            
        except Exception as e:
            error_msg = f"Error extracting code components: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _create_traceability_links(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Create traceability links between elements using LLM
        """
        logger.info("Creating traceability links")
        state.current_step = "creating_traceability_links"
        
        try:
            links = []
            link_counter = 1
            
            # Create requirement → design element links
            req_to_design_links = await self._create_requirement_design_links(
                state.requirements, state.design_elements
            )
            
            # Create design element → code component links
            design_to_code_links = await self._create_design_code_links(
                state.design_elements, state.code_components
            )
            
            # Combine all links
            all_links = req_to_design_links + design_to_code_links
            
            for link_data in all_links:
                link = TraceabilityLinkModel(
                    id=f"TL-{link_counter:03d}",
                    source_type=link_data["source_type"],
                    source_id=link_data["source_id"],
                    target_type=link_data["target_type"],
                    target_id=link_data["target_id"],
                    relationship_type=link_data["relationship_type"]
                )
                links.append(link)
                link_counter += 1
            
            state.traceability_links = links
            state.processing_stats["traceability_links_count"] = len(links)
            logger.info(f"Created {len(links)} traceability links")
            
        except Exception as e:
            error_msg = f"Error creating traceability links: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _generate_embeddings(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Generate vector embeddings for all elements
        """
        logger.info("Generating vector embeddings")
        state.current_step = "generating_embeddings"
        
        try:
            # Convert to dict format for embedding generation
            baseline_map_data = {
                "repository": state.repository,
                "branch": state.branch,
                "requirements": [req.dict() for req in state.requirements],
                "design_elements": [elem.dict() for elem in state.design_elements],
                "code_components": [comp.dict() for comp in state.code_components],
                "traceability_links": [link.dict() for link in state.traceability_links]
            }
            
            # Generate and store embeddings
            success = await self.vector_search_repo.generate_and_store_embeddings(baseline_map_data)
            
            if success:
                logger.info("Successfully generated vector embeddings")
            else:
                logger.warning("Failed to generate some embeddings")
            
        except Exception as e:
            error_msg = f"Error generating embeddings: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _save_baseline_map(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Save baseline map to database
        """
        logger.info("Saving baseline map to database")
        state.current_step = "saving_baseline_map"
        
        try:
            # Create baseline map model
            baseline_map = BaselineMapModel(
                repository=state.repository,
                branch=state.branch,
                requirements=state.requirements,
                design_elements=state.design_elements,
                code_components=state.code_components,
                traceability_links=state.traceability_links
            )
            
            # Save to database
            success = await self.baseline_map_repo.save_baseline_map(baseline_map)
            
            if success:
                logger.info(f"Successfully saved baseline map for {state.repository}:{state.branch}")
                state.current_step = "completed"
            else:
                error_msg = "Failed to save baseline map to database"
                logger.error(error_msg)
                state.errors.append(error_msg)
            
        except Exception as e:
            error_msg = f"Error saving baseline map: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    # Helper methods (would be implemented with actual file fetching and LLM calls)
    async def _fetch_documentation_files(self, repository: str, patterns: List[str], branch: str) -> Dict[str, str]:
        """Fetch documentation files from repository"""
        # Placeholder - would implement GitHub API calls
        return {
            "docs/requirements.md": "# Requirements\n\n## FR-001: User Authentication\nSystem must authenticate users...",
            "docs/srs.md": "# Software Requirements Specification\n\n..."
        }
    
    async def _fetch_code_files(self, repository: str, patterns: List[str], branch: str) -> List[Dict[str, Any]]:
        """Fetch code files from repository"""
        # Placeholder - would implement GitHub API calls
        return [
            {"path": "src/auth/AuthService.py", "content": "class AuthService:\n    def authenticate(self, user):\n        pass"},
            {"path": "src/main.py", "content": "from auth import AuthService\n\ndef main():\n    pass"}
        ]
    
    async def _llm_extract_requirements(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract requirements using LLM"""
        # Placeholder - would implement LLM extraction
        return [
            {
                "title": "User Authentication",
                "description": "System must provide secure user authentication",
                "type": "Functional",
                "priority": "High",
                "section": "3.1.1"
            }
        ]
    
    async def _llm_extract_design_elements(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract design elements using LLM"""
        # Placeholder - would implement LLM extraction
        return [
            {
                "name": "AuthService",
                "description": "Authentication service component",
                "type": "Service",
                "section": "4.2.1"
            }
        ]
    
    async def _extract_code_components_from_file(self, file_path: str, content: str) -> List[Dict[str, Any]]:
        """Extract code components from file"""
        # Placeholder - would implement static analysis + LLM
        return [
            {
                "name": "AuthService",
                "type": "Class"
            }
        ]
    
    async def _create_requirement_design_links(self, requirements: List[RequirementModel], design_elements: List[DesignElementModel]) -> List[Dict[str, Any]]:
        """Create links between requirements and design elements"""
        # Placeholder - would use vector similarity + LLM
        return [
            {
                "source_type": "Requirement",
                "source_id": "REQ-001",
                "target_type": "DesignElement",
                "target_id": "DE-001",
                "relationship_type": "implements"
            }
        ]
    
    async def _create_design_code_links(self, design_elements: List[DesignElementModel], code_components: List[CodeComponentModel]) -> List[Dict[str, Any]]:
        """Create links between design elements and code components"""
        # Placeholder - would use vector similarity + LLM
        return [
            {
                "source_type": "DesignElement",
                "source_id": "DE-001",
                "target_type": "CodeComponent",
                "target_id": "CC-001",
                "relationship_type": "realizes"
            }
        ]

# Factory function
def create_baseline_map_creator(llm_client: Optional[DocurecoLLMClient] = None,
                               embedding_client: Optional[DocurecoEmbeddingClient] = None) -> BaselineMapCreatorWorkflow:
    """
    Factory function to create baseline map creator workflow
    
    Args:
        llm_client: Optional LLM client
        embedding_client: Optional embedding client
        
    Returns:
        BaselineMapCreatorWorkflow: Configured workflow
    """
    return BaselineMapCreatorWorkflow(llm_client, embedding_client)

# Export main classes
__all__ = ["BaselineMapCreatorWorkflow", "BaselineMapCreatorState", "create_baseline_map_creator"] 