"""
Baseline Map Updater Workflow for Docureco Agent
Updates baseline traceability maps based on repository changes, following a structure
similar to the BaselineMapCreatorWorkflow.
"""

import logging
import sys
import os
import asyncio
from typing import Dict, Any, List, Optional
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

from langgraph.graph import StateGraph, END
from agent.llm.llm_client import DocurecoLLMClient, create_llm_client
from agent.database.baseline_map_repository import BaselineMapRepository
from agent.models.docureco_models import BaselineMapModel
from .prompts import (
    raw_change_identification_system_prompt,
    raw_change_identification_human_prompt,
    reconciliation_system_prompt,
    reconciliation_human_prompt
)
from .models import (
    DesignElementChangesOutput,
    RawChangeDetectionOutput
)

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
        logger.info("Initialized BaselineMapUpdaterWorkflow")
        
    def _build_workflow(self) -> StateGraph:
        """Builds the LangGraph workflow with conditional routing."""
        workflow = StateGraph(BaselineMapUpdaterState)
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
            "repository": repository, "branch": branch, "commit_sha": commit_sha,
            "baseline_map": None, "changed_srs_content": {}, "changed_sdd_content": {},
            "changed_code_files": {}, "new_design_elements": [], "modified_design_elements": [],
            "deleted_design_elements": [], "current_step": "initializing",
        }
        initial_state["baseline_map"] = await self.baseline_map_repo.get_baseline_map(repository, branch)
        if not initial_state["baseline_map"]:
            logger.info(f"Baseline map not found for {repository}:{branch}. Workflow will terminate.")
            return initial_state
        
        app = self.workflow.compile()
        final_state = await app.ainvoke(initial_state)
        
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

    async def _fetch_changed_files_content(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        logger.info(f"Fetching changed files for commit {state['commit_sha']}...")
        state["current_step"] = "fetching_files"
        repo, commit_sha, github_token = state["repository"], state["commit_sha"], os.getenv("GITHUB_TOKEN")

        if not github_token:
            state["error"] = "GITHUB_TOKEN not set."
            return state

        headers = {"Authorization": f"token {github_token}"}
        commit_url = f"https://api.github.com/repos/{repo}/commits/{commit_sha}"

        try:
            async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
                commit_response = await client.get(commit_url)
                commit_response.raise_for_status()
                commit_data = commit_response.json()
                parent_sha = commit_data["parents"][0]["sha"] if commit_data.get("parents") else None
                
                compare_url = f"https://api.github.com/repos/{repo}/compare/{parent_sha}...{commit_sha}" if parent_sha else commit_url
                compare_response = await client.get(compare_url)
                compare_response.raise_for_status()
                changed_files = compare_response.json().get("files", [])

                sdd_patterns = ["sdd.md", "design.md"]
                srs_patterns = ["srs.md", "requirements.md"]

                for file_info in changed_files:
                    status, file_path = file_info["status"], file_info["filename"]
                    change_data = {"change_type": status, "old_content": "", "new_content": "", "patch": file_info.get("patch", "")}
                    is_doc = any(p in file_path for p in sdd_patterns) or any(p in file_path for p in srs_patterns)

                    if is_doc:
                        if status in ["added", "modified"]:
                            change_data["new_content"] = await self._get_file_content_from_api(client, file_info["contents_url"])
                        if parent_sha and status in ["modified", "deleted"]:
                            old_content_url = f"https://api.github.com/repos/{repo}/contents/{file_path}?ref={parent_sha}"
                            change_data["old_content"] = await self._get_file_content_from_api(client, old_content_url)

                    if any(p in file_path for p in sdd_patterns): state["changed_sdd_content"][file_path] = change_data
                    elif any(p in file_path for p in srs_patterns): state["changed_srs_content"][file_path] = change_data
                    else: state["changed_code_files"][file_path] = change_data

        except httpx.HTTPStatusError as e:
            state["error"] = f"GitHub API request failed: {e}"
        return state

    async def _process_single_document_analysis(self, file_path: str, changes: Dict, baseline_elements: List[Dict]) -> Optional[DesignElementChangesOutput]:
        try:
            old_content, new_content = changes.get("old_content", ""), changes.get("new_content", "")
            if not new_content and not old_content: return None

            # Pass 1: Raw Identification
            diff_text = ''.join(difflib.unified_diff(old_content.splitlines(), new_content.splitlines(), fromfile=f"a/{file_path}", tofile=f"b/{file_path}"))
            raw_parser = JsonOutputParser(pydantic_object=RawChangeDetectionOutput)
            raw_system_prompt = raw_change_identification_system_prompt()
            raw_human_prompt = raw_change_identification_human_prompt(new_content, diff_text, file_path)
            
            identification_result = await self.llm_client.generate_response(
                prompt=raw_human_prompt,
                system_message=raw_system_prompt + "\n" + raw_parser.get_format_instructions(),
                output_format="json", 
                temperature=0.1
            )
            detected_changes = identification_result.content["detected_changes"]

            if not detected_changes: return None

            # Pass 2: Reconciliation
            relevant_elements = [de for de in baseline_elements if re.match(r'^(?:REQ|DE)-' + re.escape(file_path), de['reference_id'])]
            recon_parser = JsonOutputParser(pydantic_object=DesignElementChangesOutput)
            recon_system_prompt = reconciliation_system_prompt()
            recon_human_prompt = reconciliation_human_prompt([c.dict() for c in detected_changes], relevant_elements)
            
            reconciliation_result = await self.llm_client.generate_response(
                prompt=recon_human_prompt,
                system_message=recon_system_prompt + "\n" + recon_parser.get_format_instructions(),
                output_format="json", 
                temperature=0.0
            )
            return reconciliation_result.content
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}")
            return None

    async def _identify_changed_design_elements(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        logger.info("Identifying changed design elements from SDD files...")
        state["current_step"] = "identifying_design_element_changes"
        changed_sdds = state.get("changed_sdd_content", {})
        
        baseline_elements_as_dicts = [de.dict() for de in state["baseline_map"].design_elements]

        tasks = [
            self._process_single_document_analysis(file_path, changes, baseline_elements_as_dicts)
            for file_path, changes in changed_sdds.items()
        ]
        results = await asyncio.gather(*tasks)

        for result in results:
            if result:
                state["new_design_elements"].extend(result.added)
                state["modified_design_elements"].extend(result.modified)
                state["deleted_design_elements"].extend(result.deleted)

        logger.info(f"Analysis complete. Found {len(state['new_design_elements'])} new, {len(state['modified_design_elements'])} modified, and {len(state['deleted_design_elements'])} deleted elements.")
        return state

    async def _identify_changed_requirements(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        logger.info("Skipping detailed SRS analysis in this version.")
        return state

    async def _update_design_to_design_mapping(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        logger.info("Skipping D2D mapping logic in this version.")
        return state

    async def _update_requirements_to_design_mapping(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        logger.info("Skipping R2D mapping logic in this version.")
        return state

    async def _map_new_code_to_design(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        logger.info("Skipping C2D mapping for new files in this version.")
        return state

    async def _save_baseline_map_update(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
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