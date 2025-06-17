"""
Baseline Map Creator Workflow for Docureco Agent
Creates baseline traceability maps from repository documentation and code
"""

import asyncio
import logging
import re
import sys
import os
import fnmatch
import base64
import time
from typing import Dict, Any, List, Optional, Set
from pathlib import Path

# Add parent directories to path for absolute imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, root_dir)

from github import Github, GithubException
from github.Repository import Repository
from github.ContentFile import ContentFile

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agent.llm.llm_client import DocurecoLLMClient, create_llm_client
from agent.database import BaselineMapRepository
from agent.models.docureco_models import (
    BaselineMapModel, RequirementModel, DesignElementModel, 
    CodeComponentModel, TraceabilityLinkModel
)

logger = logging.getLogger(__name__)

BaselineMapCreatorState = Dict[str, Any]

class BaselineMapCreatorWorkflow:
    """
    LangGraph workflow for creating baseline traceability maps from repository documentation and code.
    
    This workflow implements the Baseline Map Creator component which analyzes:
    1. Software Requirements Specification (SRS) documents
    2. Software Design Documents (SDD) 
    3. Source code files
    4. Creates traceability mappings between elements
    
    The workflow prioritizes SDD processing first since it often contains explicit traceability matrices.
    """
    
    def __init__(self, 
                 llm_client: Optional[DocurecoLLMClient] = None,
                 baseline_map_repo: Optional[BaselineMapRepository] = None):
        """
        Initialize baseline map creator workflow
        
        Args:
            llm_client: Optional LLM client for document parsing
            baseline_map_repo: Optional repository for data persistence
        """
        self.llm_client = llm_client or create_llm_client()
        self.baseline_map_repo = baseline_map_repo or BaselineMapRepository()
        
        # Initialize GitHub client
        self.github_token = os.getenv("GITHUB_TOKEN")
        if not self.github_token:
            print("No GitHub token provided. Repository scanning will be limited.")
            self.github_client = None
        else:
            self.github_client = Github(self.github_token)
            print("GitHub client initialized")
        
        self.workflow = self._build_workflow()
        self.memory = MemorySaver()
        
        logger.info("Initialized BaselineMapCreatorWorkflow")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow following the SRS, SDD, and Code Mapping process"""
        workflow = StateGraph(BaselineMapCreatorState)
        
        # Add nodes for each major process step (following the diagram flow)
        workflow.add_node("scan_repository", self._scan_repository)
        workflow.add_node("identify_design_elements", self._identify_design_elements)
        workflow.add_node("design_to_design_mapping", self._design_to_design_mapping)
        workflow.add_node("design_to_code_mapping", self._design_to_code_mapping)
        workflow.add_node("identify_requirements", self._identify_requirements)
        workflow.add_node("requirements_to_design_mapping", self._requirements_to_design_mapping)
        workflow.add_node("save_baseline_map", self._save_baseline_map)
        
        # Define workflow edges following the diagram
        workflow.set_entry_point("scan_repository")
        workflow.add_edge("scan_repository", "identify_design_elements")
        workflow.add_edge("identify_design_elements", "design_to_design_mapping")  
        workflow.add_edge("design_to_design_mapping", "design_to_code_mapping")
        workflow.add_edge("design_to_code_mapping", "identify_requirements")
        workflow.add_edge("identify_requirements", "requirements_to_design_mapping")
        workflow.add_edge("requirements_to_design_mapping", "save_baseline_map")
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
        initial_state = {
            "repository": repository,
            "branch": branch,
            "srs_content": {},
            "sdd_content": {},
            "code_files": [],
            "requirements": [],
            "design_elements": [],
            "code_components": [],
            "design_to_design_links": [],
            "design_to_code_links": [],
            "requirements_to_design_links": [],
            "traceability_links": [],
            "current_step": "initializing",
            "errors": [],
            "processing_stats": {}
        }
        
        try:
            # Check if baseline map already exists
            existing_map = await self.baseline_map_repo.get_baseline_map(repository, branch)
            force_recreate = os.getenv("FORCE_RECREATE").lower() == "true"
            print(f"Baseline map already exists for {repository}:{branch}")
            if existing_map and not force_recreate:
                print("Baseline map exists. Exiting...")
                return initial_state
            
            # Compile and run workflow
            app = self.workflow.compile(checkpointer=self.memory)
            config = {"configurable": {"thread_id": f"baseline_{repository.replace('/', '_')}_{branch}"}}
            
            final_state = await app.ainvoke(initial_state, config=config)
            
            print(f"Baseline map creation completed for {repository}:{branch}")
            return final_state
            
        except Exception as e:
            print(f"Baseline map creation failed: {str(e)}")
            initial_state["errors"].append(str(e))
            raise
    
    async def _scan_repository(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Scan repository for documentation and code files
        """
        print(f"Scanning repository {state['repository']}:{state['branch']}")
        state["current_step"] = "scanning_repository"
        
        try:
            # In a full implementation, this would use GitHub API to fetch files
            # For now, we'll simulate the repository scanning
            
            # Look for SDD files first (priority since they contain traceability matrices)
            sdd_patterns = [
                "design.md", "sdd.md", "software-design.md", "architecture.md",
                "docs/design.md", "docs/sdd.md", "docs/architecture.md",
                "traceability.md", "traceability-matrix.md"
            ]
            
            # Look for SRS files (common patterns)
            srs_patterns = [
                "requirements.md", "srs.md", "software-requirements.md",
                "docs/requirements.md", "docs/srs.md", "documentation/requirements.md"
            ]
            
            # Look for code files (common patterns)
            code_patterns = ["*.py", "*.java", "*.js", "*.ts", "*.cpp", "*.h"]
            
            # Scan SDD first (contains traceability matrix)
            print("Scanning SDD files (priority for traceability matrix)...")
            state["sdd_content"] = await self._fetch_documentation_files(state["repository"], sdd_patterns, state["branch"])
            
            # Then scan SRS and code files
            print("Scanning SRS and code files...")
            state["srs_content"] = await self._fetch_documentation_files(state["repository"], srs_patterns, state["branch"])
            state["code_files"] = await self._fetch_code_files(state["repository"], code_patterns, state["branch"])
            
            print(f"Found {len(state['sdd_content'])} SDD files, {len(state['srs_content'])} SRS files, {len(state['code_files'])} code files")
            
        except Exception as e:
            error_msg = f"Error scanning repository: {str(e)}"
            state["errors"].append(error_msg)
            raise e
        
        return state
    
    async def _identify_design_elements(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Identify design elements from SDD documentation using LLM
        SDD is processed first as it contains the traceability matrix between design elements and requirements
        """
        print("Identifying design elements from SDD")
        state["current_step"] = "identifying_design_elements"
        
        try:
            design_elements = []
            elem_counter = 1
            
            for file_path, content in state["sdd_content"].items():
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
            
            state["design_elements"] = design_elements
            state["processing_stats"]["design_elements_count"] = len(design_elements)
            print(f"Identified {len(design_elements)} design elements")
            
        except Exception as e:
            error_msg = f"Error identifying design elements: {str(e)}"
            print(error_msg)
            state["errors"].append(error_msg)
        
        return state
    
    async def _design_to_design_mapping(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Create mappings between design elements (internal relationships)
        """
        print("Creating design-to-design mappings")
        state["current_step"] = "design_to_design_mapping"
        
        try:
            design_to_design_links = []
            link_counter = 1
            
            # Analyze relationships between design elements using LLM
            if len(state["design_elements"]) > 1:
                links_data = await self._create_design_element_relationships(state["design_elements"])
                
                for link_data in links_data:
                    link = TraceabilityLinkModel(
                        id=f"DD-{link_counter:03d}",
                        source_type="DesignElement",
                        source_id=link_data["source_id"],
                        target_type="DesignElement", 
                        target_id=link_data["target_id"],
                        relationship_type=link_data["relationship_type"]
                    )
                    design_to_design_links.append(link)
                    link_counter += 1
            
            state["design_to_design_links"] = design_to_design_links
            state["processing_stats"]["design_to_design_links_count"] = len(design_to_design_links)
            print(f"Created {len(design_to_design_links)} design-to-design mappings")
            
        except Exception as e:
            error_msg = f"Error creating design-to-design mappings: {str(e)}"
            print(error_msg)
            state["errors"].append(error_msg)
        
        return state
    
    async def _design_to_code_mapping(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Create mappings between design elements and code components
        """
        print("Creating design-to-code mappings")
        state["current_step"] = "design_to_code_mapping"
        
        try:
            # Create code components from file paths (simplified approach)
            code_components = []
            comp_counter = 1
            
            for file_info in state["code_files"]:
                file_path = file_info.get("path", "")
                
                if not file_path:
                    continue
                
                # Create a code component for each file path
                code_component = CodeComponentModel(
                    id=f"CC-{comp_counter:03d}",
                    path=file_path,
                    type="File",
                    name=Path(file_path).name  # Use full filename instead of stem
                )
                code_components.append(code_component)
                comp_counter += 1
            
            state["code_components"] = code_components
            state["processing_stats"]["code_components_count"] = len(code_components)
            
            # Create design-to-code links using simple matching
            design_to_code_links = []
            link_counter = 1
            
            links_data = await self._create_design_code_links(state["design_elements"], code_components)
            
            for link_data in links_data:
                link = TraceabilityLinkModel(
                    id=f"DC-{link_counter:03d}",
                    source_type="DesignElement",
                    source_id=link_data["source_id"],
                    target_type="CodeComponent",
                    target_id=link_data["target_id"],
                    relationship_type=link_data["relationship_type"]
                )
                design_to_code_links.append(link)
                link_counter += 1
            
            state["design_to_code_links"] = design_to_code_links
            state["processing_stats"]["design_to_code_links_count"] = len(design_to_code_links)
            print(f"Created {len(design_to_code_links)} design-to-code mappings")
            
        except Exception as e:
            error_msg = f"Error creating design-to-code mappings: {str(e)}"
            print(error_msg)
            state["errors"].append(error_msg)
        
        return state
    
    async def _identify_requirements(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Identify requirements from SRS documentation using LLM
        """
        print("Identifying requirements from SRS")
        state["current_step"] = "identifying_requirements"
        
        try:
            requirements = []
            req_counter = 1
            
            for file_path, content in state["srs_content"].items():
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
            
            state["requirements"] = requirements
            state["processing_stats"]["requirements_count"] = len(requirements)
            print(f"Identified {len(requirements)} requirements")
            
        except Exception as e:
            error_msg = f"Error identifying requirements: {str(e)}"
            print(error_msg)
            state["errors"].append(error_msg)
        
        return state
    
    async def _requirements_to_design_mapping(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Create mappings between requirements and design elements
        Uses the traceability matrix from SDD documentation
        """
        print("Creating requirements-to-design mappings")
        state["current_step"] = "requirements_to_design_mapping"
        
        try:
            requirements_to_design_links = []
            link_counter = 1
            
            # Extract traceability matrix from SDD and create requirement-design links
            req_to_design_links = await self._create_requirement_design_links_from_sdd(
                state["requirements"], state["design_elements"], state["sdd_content"]
            )
            
            for link_data in req_to_design_links:
                link = TraceabilityLinkModel(
                    id=f"RD-{link_counter:03d}",
                    source_type="Requirement",
                    source_id=link_data["source_id"],
                    target_type="DesignElement",
                    target_id=link_data["target_id"],
                    relationship_type=link_data["relationship_type"]
                )
                requirements_to_design_links.append(link)
                link_counter += 1
            
            state["requirements_to_design_links"] = requirements_to_design_links
            state["processing_stats"]["requirements_to_design_links_count"] = len(requirements_to_design_links)
            
            # Combine all traceability links
            state["traceability_links"] = (
                state["design_to_design_links"] + 
                state["design_to_code_links"] + 
                state["requirements_to_design_links"]
            )
            state["processing_stats"]["total_traceability_links_count"] = len(state["traceability_links"])
            
            print(f"Created {len(requirements_to_design_links)} requirements-to-design mappings")
            print(f"Total traceability links: {len(state['traceability_links'])}")
            
        except Exception as e:
            error_msg = f"Error creating requirements-to-design mappings: {str(e)}"
            print(error_msg)
            state["errors"].append(error_msg)
        
        return state
    
    async def _save_baseline_map(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Save baseline map to database
        """
        print("Saving baseline map to database")
        state["current_step"] = "saving_baseline_map"
        
        try:
            # Create baseline map model
            baseline_map = BaselineMapModel(
                repository=state["repository"],
                branch=state["branch"],
                requirements=state["requirements"],
                design_elements=state["design_elements"],
                code_components=state["code_components"],
                traceability_links=state["traceability_links"]
            )
            
            # Save to database
            success = await self.baseline_map_repo.save_baseline_map(baseline_map)
            
            if success:
                print(f"Successfully saved baseline map for {state['repository']}:{state['branch']}")
                state["current_step"] = "completed"
            else:
                error_msg = "Failed to save baseline map to database"
                print(error_msg)
                state["errors"].append(error_msg)
            
        except Exception as e:
            error_msg = f"Error saving baseline map: {str(e)}"
            print(error_msg)
            state["errors"].append(error_msg)
        
        return state
    
    # Helper methods for GitHub API integration
    async def _fetch_documentation_files(self, repository: str, patterns: List[str], branch: str) -> Dict[str, str]:
        """Fetch documentation files from repository using GitHub API"""
        documentation_files = {}
        
        try:
            # Get repository
            repo = self.github_client.get_repo(repository)
            print(f"Fetching documentation files from {repository}:{branch}")
            
            # Search for documentation files
            matching_files = await self._find_files_by_patterns(repo, patterns, branch)
            if len(matching_files) == 0:
                raise Exception(f"No documentation files found for {repository}:{branch} with patterns {patterns}")
            
            # Fetch content for each matching file
            for file_path in matching_files:
                try:
                    content = await self._get_file_content(repo, file_path, branch)
                    if content:
                        documentation_files[file_path] = content
                        print(f"Fetched documentation file: {file_path}")
                except Exception as e:
                    print(f"Failed to fetch content for {file_path}: {str(e)}")
                    raise e
            
        except Exception as e:
            print(f"Error fetching documentation files: {str(e)}")
            raise e
        
        return documentation_files
    
    async def _fetch_code_files(self, repository: str, patterns: List[str], branch: str) -> List[Dict[str, Any]]:
        """Fetch code files from repository using GitHub API"""
        code_files = []
        
        if not self.github_client:
            print("GitHub client not available. Returning empty code files.")
            return code_files
        
        try:
            # Get repository
            repo = self.github_client.get_repo(repository)
            print(f"Fetching code files from {repository}:{branch}")
            
            # Search for code files
            matching_files = await self._find_files_by_patterns(repo, patterns, branch)
            
            # Create file info for each matching file (without content for performance)
            for file_path in matching_files:
                code_files.append({
                    "path": file_path,
                    "content": ""  # Placeholder for file content
                })
                print(f"Found code file: {file_path}")
            
            print(f"Found {len(code_files)} code files")
            
        except Exception as e:
            print(f"Error fetching code files: {str(e)}")
        
        return code_files
    
    async def _find_files_by_patterns(self, repo: Repository, patterns: List[str], branch: str) -> List[str]:
        """Find files in repository matching the given patterns"""
        matching_files = []
        
        try:
            # Check rate limit before making API calls
            await self._check_rate_limit()
            
            # Get all files in the repository
            contents = repo.get_contents("", ref=branch)
            
            # Recursively search through directory structure
            matching_files = await self._search_files_recursive(repo, contents, patterns, branch)
            
        except GithubException as e:
            if e.status == 403:
                print("GitHub API rate limit exceeded. Please wait and try again.")
            elif e.status == 404:
                print(f"Repository or branch not found: {repo.full_name}:{branch}")
            else:
                print(f"GitHub API error: {str(e)}")
        except Exception as e:
            print(f"Error searching files: {str(e)}")
        
        return matching_files
    
    async def _search_files_recursive(self, repo: Repository, contents: List[ContentFile], 
                                    patterns: List[str], branch: str, current_path: str = "", 
                                    max_depth: int = 5, current_depth: int = 0) -> List[str]:
        """Recursively search for files matching patterns with depth limit"""
        matching_files = []
        
        # Prevent infinite recursion and limit API calls
        if current_depth > max_depth:
            print(f"Maximum search depth ({max_depth}) reached at {current_path}")
            return matching_files
        
        for content in contents:
            full_path = f"{current_path}/{content.path}" if current_path else content.path
            
            if content.type == "dir":
                # Skip common directories that usually don't contain documentation
                skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'env', 
                           'target', 'build', 'dist', '.next', 'coverage'}
                
                if content.name.lower() in skip_dirs:
                    print(f"Skipping directory: {content.path}")
                    continue
                
                # Recursively search directories
                try:
                    # Check rate limit before each directory access
                    await self._check_rate_limit()
                    
                    sub_contents = repo.get_contents(content.path, ref=branch)
                    sub_matches = await self._search_files_recursive(
                        repo, sub_contents, patterns, branch, current_path, max_depth, current_depth + 1
                    )
                    matching_files.extend(sub_matches)
                    
                except GithubException as e:
                    if e.status == 403:
                        print(f"Rate limit hit while accessing {content.path}")
                        await asyncio.sleep(1)  # Brief pause
                    else:
                        print(f"Failed to access directory {content.path}: {str(e)}")
                except Exception as e:
                    print(f"Failed to access directory {content.path}: {str(e)}")
            else:
                # Check if file matches any pattern
                if self._matches_patterns(content.path, patterns):
                    matching_files.append(content.path)
                    print(f"Found matching file: {content.path}")
        
        return matching_files
    
    def _matches_patterns(self, file_path: str, patterns: List[str]) -> bool:
        """Check if file path matches any of the given patterns"""
        for pattern in patterns:
            # Handle glob patterns (*.py) and exact matches
            if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(file_path.lower(), pattern.lower()):
                return True
            
            # Also check just the filename
            filename = os.path.basename(file_path)
            if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(filename.lower(), pattern.lower()):
                return True
        
        return False
    
    async def _get_file_content(self, repo: Repository, file_path: str, branch: str) -> Optional[str]:
        """Get the content of a specific file from the repository"""
        try:
            file_content = repo.get_contents(file_path, ref=branch)
            
            # Handle single file (not a list)
            if isinstance(file_content, list):
                if len(file_content) > 0:
                    file_content = file_content[0]
                else:
                    return None
            
            # Decode content
            if file_content.encoding == "base64":
                content = base64.b64decode(file_content.content).decode('utf-8')
            else:
                content = file_content.content
            
            return content
            
        except Exception as e:
            print(f"Failed to get content for {file_path}: {str(e)}")
            return None
    
    async def _check_rate_limit(self):
        """Check GitHub API rate limit and wait if necessary"""
        if not self.github_client:
            return
        
        try:
            rate_limit = self.github_client.get_rate_limit()
            core_remaining = rate_limit.core.remaining
            
            if core_remaining < 10:  # Less than 10 requests remaining
                reset_time = rate_limit.core.reset.timestamp()
                wait_time = max(0, reset_time - time.time())
                
                if wait_time > 0:
                    print(f"GitHub API rate limit low ({core_remaining} remaining). Waiting {wait_time:.1f} seconds...")
                    await asyncio.sleep(wait_time)
            
        except Exception as e:
            print(f"Failed to check rate limit: {str(e)}")
    
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
    
    async def _create_design_element_relationships(self, design_elements: List[DesignElementModel]) -> List[Dict[str, Any]]:
        """Create relationships between design elements using simple heuristics"""
        relationships = []
        
        try:
            # Simple placeholder implementation - would use LLM analysis in production
            if len(design_elements) >= 2:
                relationships.append({
                    "source_id": design_elements[0].id,
                    "target_id": design_elements[1].id,
                    "relationship_type": "depends_on"
                })
            
        except Exception as e:
            print(f"Failed to create design element relationships: {str(e)}")
        
        return relationships
    
    async def _create_requirement_design_links_from_sdd(self, requirements: List[RequirementModel], 
                                                       design_elements: List[DesignElementModel],
                                                       sdd_content: Dict[str, str]) -> List[Dict[str, Any]]:
        """Create links between requirements and design elements using SDD traceability matrix"""
        links = []
        
        try:
            # Try to parse explicit traceability matrix from SDD
            explicit_links = await self._parse_traceability_matrix_from_sdd(sdd_content, requirements, design_elements)
            links.extend(explicit_links)
            
            # Simple placeholder implementation if no explicit matrix found
            if not links and requirements and design_elements:
                links.append({
                    "source_id": requirements[0].id,
                    "target_id": design_elements[0].id,
                    "relationship_type": "implements"
                })
            
        except Exception as e:
            print(f"Failed to create requirement-design links: {str(e)}")
        
        return links
    
    async def _create_design_code_links(self, design_elements: List[DesignElementModel], code_components: List[CodeComponentModel]) -> List[Dict[str, Any]]:
        """Create links between design elements and code components using simple name matching"""
        links = []
        
        try:
            # Simple placeholder implementation - would use LLM analysis in production
            if design_elements and code_components:
                links.append({
                    "source_id": design_elements[0].id,
                    "target_id": code_components[0].id,
                    "relationship_type": "realizes"
                })
            
        except Exception as e:
            print(f"Failed to create design-code links: {str(e)}")
        
        return links
    

    
    async def _parse_traceability_matrix_from_sdd(self, sdd_content: Dict[str, str], 
                                                 requirements: List[RequirementModel],
                                                 design_elements: List[DesignElementModel]) -> List[Dict[str, Any]]:
        """Parse explicit traceability matrix from SDD content"""
        # Placeholder - would implement parsing of traceability tables/matrices in SDD
        return []
    


# Factory function
def create_baseline_map_creator(llm_client: Optional[DocurecoLLMClient] = None,
                               baseline_map_repo: Optional[BaselineMapRepository] = None) -> BaselineMapCreatorWorkflow:
    """
    Factory function to create baseline map creator workflow
    
    Args:
        llm_client: Optional LLM client for document parsing
        baseline_map_repo: Optional repository for data persistence
        
    Returns:
        BaselineMapCreatorWorkflow: Configured workflow
    """
    return BaselineMapCreatorWorkflow(llm_client, baseline_map_repo)

# Export main classes
__all__ = ["BaselineMapCreatorWorkflow", "BaselineMapCreatorState", "create_baseline_map_creator"] 