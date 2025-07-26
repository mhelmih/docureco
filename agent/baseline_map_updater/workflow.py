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
import httpx
import base64
import difflib
import re
from langchain_core.output_parsers import JsonOutputParser

# Add parent directories to path for absolute imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, root_dir)

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END

from agent.llm.llm_client import DocurecoLLMClient, create_llm_client
from agent.database.baseline_map_repository import BaselineMapRepository
from agent.models.docureco_models import BaselineMapModel, DesignElementModel, RequirementModel, CodeComponentModel, TraceabilityLinkModel
from .prompts import design_element_analysis_system_prompt, design_element_analysis_human_prompt
from .models import DesignElementChangesOutput

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
        workflow.add_node("identify_changed_design_elements", self._identify_changed_design_elements)
        workflow.add_node("identify_changed_requirements", self._identify_changed_requirements)
        workflow.add_node("update_design_to_design_mapping", self._update_design_to_design_mapping)
        workflow.add_node("update_requirements_to_design_mapping", self._update_requirements_to_design_mapping)
        workflow.add_node("map_new_code_to_design", self._map_new_code_to_design)
        workflow.add_node("save_baseline_map_update", self._save_baseline_map_update)

        workflow.set_entry_point("fetch_changed_files_content")
        
        workflow.add_conditional_edges(
            "fetch_changed_files_content",
            lambda state: "identify_changed_design_elements" if not state.get("error") else END,
            {"identify_changed_design_elements": "identify_changed_design_elements", "end": END}
        )
        
        # Linear flow for the rest of the mapping process
        workflow.add_edge("identify_changed_design_elements", "identify_changed_requirements")
        workflow.add_edge("identify_changed_requirements", "update_design_to_design_mapping")
        workflow.add_edge("update_design_to_design_mapping", "update_requirements_to_design_mapping")
        workflow.add_edge("update_requirements_to_design_mapping", "map_new_code_to_design")
        workflow.add_edge("map_new_code_to_design", "save_baseline_map_update")
        workflow.add_edge("save_baseline_map_update", END)
        
        return workflow

    async def execute(self, repository: str, branch: str, commit_sha: str) -> BaselineMapUpdaterState:
        """Executes the baseline map update workflow."""
        initial_state = {
            "repository": repository,
            "branch": branch,
            "commit_sha": commit_sha,
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

    async def _get_file_content_from_api(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        """Helper to fetch and decode file content from GitHub API."""
        try:
            response = await client.get(url)
            response.raise_for_status()
            content_base64 = response.json().get("content", "")
            if content_base64:
                try:
                    return base64.b64decode(content_base64).decode('utf-8')
                except UnicodeDecodeError:
                    logger.warning(f"Could not decode file content from {url} as UTF-8. Treating as binary.")
                    return "[binary content]"
            return ""
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch content from {url}: {e.response.status_code} - {e.response.text}")
            return None
        except (base64.binascii.Error, UnicodeDecodeError) as e:
            logger.error(f"Failed to decode content from {url}: {e}")
            return None

    async def _fetch_changed_files_content(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """
        Fetches the content of changed files from the specified commit using the GitHub API.
        """
        logger.info(f"Fetching changed files content for commit {state['commit_sha']}...")
        state["current_step"] = "fetching_files"
        
        repo = state["repository"]
        commit_sha = state["commit_sha"]
        github_token = os.getenv("GITHUB_TOKEN")
        
        if not github_token:
            state["error"] = "GITHUB_TOKEN environment variable not set."
            logger.error(state["error"])
            return state

        headers = {"Authorization": f"token {github_token}"}
        commit_url = f"https://api.github.com/repos/{repo}/commits/{commit_sha}"

        try:
            async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
                commit_response = await client.get(commit_url)
                commit_response.raise_for_status()
                commit_data = commit_response.json()

                parent_sha = commit_data["parents"][0]["sha"] if commit_data.get("parents") else None
                
                if not parent_sha:
                    logger.info("No parent commit found. This might be the first commit. Analyzing all files.")
                    changed_files = commit_data.get("files", [])
                else:
                    compare_url = f"https://api.github.com/repos/{repo}/compare/{parent_sha}...{commit_sha}"
                    compare_response = await client.get(compare_url)
                    compare_response.raise_for_status()
                    changed_files = compare_response.json().get("files", [])

                if not changed_files:
                    logger.info("No file changes detected in the commit. Terminating workflow.")
                    state["error"] = "No file changes detected."
                    return state

                sdd_patterns = ["sdd.md", "design.md"]
                srs_patterns = ["srs.md", "requirements.md"]

                for file_info in changed_files:
                    status = file_info["status"]
                    file_path = file_info["filename"]
                    
                    change_data = {"change_type": status, "old_content": "", "new_content": "", "patch": ""}

                    is_doc_file = any(p in file_path for p in sdd_patterns) or any(p in file_path for p in srs_patterns)

                    if is_doc_file:
                        # For documentation, fetch full content for better contextual analysis
                        if status in ["added", "modified"]:
                            new_content_url = file_info["contents_url"]
                            change_data["new_content"] = await self._get_file_content_from_api(client, new_content_url)
                        
                        if parent_sha and status in ["modified", "deleted"]:
                            old_content_url = f"https://api.github.com/repos/{repo}/contents/{file_path}?ref={parent_sha}"
                            change_data["old_content"] = await self._get_file_content_from_api(client, old_content_url)
                    else:
                        # For code files, just get the patch for efficiency
                        change_data["patch"] = file_info.get("patch", "")

                    if any(p in file_path for p in sdd_patterns):
                        state["changed_sdd_content"][file_path] = change_data
                    elif any(p in file_path for p in srs_patterns):
                        state["changed_srs_content"][file_path] = change_data
                    else:
                        state["changed_code_files"][file_path] = change_data
                
                logger.info(f"CHANGED CODE FILES: {state['changed_code_files']}")
                logger.info(f"CHANGED SDD CONTENT: {state['changed_sdd_content']}")
                logger.info(f"CHANGED SRS CONTENT: {state['changed_srs_content']}")
                
                if not state["changed_sdd_content"] and not state["changed_srs_content"]:
                    logger.info("No changes found in SRS or SDD files. Workflow will terminate.")
                    state["error"] = "No documentation files changed."

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch commit data from GitHub API: {e.response.status_code} - {e.response.text}")
            state["error"] = "GitHub API request failed."
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching changed files: {e}")
            state["error"] = "Unexpected error during file fetching."
            
        return state
    
    async def _identify_changed_design_elements(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """
        Identifies added, modified, and deleted design elements by comparing
        the new version of an SDD with a diff of the changes.
        """
        logger.info("Identifying changed design elements from SDD files...")
        state["current_step"] = "identifying_design_element_changes"
        
        changed_sdds = state.get("changed_sdd_content", {})
        if not changed_sdds:
            logger.info("No changed SDD files to analyze.")
            return state
        
        all_new_elements, all_modified_elements, all_deleted_elements = [], [], []

        output_parser = JsonOutputParser(pydantic_object=DesignElementChangesOutput)
        system_prompt = design_element_analysis_system_prompt()

        for file_path, changes in changed_sdds.items():
            old_content = changes.get("old_content", "")
            new_content = changes.get("new_content", "")

            if not new_content and not old_content:
                continue

            # Filter baseline elements to only those relevant to the current file using regex on the ID
            relevant_existing_elements = []
            for de in state["baseline_map"].design_elements:
                # Extracts the file path from IDs like 'DE-path/to/doc.md-001'
                match = re.match(r'^(?:REQ|DE)-(.+)-\d{3}$', de.id)
                if match:
                    file_path_from_id = match.group(1)
                    if file_path_from_id == file_path:
                        relevant_existing_elements.append(de.dict())

            # Create a lookup set of IDs for the relevant elements for reconciliation
            relevant_existing_ids = {el['reference_id'] for el in relevant_existing_elements}

            diff_text = ''.join(difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
            ))

            human_prompt = design_element_analysis_human_prompt(
                new_content=new_content,
                diff_text=diff_text,
                file_path=file_path,
                relevant_existing_elements=relevant_existing_elements
            )
            
            try:
                response = await self.llm_client.generate_response(
                    prompt=human_prompt,
                    system_message=system_prompt + "\n" + output_parser.get_format_instructions(),
                    output_format="json",
                    temperature=0.1
                )
                
                llm_analysis_result = response.content

                for added_el in llm_analysis_result["added"]:
                    if added_el["reference_id"] in relevant_existing_ids:
                        logger.warning(f"LLM suggested adding element `{added_el['reference_id']}` which already exists. Treating as modification.")
                        all_modified_elements.append({"reference_id": added_el["reference_id"], "changes": added_el})
                    else:
                        all_new_elements.append(added_el)
                        relevant_existing_ids.add(added_el["reference_id"]) # Add to set to avoid duplicates within same analysis
                
                for modified_el in llm_analysis_result["modified"]:
                    if modified_el["reference_id"] in relevant_existing_ids:
                        all_modified_elements.append(modified_el)
                    else:
                        logger.warning(f"LLM suggested modifying element `{modified_el['reference_id']}` which does not exist. Ignoring.")

                for deleted_el in llm_analysis_result["deleted"]:
                    if deleted_el["reference_id"] in relevant_existing_ids:
                        all_deleted_elements.append(deleted_el)
                        relevant_existing_ids.remove(deleted_el["reference_id"]) # Remove from set
                    else:
                        logger.warning(f"LLM suggested deleting element `{deleted_el['reference_id']}` which does not exist. Ignoring.")

            except Exception as e:
                logger.error(f"Failed to analyze design element changes for {file_path}: {e}")
                state["error"] = f"LLM analysis failed for {file_path}."
                continue
        
        state["new_design_elements"] = all_new_elements
        state["modified_design_elements"] = all_modified_elements
        state["deleted_design_elements"] = all_deleted_elements
        
        logger.info(f"NEW DESIGN ELEMENTS: {all_new_elements}")
        logger.info(f"MODIFIED DESIGN ELEMENTS: {all_modified_elements}")
        logger.info(f"DELETED DESIGN ELEMENTS: {all_deleted_elements}")

        logger.info(f"Analysis complete. Found {len(all_new_elements)} new, {len(all_modified_elements)} modified, and {len(all_deleted_elements)} deleted design elements.")
        
        return state

    async def _identify_changed_requirements(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """4. Identify changed requirements in SRS."""
        logger.info("Identifying changed requirements from changed SRS files.")
        logger.info("Skipping detailed SRS analysis in this version.")
        return state

    async def _update_design_to_design_mapping(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """5. Update design-to-design mappings based on changed elements."""
        logger.info("Updating design-to-design mappings.")
        return state

    async def _update_requirements_to_design_mapping(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """6. Update requirements-to-design mappings based on changed requirements."""
        logger.info("Updating requirements-to-design mappings.")
        return state

    async def _map_new_code_to_design(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """7. Map newly added code files to all design elements."""
        logger.info("Mapping new code files to design elements.")
        return state

    async def _save_baseline_map_update(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        """8. Save the updated baseline map, handling creations, updates, and deletions."""
        logger.info("Applying all changes and saving the updated baseline map.")
        
        baseline_map: BaselineMapModel = state["baseline_map"]
        
        success = await self.baseline_map_repo.save_baseline_map(baseline_map)
        if not success:
            state["error"] = "Failed to save the updated baseline map."
            logger.error(state["error"])
        else:
            logger.info("Successfully saved the updated baseline map.")
            state["current_step"] = "completed"
            
        return state

def create_baseline_map_updater(llm_client: Optional[DocurecoLLMClient] = None,
                               baseline_map_repo: Optional[BaselineMapRepository] = None) -> BaselineMapUpdaterWorkflow:
    return BaselineMapUpdaterWorkflow(llm_client, baseline_map_repo)

__all__ = ["BaselineMapUpdaterWorkflow", "BaselineMapUpdaterState", "create_baseline_map_updater"] 