"""
Initial Baseline Map Creator for Docureco Agent
Creates initial traceability maps by scanning repository documentation and code
"""

import asyncio
import logging
import os
import re
import time
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
from dataclasses import dataclass, field
import fnmatch
import base64

from github import Github, GithubException
from github.Repository import Repository
from github.ContentFile import ContentFile
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..llm.llm_client import DocurecoLLMClient, create_llm_client
from ..llm.embedding_client import DocurecoEmbeddingClient, create_embedding_client
from ..database import BaselineMapRepository
try:
    from ..database import VectorSearchRepository
except ImportError:
    # VectorSearchRepository may not be implemented yet
    VectorSearchRepository = None
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
    srs_content: Dict[str, str] = field(default_factory=dict)
    sdd_content: Dict[str, str] = field(default_factory=dict)
    code_files: List[Dict[str, Any]] = field(default_factory=list)
    
    # Extracted elements
    requirements: List[RequirementModel] = field(default_factory=list)
    design_elements: List[DesignElementModel] = field(default_factory=list)
    code_components: List[CodeComponentModel] = field(default_factory=list)
    
    # Mapping relationships
    design_to_design_links: List[TraceabilityLinkModel] = field(default_factory=list)
    design_to_code_links: List[TraceabilityLinkModel] = field(default_factory=list)
    requirements_to_design_links: List[TraceabilityLinkModel] = field(default_factory=list)
    
    # Combined traceability links
    traceability_links: List[TraceabilityLinkModel] = field(default_factory=list)
    
    # Workflow metadata
    current_step: str = "initializing"
    errors: List[str] = field(default_factory=list)
    processing_stats: Dict[str, int] = field(default_factory=dict)

