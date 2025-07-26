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
    raw_unified_change_identification_system_prompt,
    raw_unified_change_identification_human_prompt,
    unified_reconciliation_system_prompt,
    unified_reconciliation_human_prompt
)
from .models import (
    UnifiedChangesOutput,
    RawUnifiedChangeDetectionOutput
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
        workflow.add_node("analyze_document_changes", self._analyze_document_changes)
        workflow.add_node("update_traceability_mappings", self._update_traceability_mappings)
        workflow.add_node("save_baseline_map_update", self._save_baseline_map_update)

        workflow.set_entry_point("fetch_changed_files_content")
        workflow.add_conditional_edges(
            "fetch_changed_files_content",
            lambda state: "analyze_document_changes" if not state.get("error") else END,
            {"analyze_document_changes": "analyze_document_changes", "end": END}
        )
        
        workflow.add_edge("analyze_document_changes", "update_traceability_mappings")
        workflow.add_edge("update_traceability_mappings", "save_baseline_map_update")
        workflow.add_edge("save_baseline_map_update", END)
        return workflow

    async def execute(self, repository: str, branch: str, commit_sha: str) -> BaselineMapUpdaterState:
        """Executes the baseline map update workflow."""
        initial_state = {
            "repository": repository, "branch": branch, "commit_sha": commit_sha,
            "baseline_map": None, "changed_docs": {}, "changed_code_files": {},
            "new_elements": [], "modified_elements": [], "deleted_elements": [],
            "current_step": "initializing",
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
        return final_state

    async def _get_file_content_from_api(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        """Helper to fetch and decode file content from GitHub API."""
        try:
            response = await client.get(url)
            response.raise_for_status()
            content_base64 = response.json().get("content", "")
            if content_base64:
                try: return base64.b64decode(content_base64).decode('utf-8')
                except UnicodeDecodeError: return "[binary content]"
            return ""
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch content from {url}: {e.response.status_code}")
            return None

    async def _fetch_changed_files_content(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        logger.info(f"Fetching changed files for commit {state['commit_sha']}...")
        state["current_step"] = "fetching_files"
        repo, commit_sha, github_token = state["repository"], state["commit_sha"], os.getenv("GITHUB_TOKEN")

        if not github_token:
            state["error"] = "GITHUB_TOKEN not set."
            return state

        headers = {"Authorization": f"token {github_token}"}
        try:
            async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
                commit_url = f"https://api.github.com/repos/{repo}/commits/{commit_sha}"
                commit_response = await client.get(commit_url)
                commit_response.raise_for_status()
                commit_data = commit_response.json()
                parent_sha = commit_data["parents"][0]["sha"] if commit_data.get("parents") else None
                
                compare_url = f"https://api.github.com/repos/{repo}/compare/{parent_sha}...{commit_sha}" if parent_sha else commit_url
                compare_response = await client.get(compare_url)
                compare_response.raise_for_status()
                changed_files = compare_response.json().get("files", [])

                doc_patterns = ["sdd.md", "design.md", "srs.md", "requirements.md"]
                for file_info in changed_files:
                    file_path = file_info["filename"]
                    if any(p in file_path for p in doc_patterns):
                        status = file_info["status"]
                        change_data = {"old_content": "", "new_content": ""}
                        if status in ["added", "modified"]:
                            change_data["new_content"] = await self._get_file_content_from_api(client, file_info["contents_url"])
                        if parent_sha and status in ["modified", "deleted"]:
                            old_content_url = f"https://api.github.com/repos/{repo}/contents/{file_path}?ref={parent_sha}"
                            change_data["old_content"] = await self._get_file_content_from_api(client, old_content_url)
                        state["changed_docs"][file_path] = change_data
                    else:
                        state["changed_code_files"][file_path] = file_info.get("patch", "")
        except httpx.HTTPStatusError as e:
            state["error"] = f"GitHub API request failed: {e}"
        return state

    async def _process_single_document_for_any_element(self, file_path: str, changes: Dict, baseline_elements: List[Dict]) -> Optional[UnifiedChangesOutput]:
        try:
            logger.info(f"Processing document {file_path} for any element type...")
            old_content, new_content = changes.get("old_content", ""), changes.get("new_content", "")
            if not new_content and not old_content: return None

            raw_parser = JsonOutputParser(pydantic_object=RawUnifiedChangeDetectionOutput)
            raw_system_prompt = raw_unified_change_identification_system_prompt()
            raw_human_prompt = raw_unified_change_identification_human_prompt(old_content, new_content, file_path)
            
            identification_result = await self.llm_client.generate_response(
                prompt=raw_human_prompt,
                system_message=raw_system_prompt + "\n" + raw_parser.get_format_instructions(), 
                output_format="json", 
                temperature=0.1
            )
            detected_changes = identification_result.content["detected_changes"]
            logger.info(f"Detected changes from {file_path}: {detected_changes}")
            
            if not detected_changes: return None

            relevant_elements = [el for el in baseline_elements if re.match(r'^(?:REQ|DE)-' + re.escape(file_path), el.get('id', ''))]
            logger.info(f"Relevant elements from {file_path}: {relevant_elements}")            
            recon_parser = JsonOutputParser(pydantic_object=UnifiedChangesOutput)
            recon_system_prompt = unified_reconciliation_system_prompt()
            recon_human_prompt = unified_reconciliation_human_prompt([c.dict() for c in detected_changes], relevant_elements)
            
            reconciliation_result = await self.llm_client.generate_response(
                prompt=recon_human_prompt,
                system_message=recon_system_prompt + "\n" + recon_parser.get_format_instructions(),
                output_format="json", 
                temperature=0.1
            )
            logger.info(f"Reconciliation result from {file_path}: {reconciliation_result.content}")
            return reconciliation_result.content
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}")
            return None

    async def _analyze_document_changes(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        logger.info("Analyzing all changed documentation files for any element types...")
        state["current_step"] = "analyzing_documents"
        
        all_baseline_elements = [de.dict() for de in state["baseline_map"].design_elements] + \
                                [req.dict() for req in state["baseline_map"].requirements]

        tasks = [
            self._process_single_document_for_any_element(file_path, changes, all_baseline_elements)
            for file_path, changes in state["changed_docs"].items()
        ]
        results = await asyncio.gather(*tasks)

        for result in results:
            if result:
                state["new_elements"].extend(result.added)
                state["modified_elements"].extend(result.modified)
                state["deleted_elements"].extend(result.deleted)

        logger.info(f"Analysis complete. Found {len(state['new_elements'])} new, {len(state['modified_elements'])} modified, and {len(state['deleted_elements'])} total elements.")
        return state

    async def _update_traceability_mappings(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        logger.info("Skipping traceability mapping updates in this version.")
        return state

    async def _save_baseline_map_update(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        logger.info("Applying all changes and saving the updated baseline map.")
        # Placeholder for actual update logic
        logger.info("Skipping save in this version.")
        state["current_step"] = "completed"
        return state

def create_baseline_map_updater(llm_client: Optional[DocurecoLLMClient] = None,
                               baseline_map_repo: Optional[BaselineMapRepository] = None) -> BaselineMapUpdaterWorkflow:
    return BaselineMapUpdaterWorkflow(llm_client, baseline_map_repo)

__all__ = ["BaselineMapUpdaterWorkflow", "BaselineMapUpdaterState", "create_baseline_map_updater"] 