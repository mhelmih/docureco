"""
Baseline Map Updater Workflow for Docureco Agent
Updates baseline traceability maps based on repository changes, following a structure
similar to the BaselineMapCreatorWorkflow.
"""

import logging
import sys
import os
from typing import Dict, Any, List, Optional, Tuple
import subprocess

# Add parent directories to path for absolute imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, root_dir)

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langchain_core.output_parsers import JsonOutputParser

from agent.llm.llm_client import DocurecoLLMClient, create_llm_client
from agent.database.baseline_map_repository import BaselineMapRepository
from agent.models.docureco_models import BaselineMapModel, DesignElementModel, RequirementModel, CodeComponentModel, TraceabilityLinkModel
from .prompts import get_analysis_prompt_for_changes
from .models import RelationshipListOutput

logger = logging.getLogger(__name__)

BaselineMapUpdaterState = Dict[str, Any]

class BaselineMapUpdaterWorkflow:
    """
    LangGraph workflow for updating baseline traceability maps based on file changes.
    This workflow mimics the structure of the creator but operates on incremental changes.
    """
    
    def __init__(self, 
                 llm_client: Optional[DocurecoLLMClient] = None,
                 baseline_map_repo: Optional[BaselineMapRepository] = None):
        self.llm_client = llm_client or create_llm_client()
        self.baseline_map_repo = baseline_map_repo or BaselineMapRepository()
        self.workflow = self._build_workflow()
        self.memory = MemorySaver()
    
        logger.info("Initialized BaselineMapUpdaterWorkflow")
        
    def _build_workflow(self) -> StateGraph:
        """Builds the LangGraph workflow with conditional routing."""
        workflow = StateGraph(BaselineMapUpdaterState)
        
        # Define the nodes based on the user's specified flow
        workflow.add_node("fetch_changed_files_content", self._fetch_changed_files_content)
        # workflow.add_node("identify_changed_design_elements", self._identify_changed_design_elements)
        # workflow.add_node("identify_changed_requirements", self._identify_changed_requirements)
        # workflow.add_node("update_design_to_design_mapping", self._update_design_to_design_mapping)
        # workflow.add_node("update_requirements_to_design_mapping", self._update_requirements_to_design_mapping)
        # workflow.add_node("map_new_code_to_design", self._map_new_code_to_design)
        # workflow.add_node("save_baseline_map_update", self._save_baseline_map_update)

        # workflow.add_conditional_edges(
        #     "fetch_changed_files_content",
        #     lambda state: "identify_changed_design_elements" if not state.get("error") else "end",
        #     {"identify_changed_design_elements": "identify_changed_design_elements", "end": END}
        # )
        
        # # Linear flow for the rest of the mapping process
        # workflow.add_edge("identify_changed_design_elements", "identify_changed_requirements")
        # workflow.add_edge("identify_changed_requirements", "update_design_to_design_mapping")
        # workflow.add_edge("update_design_to_design_mapping", "update_requirements_to_design_mapping")
        # workflow.add_edge("update_requirements_to_design_mapping", "map_new_code_to_design")
        # workflow.add_edge("map_new_code_to_design", "save_baseline_map_update")
        # workflow.add_edge("save_baseline_map_update", END)
        
        return workflow

    async def execute(self, repository: str, branch: str, file_changes: List[Dict[str, Any]]) -> BaselineMapUpdaterState:
        """Executes the baseline map update workflow."""
        initial_state = {
            "repository": repository,
            "branch": branch,
            "file_changes": file_changes,
            "baseline_map": None,
            "changed_srs_content": {},
            "changed_sdd_content": {},
            "changed_code_files": {},
            "changed_design_elements": [],
            "changed_requirements": [],
            "new_or_updated_links": [],
            "current_step": "initializing",
            "processing_stats": {}
        }
        
        # Check if baseline map already exists
        initial_state["baseline_map"] = await self.baseline_map_repo.get_baseline_map(repository, branch)
        
        if not initial_state["baseline_map"]:
            logger.info(f"Baseline map not found for {repository}:{branch}. Workflow will terminate.")
            return initial_state
        
        app = self.workflow.compile(checkpointer=self.memory)
        config = {"configurable": {"thread_id": f"baseline_{repository.replace('/', '_')}_{branch}"}}
        
        final_state = await app.ainvoke(initial_state, config=config)
        
        current_step = final_state.get("current_step", "unknown")
        if current_step == "completed":
            logger.info(f"✅ Baseline map update completed successfully for {repository}:{branch}")
        else:
            logger.error(f"⚠️  Baseline map update terminated early at step: {current_step}")
            logger.error(f"   Repository: {repository}:{branch}")
            
        return final_state

    async def _fetch_changed_files_content(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """
        Fetches the content of changed files from the latest merge commit.
        This implementation uses git commands to get the real changes.
        """
        logger.info("Fetching changed files content from the last commit...")
        state["current_step"] = "fetching_files"

        try:
            # Get the list of changed files from the last commit compared to its first parent
            git_diff_cmd = "git diff --name-status HEAD^ HEAD"
            # In a real CI environment, you might need to fetch more history `git fetch --depth=2`
            result = subprocess.run(git_diff_cmd, capture_output=True, text=True, shell=True, check=True)
            changed_files_raw = result.stdout.strip().split('\n')

            if not changed_files_raw or not changed_files_raw[0]:
                logger.info("No file changes detected in the last commit. Terminating workflow.")
                state["error"] = "No file changes detected."
                return state

            sdd_patterns = ["sdd.md", "design.md"]
            srs_patterns = ["srs.md", "requirements.md"]

            for file_info in changed_files_raw:
                status, file_path = file_info.split('\t')
                change_data = {"change_type": None, "old_content": "", "new_content": ""}

                if status == 'A': # Added
                    change_data["change_type"] = "addition"
                    new_content_raw = subprocess.run(f"git show HEAD:'{file_path}'", capture_output=True, text=True, shell=True)
                    if new_content_raw.returncode == 0:
                        change_data["new_content"] = new_content_raw.stdout
                
                elif status == 'D': # Deleted
                    change_data["change_type"] = "deletion"
                    old_content_raw = subprocess.run(f"git show HEAD^:'{file_path}'", capture_output=True, text=True, shell=True)
                    if old_content_raw.returncode == 0:
                        change_data["old_content"] = old_content_raw.stdout

                elif status == 'M': # Modified
                    change_data["change_type"] = "modification"
                    old_content_raw = subprocess.run(f"git show HEAD^:'{file_path}'", capture_output=True, text=True, shell=True)
                    if old_content_raw.returncode == 0:
                        change_data["old_content"] = old_content_raw.stdout
                    new_content_raw = subprocess.run(f"git show HEAD:'{file_path}'", capture_output=True, text=True, shell=True)
                    if new_content_raw.returncode == 0:
                        change_data["new_content"] = new_content_raw.stdout
                
                elif status == 'R': # Renamed
                    change_data["change_type"] = "renamed"
                    old_content_raw = subprocess.run(f"git show HEAD^:'{file_path}'", capture_output=True, text=True, shell=True)
                    if old_content_raw.returncode == 0:
                        change_data["old_content"] = old_content_raw.stdout
                    new_content_raw = subprocess.run(f"git show HEAD:'{file_path}'", capture_output=True, text=True, shell=True)
                    if new_content_raw.returncode == 0:
                        change_data["new_content"] = new_content_raw.stdout
                
                else: # Renamed, copied, etc.
                    logger.info(f"Skipping unhandled change status '{status}' for file {file_path}")
                    continue
                
                # Categorize the file
                if any(p in file_path for p in sdd_patterns):
                    state["changed_sdd_content"][file_path] = change_data
                elif any(p in file_path for p in srs_patterns):
                    state["changed_srs_content"][file_path] = change_data
                else:
                    state["changed_code_files"][file_path] = change_data
                
                logger.info(f"CHANGED SDD CONTENT: {state['changed_sdd_content']}")
                logger.info(f"CHANGED SRS CONTENT: {state['changed_srs_content']}")
                logger.info(f"CHANGED CODE FILES: {state['changed_code_files']}")

            if not state["changed_sdd_content"] and not state["changed_srs_content"]:
                logger.info("No changes found in SRS or SDD files. Workflow will terminate.")
                state["error"] = "No documentation files changed."

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to run git command: {e.stderr}")
            state["error"] = "Git command failed."
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching changed files: {e}")
            state["error"] = "Unexpected error during file fetching."
            
        return state
    
    async def _identify_changed_design_elements(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """3. Identify changed design elements in SDD."""
        logger.info("Identifying changed design elements from changed SDD files.")
        # This is a simplified analysis. A real one would be more complex.
        # For now, we'll imagine a prompt that can identify new, updated, and deleted elements.
        # The logic for deletion and updates will be handled in the save step for simplicity here.
        logger.info("Skipping detailed SDD analysis in this version.")
        return state

    async def _identify_changed_requirements(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """4. Identify changed requirements in SRS."""
        logger.info("Identifying changed requirements from changed SRS files.")
        # Similar to design elements, this is a placeholder for a more complex analysis.
        logger.info("Skipping detailed SRS analysis in this version.")
        return state

    async def _update_design_to_design_mapping(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """5. Update design-to-design mappings based on changed elements."""
        logger.info("Updating design-to-design mappings.")
        # Placeholder for D2D mapping logic
        return state

    async def _update_requirements_to_design_mapping(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """6. Update requirements-to-design mappings based on changed requirements."""
        logger.info("Updating requirements-to-design mappings.")
        # Placeholder for R2D mapping logic
        return state

    async def _map_new_code_to_design(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """7. Map newly added code files to all design elements."""
        logger.info("Mapping new code files to design elements.")
        # Placeholder for C2D mapping for new files
        return state

    async def _save_baseline_map_update(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """8. Save the updated baseline map, handling creations, updates, and deletions."""
        logger.info("Applying all changes and saving the updated baseline map.")
        
        baseline_map: BaselineMapModel = state["baseline_map"]

        # Handle deletions first
        # Remove elements associated with deleted documents
        # This requires knowing which document an element belongs to. We'll simulate with path matching.
        
        # A more robust implementation needs to be added here to handle CRUD operations correctly
        # based on the outputs from the analysis steps.
        
        success = await self.baseline_map_repo.save_baseline_map(baseline_map)
        if not success:
            state["error"] = "Failed to save the updated baseline map."
            logger.error(state["error"])
        else:
            logger.info("Successfully saved the updated baseline map.")
            
        return state

def create_baseline_map_updater(llm_client: Optional[DocurecoLLMClient] = None,
                               baseline_map_repo: Optional[BaselineMapRepository] = None) -> BaselineMapUpdaterWorkflow:
    return BaselineMapUpdaterWorkflow(llm_client, baseline_map_repo)

__all__ = ["BaselineMapUpdaterWorkflow", "BaselineMapUpdaterState", "create_baseline_map_updater"] 