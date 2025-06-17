"""
Baseline Map Updater Workflow for Docureco Agent
Updates existing baseline traceability maps based on repository changes
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..llm.llm_client import DocurecoLLMClient, create_llm_client
from ..database import BaselineMapRepository
from ..models.docureco_models import (
    BaselineMapModel, RequirementModel, DesignElementModel, 
    CodeComponentModel, TraceabilityLinkModel
)

logger = logging.getLogger(__name__)

@dataclass
class BaselineMapUpdaterState:
    """State for baseline map updater workflow"""
    repository: str
    branch: str = "main"
    
    # Current baseline map
    current_baseline_map: Optional[BaselineMapModel] = None
    
    # Change analysis
    changed_files: List[str] = field(default_factory=list)
    commit_messages: List[str] = field(default_factory=list)
    pr_changes: List[Dict[str, Any]] = field(default_factory=list)
    
    # Impact analysis results
    impacted_requirements: List[RequirementModel] = field(default_factory=list)
    impacted_design_elements: List[DesignElementModel] = field(default_factory=list)
    impacted_code_components: List[CodeComponentModel] = field(default_factory=list)
    
    # New elements to add
    new_requirements: List[RequirementModel] = field(default_factory=list)
    new_design_elements: List[DesignElementModel] = field(default_factory=list)
    new_code_components: List[CodeComponentModel] = field(default_factory=list)
    new_traceability_links: List[TraceabilityLinkModel] = field(default_factory=list)
    
    # Updated baseline map
    updated_baseline_map: Optional[BaselineMapModel] = None
    
    # Workflow metadata
    current_step: str = ""
    errors: List[str] = field(default_factory=list)
    processing_stats: Dict[str, int] = field(default_factory=dict)

class BaselineMapUpdaterWorkflow:
    """
    Workflow for updating baseline traceability maps based on repository changes
    """
    
    def __init__(self, 
                 llm_client: Optional[DocurecoLLMClient] = None,
                 baseline_map_repo: Optional[BaselineMapRepository] = None):
        """
        Initialize baseline map updater workflow
        
        Args:
            llm_client: Optional LLM client for analysis
            baseline_map_repo: Optional baseline map repository
        """
        self.llm_client = llm_client or create_llm_client()
        self.baseline_map_repo = baseline_map_repo or BaselineMapRepository()
        
        self.workflow = self._build_workflow()
        self.memory = MemorySaver()
        
        logger.info("Initialized BaselineMapUpdaterWorkflow")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(BaselineMapUpdaterState)
        
        # Add nodes for each major process step
        workflow.add_node("load_baseline_map", self._load_baseline_map)
        workflow.add_node("analyze_pr_changes", self._analyze_pr_changes)
        workflow.add_node("identify_impacts", self._identify_impacts)
        workflow.add_node("extract_new_elements", self._extract_new_elements)
        workflow.add_node("update_traceability_links", self._update_traceability_links)
        workflow.add_node("save_updated_map", self._save_updated_map)
        
        # Define workflow edges
        workflow.set_entry_point("load_baseline_map")
        workflow.add_edge("load_baseline_map", "analyze_pr_changes")
        workflow.add_edge("analyze_pr_changes", "identify_impacts")
        workflow.add_edge("identify_impacts", "extract_new_elements")
        workflow.add_edge("extract_new_elements", "update_traceability_links")
        workflow.add_edge("update_traceability_links", "save_updated_map")
        workflow.add_edge("save_updated_map", END)
        
        return workflow
    
    async def execute(self, 
                     repository: str, 
                     branch: str = "main") -> BaselineMapUpdaterState:
        """
        Execute baseline map update workflow
        
        Args:
            repository: Repository name (owner/repo)
            branch: Branch name
            
        Returns:
            BaselineMapUpdaterState: Final workflow state
        """
        # Initialize state
        initial_state = BaselineMapUpdaterState(
            repository=repository,
            branch=branch,
            pr_changes=[],
            changed_files=[],
            commit_messages=[],
            impacted_requirements=[],
            impacted_design_elements=[],
            impacted_code_components=[],
            new_requirements=[],
            new_design_elements=[],
            new_code_components=[],
            new_traceability_links=[],
            errors=[],
            processing_stats={}
        )
        
        try:
            # Compile and run workflow
            app = self.workflow.compile(checkpointer=self.memory)
            config = {"configurable": {"thread_id": f"update_{repository.replace('/', '_')}_{branch}"}}
            
            final_state = await app.ainvoke(initial_state, config=config)
            
            logger.info(f"Baseline map update completed for {repository}:{branch}")
            return final_state
            
        except Exception as e:
            logger.error(f"Baseline map update failed: {str(e)}")
            initial_state.errors.append(str(e))
            raise
    
    async def _load_baseline_map(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """
        Load current baseline map from database
        """
        logger.info(f"Loading baseline map for {state.repository}:{state.branch}")
        state.current_step = "loading_baseline_map"
        
        try:
            # Load baseline map from database
            baseline_map = await self.baseline_map_repo.get_baseline_map(state.repository, state.branch)
            
            if not baseline_map:
                error_msg = f"No baseline map found for {state.repository}:{state.branch}"
                logger.error(error_msg)
                state.errors.append(error_msg)
                return state
            
            state.current_baseline_map = BaselineMapModel(**baseline_map)
            logger.info(f"Loaded baseline map with {len(state.current_baseline_map.requirements)} requirements, "
                       f"{len(state.current_baseline_map.design_elements)} design elements, "
                       f"{len(state.current_baseline_map.code_components)} code components")
            
        except Exception as e:
            error_msg = f"Error loading baseline map: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _analyze_pr_changes(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """
        Analyze PR changes to understand what was modified
        """
        logger.info(f"Analyzing PR changes for {state.repository}:{state.branch}")
        state.current_step = "analyzing_pr_changes"
        
        try:
            # Fetch PR details and changes
            pr_data = await self._fetch_pr_data(state.repository)
            
            if pr_data:
                state.pr_changes = pr_data.get("changes", [])
                state.changed_files = [change.get("filename", "") for change in state.pr_changes]
                state.commit_messages = pr_data.get("commit_messages", [])
                
                logger.info(f"Found {len(state.pr_changes)} file changes across {len(state.changed_files)} files")
            else:
                logger.warning("No PR data found, performing general update")
            
        except Exception as e:
            error_msg = f"Error analyzing PR changes: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _identify_impacts(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """
        Identify which baseline map elements are impacted by the changes
        """
        logger.info("Identifying impacted elements")
        state.current_step = "identifying_impacts"
        
        try:
            impacted_requirements = []
            impacted_design_elements = []
            impacted_code_components = []
            
            # Check for direct file path matches with code components
            for code_component in state.current_baseline_map.code_components:
                if code_component.path in state.changed_files:
                    impacted_code_components.append(code_component)
            
            state.impacted_requirements = impacted_requirements
            state.impacted_design_elements = impacted_design_elements
            state.impacted_code_components = impacted_code_components
            
            logger.info(f"Identified {len(impacted_requirements)} impacted requirements, "
                       f"{len(impacted_design_elements)} impacted design elements, "
                       f"{len(impacted_code_components)} impacted code components")
            
        except Exception as e:
            error_msg = f"Error identifying impacts: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _extract_new_elements(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """
        Extract new requirements, design elements, and code components from changes
        """
        logger.info("Extracting new elements from changes")
        state.current_step = "extracting_new_elements"
        
        try:
            new_requirements = []
            new_design_elements = []
            new_code_components = []
            
            # Check for new documentation files
            doc_files = [f for f in state.changed_files if f.endswith(('.md', '.txt', '.rst', '.doc', '.docx'))]
            
            if doc_files:
                # Extract new elements from documentation changes using LLM
                for file_path in doc_files:
                    change_data = next((c for c in state.pr_changes if c.get("filename") == file_path), None)
                    
                    if change_data and change_data.get("patch"):
                        # Extract added content from patch
                        added_content = self._extract_added_content(change_data.get("patch", ""))
                        
                        if added_content:
                            # Use LLM to identify new requirements/design elements
                            if "requirement" in file_path.lower() or "srs" in file_path.lower():
                                extracted_reqs = await self._llm_extract_requirements_from_content(added_content, file_path)
                                new_requirements.extend(extracted_reqs)
                            
                            if "design" in file_path.lower() or "sdd" in file_path.lower() or "architecture" in file_path.lower():
                                extracted_elements = await self._llm_extract_design_elements_from_content(added_content, file_path)
                                new_design_elements.extend(extracted_elements)
            
            # Check for new code files
            code_files = [f for f in state.changed_files if any(f.endswith(ext) for ext in ['.py', '.java', '.js', '.ts', '.cpp', '.h', '.cs'])]
            
            for file_path in code_files:
                change_data = next((c for c in state.pr_changes if c.get("filename") == file_path), None)
                
                if change_data and change_data.get("status") == "added":
                    # New file added
                    new_component = CodeComponentModel(
                        id=f"CC-NEW-{len(new_code_components) + 1:03d}",
                        path=file_path,
                        type="File",
                        name=Path(file_path).stem
                    )
                    new_code_components.append(new_component)
                elif change_data and change_data.get("patch"):
                    # Check if significant new functionality was added
                    added_content = self._extract_added_content(change_data.get("patch", ""))
                    if self._is_significant_code_addition(added_content):
                        # Extract new components from significant additions
                        extracted_components = await self._extract_components_from_code_addition(file_path, added_content)
                        new_code_components.extend(extracted_components)
            
            state.new_requirements = new_requirements
            state.new_design_elements = new_design_elements
            state.new_code_components = new_code_components
            
            logger.info(f"Extracted {len(new_requirements)} new requirements, "
                       f"{len(new_design_elements)} new design elements, "
                       f"{len(new_code_components)} new code components")
            
        except Exception as e:
            error_msg = f"Error extracting new elements: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _update_traceability_links(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """
        Update traceability links with new elements and relationships
        """
        logger.info("Updating traceability links")
        state.current_step = "updating_traceability_links"
        
        try:
            new_links = []
            
            # Create links between new requirements and existing/new design elements
            if state.new_requirements:
                all_design_elements = state.current_baseline_map.design_elements + state.new_design_elements
                new_req_design_links = await self._create_requirement_design_links(
                    state.new_requirements, all_design_elements
                )
                new_links.extend(new_req_design_links)
            
            # Create links between new design elements and existing/new code components
            if state.new_design_elements:
                all_code_components = state.current_baseline_map.code_components + state.new_code_components
                new_design_code_links = await self._create_design_code_links(
                    state.new_design_elements, all_code_components
                )
                new_links.extend(new_design_code_links)
            
            # Update existing links that might be affected by changes
            updated_links = await self._update_existing_links(state)
            new_links.extend(updated_links)
            
            state.new_traceability_links = new_links
            logger.info(f"Created/updated {len(new_links)} traceability links")
            
        except Exception as e:
            error_msg = f"Error updating traceability links: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _save_updated_map(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """
        Save updated baseline map to database
        """
        logger.info("Saving updated baseline map")
        state.current_step = "saving_updated_map"
        
        try:
            # Create updated baseline map
            updated_baseline_map = BaselineMapModel(
                repository=state.repository,
                branch=state.branch,
                requirements=state.current_baseline_map.requirements + state.new_requirements,
                design_elements=state.current_baseline_map.design_elements + state.new_design_elements,
                code_components=state.current_baseline_map.code_components + state.new_code_components,
                traceability_links=state.current_baseline_map.traceability_links + state.new_traceability_links
            )
            
            # Save to database (this will update the existing map)
            success = await self.baseline_map_repo.save_baseline_map(updated_baseline_map)
            
            if success:
                logger.info(f"Successfully updated baseline map for {state.repository}:{state.branch}")
                state.current_step = "completed"
                
                # Update statistics
                state.processing_stats = {
                    "new_requirements": len(state.new_requirements),
                    "new_design_elements": len(state.new_design_elements),
                    "new_code_components": len(state.new_code_components),
                    "new_traceability_links": len(state.new_traceability_links),
                    "total_requirements": len(updated_baseline_map.requirements),
                    "total_design_elements": len(updated_baseline_map.design_elements),
                    "total_code_components": len(updated_baseline_map.code_components),
                    "total_traceability_links": len(updated_baseline_map.traceability_links)
                }
            else:
                error_msg = "Failed to save updated baseline map to database"
                logger.error(error_msg)
                state.errors.append(error_msg)
            
        except Exception as e:
            error_msg = f"Error saving updated baseline map: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    # Helper methods (placeholders for actual implementations)
    async def _fetch_pr_data(self, repository: str) -> Optional[Dict[str, Any]]:
        """Fetch PR data from GitHub API"""
        # Placeholder - would implement GitHub API calls
        return {
            "changes": [
                {"filename": "src/auth/AuthService.py", "patch": "+def new_method():\n+    pass", "status": "modified"},
                {"filename": "docs/requirements.md", "patch": "+## New Requirement\n+Description...", "status": "modified"}
            ],
            "commit_messages": ["Add new authentication method", "Update requirements documentation"]
        }
    
    def _extract_added_content(self, patch: str) -> str:
        """Extract added content from Git patch"""
        added_lines = []
        for line in patch.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                added_lines.append(line[1:])  # Remove + prefix
        return '\n'.join(added_lines)
    
    def _is_significant_code_addition(self, content: str) -> bool:
        """Check if code addition is significant enough to create new components"""
        # Simple heuristic - could be more sophisticated
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        return len(lines) > 10  # More than 10 non-empty lines
    
    async def _llm_extract_requirements_from_content(self, content: str, file_path: str) -> List[RequirementModel]:
        """Extract requirements from content using LLM"""
        # Placeholder - would implement LLM extraction
        return []
    
    async def _llm_extract_design_elements_from_content(self, content: str, file_path: str) -> List[DesignElementModel]:
        """Extract design elements from content using LLM"""
        # Placeholder - would implement LLM extraction
        return []
    
    async def _extract_components_from_code_addition(self, file_path: str, content: str) -> List[CodeComponentModel]:
        """Extract code components from code addition"""
        # Placeholder - would implement static analysis + LLM
        return []
    
    async def _create_requirement_design_links(self, requirements: List[RequirementModel], design_elements: List[DesignElementModel]) -> List[TraceabilityLinkModel]:
        """Create links between requirements and design elements"""
        # Placeholder - would use vector similarity + LLM
        return []
    
    async def _create_design_code_links(self, design_elements: List[DesignElementModel], code_components: List[CodeComponentModel]) -> List[TraceabilityLinkModel]:
        """Create links between design elements and code components"""
        # Placeholder - would use vector similarity + LLM
        return []
    
    async def _update_existing_links(self, state: BaselineMapUpdaterState) -> List[TraceabilityLinkModel]:
        """Update existing links that might be affected by changes"""
        # Placeholder - would implement link update logic
        return []

# Factory function
def create_baseline_map_updater(llm_client: Optional[DocurecoLLMClient] = None,
                               baseline_map_repo: Optional[BaselineMapRepository] = None) -> BaselineMapUpdaterWorkflow:
    """
    Factory function to create baseline map updater workflow
    
    Args:
        llm_client: Optional LLM client for analysis
        baseline_map_repo: Optional baseline map repository
        
    Returns:
        BaselineMapUpdaterWorkflow: Configured workflow
    """
    return BaselineMapUpdaterWorkflow(llm_client, baseline_map_repo)

# Export main classes
__all__ = ["BaselineMapUpdaterWorkflow", "BaselineMapUpdaterState", "create_baseline_map_updater"] 