"""
Baseline Map Updater Workflow for Docureco Agent
Updates baseline traceability maps based on repository changes, following a structure
similar to the BaselineMapCreatorWorkflow.
"""

import logging
import sys
import os
import asyncio
from typing import Dict, Any, List, Optional, Union, Set, Coroutine
import httpx
import base64
import re
from langchain_core.output_parsers import JsonOutputParser
from itertools import islice

# Add parent directories to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, root_dir)

from langgraph.graph import StateGraph, END
from agent.llm.llm_client import DocurecoLLMClient, create_llm_client
from agent.database.baseline_map_repository import BaselineMapRepository
from agent.models.docureco_models import BaselineMapModel, RequirementModel, DesignElementModel, CodeComponentModel, TraceabilityLinkModel
from .prompts import (
    raw_unified_change_identification_system_prompt,
    raw_unified_change_identification_human_prompt,
    unified_reconciliation_system_prompt,
    unified_reconciliation_human_prompt,
    document_link_creation_system_prompt,
    document_link_creation_human_prompt,
    design_code_links_system_prompt,
    design_code_links_human_prompt
)
from .models import (
    UnifiedChangesOutput,
    RawUnifiedChangeDetectionOutput,
    LinkFindingOutput,
    AddedElement,
    ModifiedElement,
    DeletedElement
)

logger = logging.getLogger(__name__)
BaselineMapUpdaterState = Dict[str, Any]