class BaselineMapCreatorWorkflow:
    """
    LangGraph workflow for creating initial baseline traceability maps
    Implements the Initial Baseline Map Creator component
    """
    
    def __init__(self, 
                 llm_client: Optional[DocurecoLLMClient] = None,
                 embedding_client: Optional[DocurecoEmbeddingClient] = None,
                 baseline_map_repo: Optional[BaselineMapRepository] = None,
                 vector_search_repo: Optional[VectorSearchRepository] = None,
                 github_token: Optional[str] = None):
        """
        Initialize baseline map creator workflow
        
        Args:
            llm_client: Optional LLM client
            embedding_client: Optional embedding client
            baseline_map_repo: Optional baseline map repository
            vector_search_repo: Optional vector search repository
            github_token: Optional GitHub token for API access
        """
        self.llm_client = llm_client or create_llm_client()
        self.embedding_client = embedding_client or create_embedding_client()
        self.baseline_map_repo = baseline_map_repo or BaselineMapRepository()
        self.vector_search_repo = vector_search_repo or (VectorSearchRepository() if VectorSearchRepository else None)
        
        # Initialize GitHub client
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        if not self.github_token:
            logger.warning("No GitHub token provided. Repository scanning will be limited.")
            self.github_client = None
        else:
            self.github_client = Github(self.github_token)
            logger.info("GitHub client initialized")
        
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
        workflow.add_node("generate_embeddings", self._generate_embeddings)
        workflow.add_node("save_baseline_map", self._save_baseline_map)
        
        # Define workflow edges following the diagram
        workflow.set_entry_point("scan_repository")
        workflow.add_edge("scan_repository", "identify_design_elements")
        workflow.add_edge("identify_design_elements", "design_to_design_mapping")  
        workflow.add_edge("design_to_design_mapping", "design_to_code_mapping")
        workflow.add_edge("design_to_code_mapping", "identify_requirements")
        workflow.add_edge("identify_requirements", "requirements_to_design_mapping")
        workflow.add_edge("requirements_to_design_mapping", "generate_embeddings")
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
            branch=branch
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
            logger.info("Scanning SDD files (priority for traceability matrix)...")
            state.sdd_content = await self._fetch_documentation_files(state.repository, sdd_patterns, state.branch)
            
            # Then scan SRS and code files
            logger.info("Scanning SRS and code files...")
            state.srs_content = await self._fetch_documentation_files(state.repository, srs_patterns, state.branch)
            state.code_files = await self._fetch_code_files(state.repository, code_patterns, state.branch)
            
            logger.info(f"Found {len(state.sdd_content)} SDD files, {len(state.srs_content)} SRS files, {len(state.code_files)} code files")
            
        except Exception as e:
            error_msg = f"Error scanning repository: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _identify_design_elements(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Identify design elements from SDD documentation using LLM
        SDD is processed first as it contains the traceability matrix between design elements and requirements
        """
        logger.info("Identifying design elements from SDD")
        state.current_step = "identifying_design_elements"
        
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
            logger.info(f"Identified {len(design_elements)} design elements")
            
            # Generate embeddings for design elements immediately for better mapping accuracy
            if design_elements and self.embedding_client:
                logger.info("Generating embeddings for design elements...")
                await self._generate_design_element_embeddings(design_elements)
                logger.info("Design element embeddings generated")
            
        except Exception as e:
            error_msg = f"Error identifying design elements: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _design_to_design_mapping(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Create mappings between design elements (internal relationships)
        """
        logger.info("Creating design-to-design mappings")
        state.current_step = "design_to_design_mapping"
        
        try:
            design_to_design_links = []
            link_counter = 1
            
            # Analyze relationships between design elements using embeddings + LLM
            if len(state.design_elements) > 1:
                links_data = await self._create_design_element_relationships_with_embeddings(state.design_elements)
                
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
            
            state.design_to_design_links = design_to_design_links
            state.processing_stats["design_to_design_links_count"] = len(design_to_design_links)
            logger.info(f"Created {len(design_to_design_links)} design-to-design mappings")
            
        except Exception as e:
            error_msg = f"Error creating design-to-design mappings: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _design_to_code_mapping(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Create mappings between design elements and code components
        """
        logger.info("Creating design-to-code mappings")
        state.current_step = "design_to_code_mapping"
        
        try:
            # Create code components from file paths (simplified approach)
            code_components = []
            comp_counter = 1
            
            for file_info in state.code_files:
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
            
            state.code_components = code_components
            state.processing_stats["code_components_count"] = len(code_components)
            
            # Generate embeddings for code components for better mapping accuracy
            if code_components and self.embedding_client:
                logger.info("Generating embeddings for code components...")
                await self._generate_code_component_embeddings(code_components)
                logger.info("Code component embeddings generated")
            
            # Create design-to-code links using embeddings for similarity matching
            design_to_code_links = []
            link_counter = 1
            
            links_data = await self._create_design_code_links_with_embeddings(state.design_elements, code_components)
            
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
            
            state.design_to_code_links = design_to_code_links
            state.processing_stats["design_to_code_links_count"] = len(design_to_code_links)
            logger.info(f"Created {len(design_to_code_links)} design-to-code mappings")
            
        except Exception as e:
            error_msg = f"Error creating design-to-code mappings: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _identify_requirements(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Identify requirements from SRS documentation using LLM
        """
        logger.info("Identifying requirements from SRS")
        state.current_step = "identifying_requirements"
        
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
            logger.info(f"Identified {len(requirements)} requirements")
            
            # Generate embeddings for requirements for better mapping accuracy
            if requirements and self.embedding_client:
                logger.info("Generating embeddings for requirements...")
                await self._generate_requirement_embeddings(requirements)
                logger.info("Requirement embeddings generated")
            
        except Exception as e:
            error_msg = f"Error identifying requirements: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _requirements_to_design_mapping(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Create mappings between requirements and design elements
        Uses the traceability matrix from SDD documentation
        """
        logger.info("Creating requirements-to-design mappings")
        state.current_step = "requirements_to_design_mapping"
        
        try:
            requirements_to_design_links = []
            link_counter = 1
            
            # Extract traceability matrix from SDD and create requirement-design links using embeddings
            req_to_design_links = await self._create_requirement_design_links_from_sdd_with_embeddings(
                state.requirements, state.design_elements, state.sdd_content
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
            
            state.requirements_to_design_links = requirements_to_design_links
            state.processing_stats["requirements_to_design_links_count"] = len(requirements_to_design_links)
            
            # Combine all traceability links
            state.traceability_links = (
                state.design_to_design_links + 
                state.design_to_code_links + 
                state.requirements_to_design_links
            )
            state.processing_stats["total_traceability_links_count"] = len(state.traceability_links)
            
            logger.info(f"Created {len(requirements_to_design_links)} requirements-to-design mappings")
            logger.info(f"Total traceability links: {len(state.traceability_links)}")
            
        except Exception as e:
            error_msg = f"Error creating requirements-to-design mappings: {str(e)}"
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
            if self.vector_search_repo:
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
            else:
                logger.info("Vector search repository not available, skipping embedding generation")
            
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
    
    # Helper methods for GitHub API integration
    async def _fetch_documentation_files(self, repository: str, patterns: List[str], branch: str) -> Dict[str, str]:
        """Fetch documentation files from repository using GitHub API"""
        documentation_files = {}
        
        if not self.github_client:
            logger.warning("GitHub client not available. Returning empty documentation files.")
            return documentation_files
        
        try:
            # Get repository
            repo = self.github_client.get_repo(repository)
            logger.info(f"Fetching documentation files from {repository}:{branch}")
            
            # Search for documentation files
            matching_files = await self._find_files_by_patterns(repo, patterns, branch)
            
            # Fetch content for each matching file
            for file_path in matching_files:
                try:
                    content = await self._get_file_content(repo, file_path, branch)
                    if content:
                        documentation_files[file_path] = content
                        logger.info(f"Fetched documentation file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to fetch content for {file_path}: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error fetching documentation files: {str(e)}")
        
        return documentation_files
    
    async def _fetch_code_files(self, repository: str, patterns: List[str], branch: str) -> List[Dict[str, Any]]:
        """Fetch code files from repository using GitHub API"""
        code_files = []
        
        if not self.github_client:
            logger.warning("GitHub client not available. Returning empty code files.")
            return code_files
        
        try:
            # Get repository
            repo = self.github_client.get_repo(repository)
            logger.info(f"Fetching code files from {repository}:{branch}")
            
            # Search for code files
            matching_files = await self._find_files_by_patterns(repo, patterns, branch)
            
            # Create file info for each matching file (without content for performance)
            for file_path in matching_files:
                code_files.append({
                    "path": file_path,
                    "content": ""  # We'll only fetch content if needed for embedding generation
                })
                logger.debug(f"Found code file: {file_path}")
            
            logger.info(f"Found {len(code_files)} code files")
            
        except Exception as e:
            logger.error(f"Error fetching code files: {str(e)}")
        
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
                logger.error("GitHub API rate limit exceeded. Please wait and try again.")
            elif e.status == 404:
                logger.error(f"Repository or branch not found: {repo.full_name}:{branch}")
            else:
                logger.error(f"GitHub API error: {str(e)}")
        except Exception as e:
            logger.error(f"Error searching files: {str(e)}")
        
        return matching_files
    
    async def _search_files_recursive(self, repo: Repository, contents: List[ContentFile], 
                                    patterns: List[str], branch: str, current_path: str = "", 
                                    max_depth: int = 5, current_depth: int = 0) -> List[str]:
        """Recursively search for files matching patterns with depth limit"""
        matching_files = []
        
        # Prevent infinite recursion and limit API calls
        if current_depth > max_depth:
            logger.warning(f"Maximum search depth ({max_depth}) reached at {current_path}")
            return matching_files
        
        for content in contents:
            full_path = f"{current_path}/{content.path}" if current_path else content.path
            
            if content.type == "dir":
                # Skip common directories that usually don't contain documentation
                skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'env', 
                           'target', 'build', 'dist', '.next', 'coverage'}
                
                if content.name.lower() in skip_dirs:
                    logger.debug(f"Skipping directory: {content.path}")
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
                        logger.warning(f"Rate limit hit while accessing {content.path}")
                        await asyncio.sleep(1)  # Brief pause
                    else:
                        logger.warning(f"Failed to access directory {content.path}: {str(e)}")
                except Exception as e:
                    logger.warning(f"Failed to access directory {content.path}: {str(e)}")
            else:
                # Check if file matches any pattern
                if self._matches_patterns(content.path, patterns):
                    matching_files.append(content.path)
                    logger.debug(f"Found matching file: {content.path}")
        
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
            logger.warning(f"Failed to get content for {file_path}: {str(e)}")
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
                    logger.warning(f"GitHub API rate limit low ({core_remaining} remaining). Waiting {wait_time:.1f} seconds...")
                    await asyncio.sleep(wait_time)
            
        except Exception as e:
            logger.warning(f"Failed to check rate limit: {str(e)}")
    
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
    

    
    async def _generate_design_element_embeddings(self, design_elements: List[DesignElementModel]) -> None:
        """Generate embeddings for design elements"""
        try:
            for element in design_elements:
                # Create text representation for embedding
                text = f"{element.name}: {element.description} (Type: {element.type})"
                embedding = await self.embedding_client.embed_text(text)
                # Store embedding (would be saved to vector database in full implementation)
                element.embedding = embedding
        except Exception as e:
            logger.warning(f"Failed to generate embeddings for design elements: {str(e)}")
    
    async def _generate_code_component_embeddings(self, code_components: List[CodeComponentModel]) -> None:
        """Generate embeddings for code components"""
        try:
            for component in code_components:
                # Create text representation for embedding (using file path and name)
                text = f"File: {component.path} ({component.name})"
                embedding = await self.embedding_client.embed_text(text)
                # Store embedding (would be saved to vector database in full implementation)
                component.embedding = embedding
        except Exception as e:
            logger.warning(f"Failed to generate embeddings for code components: {str(e)}")
    
    async def _generate_requirement_embeddings(self, requirements: List[RequirementModel]) -> None:
        """Generate embeddings for requirements"""
        try:
            for requirement in requirements:
                # Create text representation for embedding
                text = f"{requirement.title}: {requirement.description} (Type: {requirement.type}, Priority: {requirement.priority})"
                embedding = await self.embedding_client.embed_text(text)
                # Store embedding (would be saved to vector database in full implementation)
                requirement.embedding = embedding
        except Exception as e:
            logger.warning(f"Failed to generate embeddings for requirements: {str(e)}")
    
    async def _create_design_element_relationships_with_embeddings(self, design_elements: List[DesignElementModel]) -> List[Dict[str, Any]]:
        """Create relationships between design elements using embedding similarity"""
        relationships = []
        
        try:
            # Calculate similarity between all pairs of design elements
            for i, source_element in enumerate(design_elements):
                for j, target_element in enumerate(design_elements):
                    if i >= j:  # Avoid duplicates and self-references
                        continue
                    
                    # Calculate similarity using embeddings (if available)
                    if hasattr(source_element, 'embedding') and hasattr(target_element, 'embedding'):
                        similarity = await self._calculate_embedding_similarity(
                            source_element.embedding, target_element.embedding
                        )
                        
                        # Create relationship if similarity is above threshold
                        if similarity > 0.7:  # Threshold for relationship
                            relationships.append({
                                "source_id": source_element.id,
                                "target_id": target_element.id,
                                "relationship_type": "related_to",
                                "similarity_score": similarity
                            })
            
        except Exception as e:
            logger.warning(f"Failed to create design element relationships with embeddings: {str(e)}")
            # Fallback to simple placeholder
            relationships = [
                {
                    "source_id": "DE-001",
                    "target_id": "DE-002", 
                    "relationship_type": "depends_on"
                }
            ]
        
        return relationships
    
    async def _create_requirement_design_links_from_sdd_with_embeddings(self, requirements: List[RequirementModel], 
                                                                       design_elements: List[DesignElementModel],
                                                                       sdd_content: Dict[str, str]) -> List[Dict[str, Any]]:
        """Create links between requirements and design elements using SDD traceability matrix + embeddings"""
        links = []
        
        try:
            # First try to parse explicit traceability matrix from SDD
            explicit_links = await self._parse_traceability_matrix_from_sdd(sdd_content, requirements, design_elements)
            links.extend(explicit_links)
            
            # Then use embedding similarity for additional mappings
            similarity_links = await self._create_requirement_design_similarity_links(requirements, design_elements)
            links.extend(similarity_links)
            
        except Exception as e:
            logger.warning(f"Failed to create requirement-design links with embeddings: {str(e)}")
            # Fallback to simple placeholder
            links = [
                {
                    "source_id": "REQ-001",
                    "target_id": "DE-001",
                    "relationship_type": "implements"
                }
            ]
        
        return links
    
    async def _create_design_code_links_with_embeddings(self, design_elements: List[DesignElementModel], code_components: List[CodeComponentModel]) -> List[Dict[str, Any]]:
        """Create links between design elements and code components using embedding similarity"""
        links = []
        
        try:
            # Use embedding similarity to match design elements with code files
            for design_element in design_elements:
                for code_component in code_components:
                    if hasattr(design_element, 'embedding') and hasattr(code_component, 'embedding'):
                        similarity = await self._calculate_embedding_similarity(
                            design_element.embedding, code_component.embedding
                        )
                        
                        # Create link if similarity is above threshold
                        if similarity > 0.6:  # Lower threshold for design-to-code mapping
                            links.append({
                                "source_id": design_element.id,
                                "target_id": code_component.id,
                                "relationship_type": "realizes",
                                "similarity_score": similarity
                            })
            
        except Exception as e:
            logger.warning(f"Failed to create design-code links with embeddings: {str(e)}")
            # Fallback to simple placeholder
            links = [
                {
                    "source_id": "DE-001",
                    "target_id": "CC-001",
                    "relationship_type": "realizes"
                }
            ]
        
        return links
    
    async def _calculate_embedding_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings"""
        try:
            import numpy as np
            
            # Convert to numpy arrays
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            logger.warning(f"Failed to calculate embedding similarity: {str(e)}")
            return 0.0
    
    async def _parse_traceability_matrix_from_sdd(self, sdd_content: Dict[str, str], 
                                                 requirements: List[RequirementModel],
                                                 design_elements: List[DesignElementModel]) -> List[Dict[str, Any]]:
        """Parse explicit traceability matrix from SDD content"""
        # Placeholder - would implement parsing of traceability tables/matrices in SDD
        return []
    
    async def _create_requirement_design_similarity_links(self, requirements: List[RequirementModel], 
                                                         design_elements: List[DesignElementModel]) -> List[Dict[str, Any]]:
        """Create requirement-design links using embedding similarity"""
        links = []
        
        try:
            for requirement in requirements:
                for design_element in design_elements:
                    if hasattr(requirement, 'embedding') and hasattr(design_element, 'embedding'):
                        similarity = await self._calculate_embedding_similarity(
                            requirement.embedding, design_element.embedding
                        )
                        
                        # Create link if similarity is above threshold
                        if similarity > 0.65:  # Threshold for requirement-design mapping
                            links.append({
                                "source_id": requirement.id,
                                "target_id": design_element.id,
                                "relationship_type": "implements",
                                "similarity_score": similarity
                            })
        
        except Exception as e:
            logger.warning(f"Failed to create requirement-design similarity links: {str(e)}")
        
        return links

# Factory function
def create_baseline_map_creator(llm_client: Optional[DocurecoLLMClient] = None,
                               embedding_client: Optional[DocurecoEmbeddingClient] = None,
                               github_token: Optional[str] = None) -> BaselineMapCreatorWorkflow:
    """
    Factory function to create baseline map creator workflow
    
    Args:
        llm_client: Optional LLM client
        embedding_client: Optional embedding client
        github_token: Optional GitHub token for API access
        
    Returns:
        BaselineMapCreatorWorkflow: Configured workflow
    """
    return BaselineMapCreatorWorkflow(llm_client, embedding_client, github_token=github_token)

# Export main classes
__all__ = ["BaselineMapCreatorWorkflow", "BaselineMapCreatorState", "create_baseline_map_creator"] 