def batched(iterable, n):
    """Batch data into tuples of length n. The last batch may be shorter."""
    it = iter(iterable)
    while True:
        batch = tuple(islice(it, n))
        if not batch:
            return
        yield batch

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
        workflow.add_conditional_edges("fetch_changed_files_content", lambda s: "analyze_document_changes" if not s.get("error") else END)
        workflow.add_edge("analyze_document_changes", "update_traceability_mappings")
        workflow.add_edge("update_traceability_mappings", "save_baseline_map_update")
        workflow.add_edge("save_baseline_map_update", END)
        return workflow

    async def execute(self, repository: str, branch: str, commit_sha: str) -> BaselineMapUpdaterState:
        """Executes the baseline map update workflow."""
        initial_state = {
            "repository": repository, "branch": branch, "commit_sha": commit_sha,
            "baseline_map": None, "changed_docs": {}, "changed_code": {},
            "changes_by_file": {}, "newly_created_links": [], "current_step": "initializing",
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
        repo, commit_sha, github_token = state["repository"], state["commit_sha"], os.getenv("GITHUB_TOKEN")
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
                    status = file_info["status"]
                    change_data = {"old_content": "", "new_content": "", "status": status}
                    
                    if status in ["added", "modified"]:
                        change_data["new_content"] = await self._get_file_content_from_api(client, file_info["contents_url"])
                    if parent_sha and status in ["modified", "deleted"]:
                        old_content_url = f"https://api.github.com/repos/{repo}/contents/{file_path}?ref={parent_sha}"
                        change_data["old_content"] = await self._get_file_content_from_api(client, old_content_url)

                    if any(p in file_path for p in doc_patterns):
                        state["changed_docs"][file_path] = change_data
                    else:
                        state["changed_code"][file_path] = change_data
        except httpx.HTTPStatusError as e:
            state["error"] = f"GitHub API request failed: {e}"
        return state

    async def _analyze_document_changes(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        logger.info("Analyzing all changed documentation files...")
        
        state["current_step"] = "analyzing_documents"
        baseline_elements = [de.dict() for de in state["baseline_map"].design_elements] + \
                            [req.dict() for req in state["baseline_map"].requirements]
        
        tasks = [self._llm_process_single_document(file_path, changes, baseline_elements) for file_path, changes in state["changed_docs"].items()]
        results = await asyncio.gather(*tasks)
        
        state["changes_by_file"] = {fp: res for fp, res in zip(state["changed_docs"].keys(), results) if res}
        logger.info(f"Analysis complete. Found changes in {len(state['changes_by_file'])} files.")
        return state
    
    async def _llm_process_single_document(self, file_path: str, changes: Dict, baseline_elements: List[Dict]) -> Optional[UnifiedChangesOutput]:
        try:
            old_content, new_content = changes.get("old_content", ""), changes.get("new_content", "")
            if not new_content and not old_content: return None
            
            raw_parser = JsonOutputParser(pydantic_object=RawUnifiedChangeDetectionOutput)
            raw_system_prompt = raw_unified_change_identification_system_prompt()
            raw_human_prompt = raw_unified_change_identification_human_prompt(old_content, new_content, file_path)
            
            identification_result = await self.llm_client.generate_response(prompt=raw_human_prompt, system_message=raw_system_prompt + "\n" + raw_parser.get_format_instructions(), output_format="json", temperature=0.1)
            detected_changes = identification_result.content.get("detected_changes", [])
            if not detected_changes: return None

            relevant_elements = [el for el in baseline_elements if el.get('file_path') == file_path]
            recon_parser = JsonOutputParser(pydantic_object=UnifiedChangesOutput)
            recon_system_prompt = unified_reconciliation_system_prompt()
            recon_human_prompt = unified_reconciliation_human_prompt(detected_changes, relevant_elements)
            
            reconciliation_result = await self.llm_client.generate_response(prompt=recon_human_prompt, system_message=recon_system_prompt + "\n" + recon_parser.get_format_instructions(), output_format="json", temperature=0.0)
            return UnifiedChangesOutput(**reconciliation_result.content)
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}")
            return None
    
    def _delete_all_associated_links(self, baseline_map: BaselineMapModel, ref_ids_to_clear: Set[str], code_paths_to_clear: Set[str]):
        """Deletes all links associated with a set of document reference IDs or code paths."""
        if not ref_ids_to_clear and not code_paths_to_clear:
            return

        initial_link_count = len(baseline_map.traceability_links)
        code_ids_to_clear = {c.id for c in baseline_map.code_components if c.path in code_paths_to_clear}

        baseline_map.traceability_links = [
            link for link in baseline_map.traceability_links 
            if (link.source_id not in ref_ids_to_clear and link.target_id not in ref_ids_to_clear)
            and (link.target_id not in code_ids_to_clear)
        ]
        deleted_count = initial_link_count - len(baseline_map.traceability_links)
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} associated links.")

    async def _run_link_creation_in_batches(self, candidates: List[Dict], targets: List[Dict], link_creation_coro: Coroutine, batch_size: int = 5):
        """Generic function to run link creation tasks in parallel batches."""
        all_new_links = []
        for batch in batched(candidates, batch_size):
            tasks = [link_creation_coro(c, targets) for c in batch]
            batch_results = await asyncio.gather(*tasks)
            for result_list in batch_results:
                all_new_links.extend(result_list)
        return all_new_links

    async def _llm_find_document_links(self, source_element: Dict, all_targets: List[Dict]) -> List[TraceabilityLinkModel]:
        try:
            parser = JsonOutputParser(pydantic_object=LinkFindingOutput)
            system_prompt = document_link_creation_system_prompt()
            human_prompt = document_link_creation_human_prompt(source_element, all_targets)
            response = await self.llm_client.generate_response(prompt=human_prompt, system_message=system_prompt + "\n" + parser.get_format_instructions(), output_format="json", temperature=0.0)
            
            source_type = "Requirement" if source_element.get('id', '').startswith("REQ-") else "DesignElement"
            source_ref_id = source_element.get('reference_id')

            return [TraceabilityLinkModel(id=f"TEMP-L", source_type=source_type, source_id=source_ref_id, target_id=link.target_id, relationship_type=link.relationship_type) for link in parser.parse(response.content).links]
        except Exception as e:
            logger.error(f"Error finding document links for element {source_element.get('reference_id')}: {e}")
            return []

    async def _llm_find_d2c_links(self, source_element: Dict, all_code_targets: List[Dict]) -> List[TraceabilityLinkModel]:
        try:
            parser = JsonOutputParser(pydantic_object=LinkFindingOutput)
            system_prompt = design_code_links_system_prompt()
            human_prompt = design_code_links_human_prompt(source_element, all_code_targets)
            response = await self.llm_client.generate_response(prompt=human_prompt, system_message=system_prompt + "\n" + parser.get_format_instructions(), output_format="json", temperature=0.0)

            source_ref_id = source_element.get('reference_id')

            return [TraceabilityLinkModel(id=f"TEMP-L", source_type="DesignElement", source_id=source_ref_id, target_id=link.target_id, relationship_type=link.relationship_type) for link in parser.parse(response.content).links]
        except Exception as e:
            logger.error(f"Error finding D2C links for element {source_element.get('reference_id')}: {e}")
            return []

    async def _update_traceability_mappings(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        logger.info("Updating all traceability mappings...")
        state["current_step"] = "updating_mappings"
        
        baseline_map: BaselineMapModel = state["baseline_map"]
        changes_by_file: Dict[str, UnifiedChangesOutput] = state.get("changes_by_file", {})     # documentation changes per file path
        changed_code: Dict[str, Dict] = state.get("changed_code", {})

        # Clear all links associated with deleted or modified elements
        doc_ref_ids_to_clear = {el.reference_id for changes in changes_by_file.values() for el in changes.deleted + changes.modified}
        code_paths_to_clear = {path for path, change in changed_code.items() if change['status'] in ['modified', 'deleted']}
        self._delete_all_associated_links(baseline_map, doc_ref_ids_to_clear, code_paths_to_clear)

        # Identify candidates for link creation
        req_candidates = []
        design_candidates = []

        def get_element_by_ref_id(file_path: str, ref_id: str):
            """Finds an element by its reference_id and file_path encoded in the main ID."""
            for el in baseline_map.requirements + baseline_map.design_elements:
                if el.reference_id == ref_id:
                    # ID format is 'TYPE-filepath-NUMBER'
                    match = re.match(r'^(?:REQ|DE)-(.+)-\d+$', el.id)
                    if match:
                        element_file_path = match.group(1)
                        if element_file_path == file_path:
                            return el
            return None


        for file_path, changes in changes_by_file.items():
            for el in changes.added:
                # For new items, details already contain all necessary fields for a new model instance
                candidate = el.details.copy()
                candidate['file_path'] = file_path # Ensure file_path is present
                if el.element_type == "Requirement":
                    req_candidates.append(candidate)
                else:
                    design_candidates.append(candidate)
            
            for el in changes.modified:
                # Find the original element to get its full context
                original_element = get_element_by_ref_id(file_path, el.reference_id)
                if original_element:
                    # Create a complete, updated version of the element for context
                    candidate = original_element.dict()
                    candidate.update(el.changes)
                    if 'id' not in candidate: candidate['id'] = original_element.id
                    
                    # The file_path is implicitly confirmed by get_element_by_ref_id
                    candidate['file_path'] = file_path
                    
                    if el.element_type == "Requirement":
                        req_candidates.append(candidate)
                    else:
                        design_candidates.append(candidate)

        all_doc_targets = [el.dict() for el in baseline_map.requirements + baseline_map.design_elements]
        # Add file_path to existing elements for linking context if not present
        for target in all_doc_targets:
            if 'file_path' not in target:
                match = re.match(r'^(?:REQ|DE)-(.+)-\d+$', target['id'])
                if match:
                    target['file_path'] = match.group(1)
                else:
                    target['file_path'] = 'unknown' # Fallback
        
        all_doc_targets.extend(req_candidates)
        all_doc_targets.extend(design_candidates)
        
        # Prepare code targets, updating content for modified files and adding new files
        code_content_map = {path: change['new_content'] for path, change in changed_code.items() if 'new_content' in change}
        all_code_targets = [c.dict() for c in baseline_map.code_components]
        for target in all_code_targets:
            if target['path'] in code_content_map:
                target['content'] = code_content_map[target['path']]
        for path, change in changed_code.items():
            if change['status'] == 'added':
                all_code_targets.append({"id": f"TEMP-{path}", "path": path, "name": os.path.basename(path), "content": change.get('new_content', '')})

        # Create links for document elements
        logger.info(f"Creating R2D links for {len(req_candidates)} and D2D links for {len(design_candidates)} candidates...")
        doc_candidates = req_candidates + design_candidates
        new_doc_links = await self._run_link_creation_in_batches(doc_candidates, all_doc_targets, self._llm_find_document_links)
        
        logger.info(f"Creating D2C links for {len(design_candidates)} candidates...")
        new_d2c_links = await self._run_link_creation_in_batches(design_candidates, all_code_targets, self._llm_find_d2c_links)
        
        state['newly_created_links'] = new_doc_links + new_d2c_links
        logger.info(f"Generated {len(state['newly_created_links'])} new traceability links in total.")
        return state

    async def _save_baseline_map_update(self, state: BaselineMapUpdaterState) -> BaselineMapUpdaterState:
        logger.info("Applying inventory changes and saving the updated baseline map.")
        state['current_step'] = 'saving_map'
        
        baseline_map: BaselineMapModel = state["baseline_map"]
        changes_by_file: Dict[str, UnifiedChangesOutput] = state.get("changes_by_file", {})
        changed_code: Dict[str, Dict] = state.get("changed_code", {})
        
        # --- Step 1: Update Element and Code Component Inventory ---
        deleted_doc_ids = set()

        def get_element_by_ref_id(file_path: str, ref_id: str):
            """Finds an element by its reference_id and file_path encoded in the main ID."""
            for el in baseline_map.requirements + baseline_map.design_elements:
                if el.reference_id == ref_id:
                    # ID format is 'TYPE-filepath-NUMBER'
                    match = re.match(r'^(?:REQ|DE)-(.+)-\d+$', el.id)
                    if match:
                        element_file_path = match.group(1)
                        if element_file_path == file_path:
                            return el
            return None

        for file_path, changes in changes_by_file.items():
            for el in changes.deleted:
                element = get_element_by_ref_id(file_path, el.reference_id)
                if element: deleted_doc_ids.add(element.id)
            for el in changes.modified:
                element = get_element_by_ref_id(file_path, el.reference_id)
                if element:
                    for field, value in el.changes.items():
                        if hasattr(element, field): setattr(element, field, value)
        
        baseline_map.requirements = [r for r in baseline_map.requirements if r.id not in deleted_doc_ids]
        baseline_map.design_elements = [d for d in baseline_map.design_elements if d.id not in deleted_doc_ids]

        for file_path, changes in changes_by_file.items():
            max_req = max([int(r.id.split('-')[-1]) for r in baseline_map.requirements if r.file_path == file_path] or [0])
            max_de = max([int(d.id.split('-')[-1]) for d in baseline_map.design_elements if d.file_path == file_path] or [0])
            for el in changes.added:
                details, el_type = el.details, el.element_type
                details['file_path'] = file_path
                if el_type == "Requirement":
                    max_req += 1; details['id'] = f"REQ-{file_path}-{max_req:03d}"
                    baseline_map.requirements.append(RequirementModel(**details))
                else:
                    max_de += 1; details['id'] = f"DE-{file_path}-{max_de:03d}"
                    baseline_map.design_elements.append(DesignElementModel(**details))

        deleted_code_paths = {path for path, change in changed_code.items() if change['status'] == 'deleted'}
        baseline_map.code_components = [c for c in baseline_map.code_components if c.path not in deleted_code_paths]
        max_cc_id = max([int(c.id.split('-')[-1]) for c in baseline_map.code_components if c.id.startswith("CC-")] or [0])
        for path, change in changed_code.items():
            if change['status'] == 'added':
                max_cc_id += 1
                baseline_map.code_components.append(CodeComponentModel(id=f"CC-{max_cc_id:03d}", path=path, name=os.path.basename(path), type=os.path.splitext(path)[1]))

        # --- Step 2: Add the newly created links ---
        new_links: List[TraceabilityLinkModel] = state.get('newly_created_links', [])
        if new_links:
            max_link_id = max([int(l.id.split('-')[-1]) for l in baseline_map.traceability_links if l.id.startswith("L-")] or [0])
            all_elements_map = {el.reference_id: el for el in baseline_map.requirements + baseline_map.design_elements}
            all_code_map = {c.id: c for c in baseline_map.code_components}
            
            for link in new_links:
                max_link_id += 1; link.id = f"L-{max_link_id:04d}"
                target_el = all_elements_map.get(link.target_id) or all_code_map.get(link.target_id)
                if target_el:
                    if isinstance(target_el, RequirementModel): link.target_type = "Requirement"
                    elif isinstance(target_el, DesignElementModel): link.target_type = "DesignElement"
                    else: link.target_type = "CodeComponent"
                else: link.target_type = "Unresolved"
            
            baseline_map.traceability_links.extend(new_links)

        logger.info("Skipping saving the updated baseline map.")
        # # --- Step 3: Save Final Map ---
        # if await self.baseline_map_repo.save_baseline_map(baseline_map):
        #     state["current_step"] = "completed"
        # else:
        #     state["error"] = "Failed to save the updated baseline map."
        return state

def create_baseline_map_updater(llm_client: Optional[DocurecoLLMClient] = None,
                               baseline_map_repo: Optional[BaselineMapRepository] = None) -> BaselineMapUpdaterWorkflow:
    return BaselineMapUpdaterWorkflow(llm_client, baseline_map_repo)

__all__ = ["BaselineMapUpdaterWorkflow", "BaselineMapUpdaterState", "create_baseline_map_updater"] 