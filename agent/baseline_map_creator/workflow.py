"""
Baseline Map Creator Workflow for Docureco Agent
Creates baseline traceability maps from repository documentation and code
"""

import logging
import sys
import os
import fnmatch
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from langchain_core.output_parsers import JsonOutputParser

# Add parent directories to path for absolute imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, root_dir)

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agent.llm.llm_client import DocurecoLLMClient, create_llm_client
from agent.database.baseline_map_repository import BaselineMapRepository
from agent.models.docureco_models import (
    BaselineMapModel, RequirementModel, DesignElementModel, 
    CodeComponentModel, TraceabilityLinkModel
)
from .prompts import BaselineMapCreatorPrompts as prompts
from .models import (
    DesignElementsWithMatrixOutput,
    RequirementsWithDesignElementsOutput,
    RelationshipListOutput
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
    Uses Repomix for fast and efficient repository scanning without API limitations.
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
        
        # Check if Repomix is available
        try:
            subprocess.run(["repomix", "--version"], capture_output=True, check=True)
            logger.info("Repomix is available for repository scanning")
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("Repomix is not installed. Please install it with: npm install -g repomix")
        
        self.workflow = self._build_workflow()
        self.memory = MemorySaver()
        
        logger.info("Initialized BaselineMapCreatorWorkflow with Repomix")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow with conditional routing based on available data"""
        workflow = StateGraph(BaselineMapCreatorState)
        
        # Add nodes for each major process step
        workflow.add_node("scan_repository", self._scan_repository)
        workflow.add_node("identify_design_elements", self._identify_design_elements)
        workflow.add_node("identify_requirements", self._identify_requirements)
        workflow.add_node("design_to_design_mapping", self._design_to_design_mapping)
        workflow.add_node("requirements_to_design_mapping", self._requirements_to_design_mapping)
        workflow.add_node("design_to_code_mapping", self._design_to_code_mapping)
        workflow.add_node("save_baseline_map", self._save_baseline_map)
        
        # Define conditional workflow routing
        workflow.set_entry_point("scan_repository")
        
        # After scanning: check if documentation exists
        workflow.add_conditional_edges(
            "scan_repository",
            self._route_after_scan,
            {
                "identify_design_elements": "identify_design_elements",
                "end": END
            }
        )
        
        # After design elements: check if any were found
        workflow.add_conditional_edges(
            "identify_design_elements", 
            self._route_after_design_elements,
            {
                "identify_requirements": "identify_requirements",
                "end": END
            }
        )
        
        # After requirements: check if any were found  
        workflow.add_conditional_edges(
            "identify_requirements",
            self._route_after_requirements,
            {
                "design_to_design_mapping": "design_to_design_mapping",
                "end": END
            }
        )
        
        # Linear flow for the rest
        workflow.add_edge("design_to_design_mapping", "requirements_to_design_mapping")
        workflow.add_edge("requirements_to_design_mapping", "design_to_code_mapping")
        workflow.add_edge("design_to_code_mapping", "save_baseline_map")
        workflow.add_edge("save_baseline_map", END)
        
        return workflow
    
    def _route_after_scan(self, state: BaselineMapCreatorState) -> str:
        """Route after repository scan based on whether documentation was found"""
        has_sdd = len(state.get("sdd_content", {})) > 0
        has_srs = len(state.get("srs_content", {})) > 0
        
        if not has_sdd and not has_srs:
            logger.error("❌ No SDD or SRS documentation found. Workflow will terminate.")
            logger.error(f"   - SDD files: {len(state.get('sdd_content', {}))}")
            logger.error(f"   - SRS files: {len(state.get('srs_content', {}))}")
            return "end"
        
        logger.info(f"✅ Documentation found - proceeding to design element identification")
        logger.info(f"   - SDD files: {len(state.get('sdd_content', {}))}")
        logger.info(f"   - SRS files: {len(state.get('srs_content', {}))}")
        return "identify_design_elements"
    
    def _route_after_design_elements(self, state: BaselineMapCreatorState) -> str:
        """Route after design element identification based on whether any were found"""
        design_elements_count = len(state.get("design_elements", []))
        
        if design_elements_count == 0:
            logger.error("❌ No design elements extracted. Workflow will terminate.")
            return "end"
        
        logger.info(f"✅ Found {design_elements_count} design elements - proceeding to requirements identification")
        return "identify_requirements"
    
    def _route_after_requirements(self, state: BaselineMapCreatorState) -> str:
        """Route after requirements identification based on whether any were found"""
        requirements_count = len(state.get("requirements", []))
        
        if requirements_count == 0:
            logger.error("❌ No requirements extracted. Workflow will terminate.")
            return "end"
        
        logger.info(f"✅ Found {requirements_count} requirements - proceeding with full workflow")
        return "design_to_design_mapping"
    
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
            "sdd_traceability_matrix": [],
            "design_to_design_links": [],
            "design_to_code_links": [],
            "requirements_to_design_links": [],
            "traceability_links": [],
            "current_step": "initializing",
            "processing_stats": {}
        }
        
        # Check if baseline map already exists
        existing_map = await self.baseline_map_repo.get_baseline_map(repository, branch)
        force_recreate = os.getenv("FORCE_RECREATE", "false").lower() == "true"
        
        if existing_map and not force_recreate:
            logger.info(f"Baseline map already exists for {repository}:{branch}")
            logger.info("Use FORCE_RECREATE=true to overwrite existing map")
            return initial_state
        
        # Compile and run workflow
        app = self.workflow.compile(checkpointer=self.memory)
        config = {"configurable": {"thread_id": f"baseline_{repository.replace('/', '_')}_{branch}"}}
        
        final_state = await app.ainvoke(initial_state, config=config)
        
        # Print completion summary
        current_step = final_state.get("current_step", "unknown")
        if current_step == "completed":
            logger.info(f"✅ Baseline map creation completed successfully for {repository}:{branch}")
        else:
            logger.error(f"⚠️  Baseline map creation terminated early at step: {current_step}")
            logger.error(f"   Repository: {repository}:{branch}")
            
        return final_state
    
    async def _scan_repository(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Scan repository for documentation and all other files using Repomix.
        """
        logger.info(f"Scanning repository {state['repository']}:{state['branch']} with Repomix")
        state["current_step"] = "scanning_repository"
        
        try:
            # Use Repomix to scan the repository
            repo_data = await self._scan_repository_with_repomix(state["repository"], state["branch"])
            
            sdd_patterns = [
                "design.md", "sdd.md", "software-design.md", "architecture.md",
                "docs/design.md", "docs/sdd.md", "docs/architecture.md",
                "traceability.md", "traceability-matrix.md"
            ]
            srs_patterns = [
                "requirements.md", "srs.md", "software-requirements.md",
                "docs/requirements.md", "docs/srs.md", "documentation/requirements.md"
            ]
            
            # Extract documentation files
            state["sdd_content"] = self._extract_documentation_files(repo_data, sdd_patterns)
            state["srs_content"] = self._extract_documentation_files(repo_data, srs_patterns)
            
            # Get a set of all documentation file paths
            doc_paths = set(state["sdd_content"].keys()) | set(state["srs_content"].keys())
            
            # Extract all other files (non-documentation)
            other_files = []
            code_files_counter = 1
            if "files" in repo_data:
                for file_info in repo_data["files"]:
                    file_path = file_info.get("path", "")
                    if file_path and file_path not in doc_paths:
                        _, file_extension = os.path.splitext(file_path)
                        file_type = file_extension.lstrip('.') if file_extension else 'unknown'
                        other_files.append({
                            "id": f"CC-{code_files_counter:03d}",
                            "path": file_path,
                            "content": file_info.get("content", ""),
                            "type": file_type
                        })
                        code_files_counter += 1
            
            state["code_files"] = other_files
            
            logger.info(f"Found {len(state['sdd_content'])} SDD files, {len(state['srs_content'])} SRS files, and {len(state['code_files'])} other files.")
            
        except Exception as e:
            logger.error(f"Error scanning repository: {str(e)}")
            raise e
        
        return state
    
    async def _scan_repository_with_repomix(self, repository: str, branch: str) -> Dict[str, Any]:
        """
        Scan repository using Repomix
        
        Args:
            repository: Repository URL or path (owner/repo format)
            branch: Branch name
            
        Returns:
            Dict containing repository structure and file contents
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, "repo_scan.xml")
            
            # Convert repository format to URL if needed
            if "/" in repository and not repository.startswith("http"):
                repo_url = f"https://github.com/{repository}.git"
            else:
                repo_url = repository
            
            try:
                # Run Repomix to scan the repository
                cmd = [
                    "repomix",
                    "--remote", repo_url,
                    "--remote-branch", branch,
                    "--output", output_file,
                    "--style", "xml",
                    "--ignore", "node_modules,__pycache__,.git,.venv,venv,env,target,build,dist,.next,coverage, agent, .github, .vscode, .env, .env.local, .env.development.local, .env.test.local, .env.production.local"
                ]
                
                logger.info(f"Running Repomix: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode != 0:
                    raise RuntimeError(f"Repomix failed: {result.stderr}")
                
                # Read and parse the XML output file
                with open(output_file, 'r', encoding='utf-8') as f:
                    xml_content = f.read()
                
                repo_data = self._parse_repomix_xml(xml_content)
                
                logger.info(f"Repomix scan completed successfully")
                return repo_data
                
            except subprocess.TimeoutExpired:
                raise RuntimeError("Repomix scan timed out after 5 minutes")
            except Exception as e:
                raise RuntimeError(f"Failed to scan repository with Repomix: {str(e)}")
    
    def _parse_repomix_xml(self, xml_content: str) -> Dict[str, Any]:
        """
        Parse Repomix XML-like output into structured data
        
        Args:
            xml_content: Raw content from Repomix (not valid XML, but uses XML-like tags)
            
        Returns:
            Dict with files structure compatible with existing code
        """
        files = []
        
        try:
            # Repomix uses <file path="..."> tags but it's not valid XML
            # We need to parse it manually using regex/string parsing
            
            # Find all <file path="..."> sections
            import re
            
            # Pattern to match <file path="..."> and capture path and content
            file_pattern = r'<file path="([^"]*)">\s*(.*?)\s*</file>'
            
            matches = re.findall(file_pattern, xml_content, re.DOTALL)
            
            for file_path, file_content in matches:
                if file_path and file_content.strip():
                    files.append({
                        "path": file_path,
                        "content": file_content.strip()
                    })
            
            if not matches:
                # Try alternative approach: split by <file path=" and parse manually
                sections = xml_content.split('<file path="')
                
                for i, section in enumerate(sections):
                    if i == 0:  # Skip the first section (header/metadata)
                        continue
                        
                    # Extract file path from the opening tag
                    if '">' not in section:
                        continue
                        
                    path_end = section.find('">')
                    if path_end == -1:
                        continue
                        
                    file_path = section[:path_end]
                    
                    # Extract content until the closing </file> tag
                    content_start = path_end + 2  # Skip ">
                    
                    # Find the closing tag
                    closing_tag = '</file>'
                    content_end = section.find(closing_tag)
                    
                    if content_end == -1:
                        # If no closing tag, take everything until next <file or end
                        next_file = section.find('<file path="', content_start)
                        if next_file != -1:
                            file_content = section[content_start:next_file].strip()
                        else:
                            file_content = section[content_start:].strip()
                    else:
                        file_content = section[content_start:content_end].strip()
                    
                    if file_path and file_content:
                        files.append({
                            "path": file_path,
                            "content": file_content
                        })

            return {"files": files}
                
        except Exception as e:
            logger.warning(f"Warning: Repomix XML parsing failed ({e}), attempting fallback parsing")
            return self._parse_repomix_fallback(xml_content)
    
    def _parse_repomix_fallback(self, content: str) -> Dict[str, Any]:
        """
        Fallback parser for Repomix Markdown-style output
        
        Args:
            content: Raw content from Repomix
            
        Returns:
            Dict with files structure
        """
        files = []
        lines = content.split('\n')
        current_file = None
        current_content = []
        in_code_block = False
        
        for i, line in enumerate(lines):
            # Look for file headers: ## path/to/file (must contain a file extension or be in recognizable directory)
            if line.startswith('## '):
                if '/' in line or '.' in line:
                    # Save previous file if exists
                    if current_file and current_content:
                        file_content = '\n'.join(current_content).strip()
                        if file_content:  # Only add if there's actual content
                            files.append({
                                "path": current_file,
                                "content": file_content
                            })
                    
                    # Extract file path (remove ## prefix and clean up)
                    potential_file = line[3:].strip()
                    
                    # Filter out non-file headers - files should have extensions or be in directories
                    if ('.' in potential_file or '/' in potential_file) and not potential_file.endswith(':'):
                        current_file = potential_file
                        current_content = []
                        in_code_block = False
                
            elif current_file:
                # Handle code blocks
                if line.startswith('```'):
                    if not in_code_block:
                        # Starting code block
                        in_code_block = True
                    else:
                        # Ending code block
                        in_code_block = False
                    continue
                elif in_code_block:
                    current_content.append(line)
        
        # Save last file
        if current_file and current_content:
            file_content = '\n'.join(current_content).strip()
            if file_content:
                files.append({
                    "path": current_file,
                    "content": file_content
                })
            
        return {"files": files}
    
    def _extract_documentation_files(self, repo_data: Dict[str, Any], patterns: List[str]) -> Dict[str, str]:
        """
        Extract documentation files from Repomix output
        
        Args:
            repo_data: Repomix output data
            patterns: File patterns to match
            
        Returns:
            Dict mapping file paths to their content
        """
        documentation_files = {}
        
        if "files" not in repo_data:
            return documentation_files
        
        for file_info in repo_data["files"]:
            file_path = file_info.get("path", "")
            file_content = file_info.get("content", "")
            
            if self._matches_patterns(file_path, patterns):
                documentation_files[file_path] = file_content
                logger.info(f"Found documentation file: {file_path}")
        
        # Allow empty documentation files - will be handled by conditional workflow
        if len(documentation_files) == 0:
            logger.error(f"No documentation files found matching patterns: {patterns}")
        
        return documentation_files
    
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
    
    async def _identify_design_elements(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Identify design elements from SDD documentation using LLM and extract traceability matrix
        SDD is processed first as it contains the traceability matrix between design elements and requirements
        """
        logger.info("Identifying design elements from SDD and extracting traceability matrix")
        state["current_step"] = "identifying_design_elements"
        
        design_elements = []
        sdd_traceability_matrix = []
        elem_counter = 1
        
        for file_path, content in state["sdd_content"].items():
            if not content.strip():
                continue
            
            # Use LLM to extract design elements AND traceability matrix in one go
            extraction_result = await self._llm_extract_design_elements_with_matrix(content, file_path)
            
            # Process design elements
            for elem_data in extraction_result['design_elements']:
                design_element = DesignElementModel(
                    id=f"DE-{elem_counter:03d}",
                    reference_id=elem_data['reference_id'],
                    name=elem_data['name'],
                    description=elem_data['description'],
                    type=elem_data['type'],
                    section=elem_data['section']
                )
                design_elements.append(design_element)
                elem_counter += 1
            
            # Process traceability matrix (without relationship types initially)
            for matrix_entry in extraction_result['traceability_matrix']:
                sdd_traceability_matrix.append(matrix_entry)
        
        state["design_elements"] = design_elements
        state["sdd_traceability_matrix"] = sdd_traceability_matrix
        state["processing_stats"]["design_elements_count"] = len(design_elements)
        state["processing_stats"]["sdd_traceability_matrix_count"] = len(sdd_traceability_matrix)
        logger.info(f"Identified {len(design_elements)} design elements and {len(sdd_traceability_matrix)} traceability matrix entries")
        
        return state
    
    async def _design_to_design_mapping(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Create mappings between design elements (internal relationships)
        """
        logger.info("Creating design-to-design mappings")
        state["current_step"] = "design_to_design_mapping"
        
        design_to_design_links = []
        link_counter = 1
        
        # Create relationships between design elements using LLM analysis with traceability matrix context
        if len(state["design_elements"]) > 1:
            links_data = await self._llm_create_design_element_relationships(
                state["design_elements"], 
                state["sdd_traceability_matrix"]
            )
            
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
        logger.info(f"Created {len(design_to_design_links)} design-to-design mappings")
        
        return state
    
    async def _design_to_code_mapping(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Create mappings between design elements and code components
        """
        logger.info("Creating design-to-code mappings")
        state["current_step"] = "design_to_code_mapping"
        
        # Create code components from file paths (simplified approach)
        code_components = []        
        for file_info in state["code_files"]:
            file_id = file_info.get("id", "")
            file_path = file_info.get("path", "")
            file_type = file_info.get("type", "File") # Use the stored type, default to "File"

            if not file_path:
                continue
            
            # Create a code component for each file path
            code_component = CodeComponentModel(
                id=file_id,
                path=file_path,
                type=file_type,
                name=Path(file_path).name
            )
            code_components.append(code_component)
        
        state["code_components"] = code_components
        state["processing_stats"]["code_components_count"] = len(code_components)
        
        # Create design-to-code links using LLM analysis with actual code content and traceability matrix context
        design_to_code_links = []
        link_counter = 1
        
        links_data = await self._llm_create_design_code_links(
            state["design_elements"], 
            code_components, 
            state["code_files"],
            state["design_to_design_links"]
        )
        
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
        logger.info(f"Created {len(design_to_code_links)} design-to-code mappings")
        
        return state
    
    async def _identify_requirements(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Identify requirements and additional design elements from SRS documentation using LLM
        Uses the traceability matrix from SDD as context for more targeted extraction
        """
        logger.info("Identifying requirements and design elements from SRS")
        state["current_step"] = "identifying_requirements"
        
        requirements = []
        additional_design_elements = []
        req_counter = 1
        elem_counter = len(state["design_elements"]) + 1  # Continue numbering from existing design elements
        
        for file_path, content in state["srs_content"].items():
            if not content.strip():
                continue
            
            # Use LLM to extract requirements and design elements with traceability matrix context
            extraction_result = await self._llm_extract_requirements_with_design_elements(
                content, file_path, state["sdd_traceability_matrix"]
            )
            
            # Process requirements
            for req_data in extraction_result['requirements']:
                requirement = RequirementModel(
                    id=f"REQ-{req_counter:03d}",
                    reference_id=req_data['reference_id'],
                    title=req_data['title'],
                    description=req_data['description'],
                    type=req_data['type'],
                    priority=req_data['priority'],
                    section=req_data['section']
                )
                requirements.append(requirement)
                req_counter += 1
        
            # Process additional design elements found in SRS
            for elem_data in extraction_result['design_elements']:
                design_element = DesignElementModel(
                    id=f"DE-{elem_counter:03d}",
                    reference_id=elem_data['reference_id'],
                    name=elem_data['name'],
                    description=elem_data['description'],
                    type=elem_data['type'],
                    section=elem_data['section']
                )
                additional_design_elements.append(design_element)
                elem_counter += 1
        
        # Merge additional design elements with existing ones
        state["design_elements"].extend(additional_design_elements)
        state["requirements"] = requirements
        state["processing_stats"]["requirements_count"] = len(requirements)
        state["processing_stats"]["additional_design_elements_count"] = len(additional_design_elements)
        state["processing_stats"]["total_design_elements_count"] = len(state["design_elements"])
        
        logger.info(f"Identified {len(requirements)} requirements and {len(additional_design_elements)} additional design elements from SRS")
        logger.info(f"Total design elements: {len(state['design_elements'])}")
        
        return state
    
    async def _requirements_to_design_mapping(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Create mappings between requirements and design elements
        Uses the traceability matrix from SDD documentation
        """
        logger.info("Creating requirements-to-design mappings")
        state["current_step"] = "requirements_to_design_mapping"
        
        requirements_to_design_links = []
        link_counter = 1
        
        # Extract traceability matrix from SDD and create requirement-design links with full context
        req_to_design_links = await self._llm_create_requirement_design_links_from_sdd(
            state["requirements"], 
            state["design_elements"], 
            state["sdd_content"],
            state["sdd_traceability_matrix"]
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
        
        logger.info(f"Created {len(requirements_to_design_links)} requirements-to-design mappings")
        
        return state
    
    async def _save_baseline_map(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Save baseline map to database
        """
        logger.info("Saving baseline map to database")
        state["current_step"] = "saving_baseline_map"
        
        # Combine all traceability links before saving (handle empty lists gracefully)
        state["traceability_links"] = (
            state.get("design_to_design_links", []) + 
            state.get("design_to_code_links", []) + 
            state.get("requirements_to_design_links", [])
        )
        state["processing_stats"]["total_traceability_links_count"] = len(state["traceability_links"])
        
        logger.info(f"Total traceability links: {len(state['traceability_links'])}")
        logger.info(f"  - Design-to-design: {len(state.get('design_to_design_links', []))}")
        logger.info(f"  - Design-to-code: {len(state.get('design_to_code_links', []))}")
        logger.info(f"  - Requirements-to-design: {len(state.get('requirements_to_design_links', []))}")
        
        # Create baseline map model (handle potentially empty state values)
        baseline_map = BaselineMapModel(
            repository=state["repository"],
            branch=state["branch"],
            requirements=state.get("requirements", []),
            design_elements=state.get("design_elements", []),
            code_components=state.get("code_components", []),
            traceability_links=state["traceability_links"]
        )
        
        # Save to database
        success = await self.baseline_map_repo.save_baseline_map(baseline_map)
        
        if not success:
            raise Exception("Failed to save baseline map to database")
        
        logger.info(f"Successfully saved baseline map for {state['repository']}:{state['branch']}")
        state["baseline_map"] = baseline_map
            
        # Final processing stats
        stats = state.get("processing_stats", {})
        stats["total_traceability_links_count"] = len(baseline_map.traceability_links)
        
        state["processing_stats"] = stats
        state["current_step"] = "completed"
        
        logger.info(f"✅ Baseline map creation completed successfully for {repository}:{branch}")

        return state
    
    async def _llm_extract_design_elements_with_matrix(self, content: str, file_path: str) -> DesignElementsWithMatrixOutput:
        """
        Extract design elements and traceability matrix from SDD content using LLM with JSON output.
        Returns a Pydantic model with validated structure.
        """
        # Get prompts from the prompts module
        system_message = prompts.design_elements_with_matrix_system_prompt()
        human_prompt = prompts.design_elements_with_matrix_human_prompt(content, file_path)

        # Create output parser for JSON format
        output_parser = JsonOutputParser(pydantic_object=DesignElementsWithMatrixOutput)

        # Generate JSON response
        response = await self.llm_client.generate_response(
            prompt=human_prompt,
            system_message=system_message + "\n" + output_parser.get_format_instructions(),
            output_format="json",
            temperature=0.1  # Low temperature for consistent extraction
        )

        logger.info(f"Extracted {len(response.content['design_elements'])} design elements and {len(response.content['traceability_matrix'])} traceability matrix entries from {file_path}")
        return response.content
    
    async def _llm_extract_requirements_with_design_elements(self, content: str, file_path: str, sdd_traceability_matrix: List[Dict[str, Any]]) -> RequirementsWithDesignElementsOutput:
        """
        Extract requirements and additional design elements from SRS content using LLM with JSON output,
        with traceability matrix from SDD as context for more targeted extraction.
        """
        # Get prompts from the prompts module
        system_message = prompts.requirements_with_design_elements_system_prompt()
        human_prompt = prompts.requirements_with_design_elements_human_prompt(content, file_path, sdd_traceability_matrix)

        # Create output parser for JSON format
        output_parser = JsonOutputParser(pydantic_object=RequirementsWithDesignElementsOutput)

        # Generate JSON response (avoid generate_structured_response as it forces function calling)
        response = await self.llm_client.generate_response(
            prompt=human_prompt,
            system_message=system_message + "\n" + output_parser.get_format_instructions(),
            output_format="json",
            temperature=0.1  # Low temperature for consistent extraction
        )

        logger.info(f"Extracted {len(response.content['requirements'])} requirements and {len(response.content['design_elements'])} design elements from {file_path} with traceability matrix context")
        return response.content
    
    async def _llm_create_design_element_relationships(self, design_elements: List[DesignElementModel], sdd_traceability_matrix: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create relationships between design elements using LLM analysis with structured output. Raises exceptions on failure instead of using fallbacks."""
        if len(design_elements) < 2:
            logger.error("Not enough design elements to create relationships")
            return []
        
        # Prepare design elements data for LLM analysis
        elements_data = []
        for element in design_elements:
            elements_data.append({
                "id": element.id,
                "reference_id": element.reference_id,
                "name": element.name,
                "description": element.description,
                "type": element.type,
                "section": element.section
            })
            
        output_parser = JsonOutputParser(pydantic_object=RelationshipListOutput)
        
        # Get prompts from the prompts module
        system_message = prompts.design_element_relationships_system_prompt()
        human_prompt = prompts.design_element_relationships_human_prompt(elements_data, sdd_traceability_matrix)

        # Generate JSON response (use auto-parsing since we don't need full Pydantic validation)
        response = await self.llm_client.generate_response(
            prompt=human_prompt,
            system_message=system_message + "\n" + output_parser.get_format_instructions(),
            output_format="json",  # Auto-parses JSON
            temperature=0.15  # Low-medium temperature for consistent but thoughtful analysis
        )

        # Response content is now a dict with a 'relationships' key
        llm_relationships = response.content.get('relationships', [])

        # Validate relationships
        validated_relationships = []
        valid_element_ids = {elem.reference_id for elem in design_elements}
        
        for relationship in llm_relationships:
            # Validate that relationship has required fields
            if not isinstance(relationship, dict) or not all(key in relationship for key in ["source_id", "target_id", "relationship_type"]):
                raise ValueError(f"Invalid relationship format: {relationship}")
                
            # Validate that source and target IDs exist
            if relationship["source_id"] not in valid_element_ids:
                raise ValueError(f"Invalid source_id '{relationship['source_id']}' in design element relationship")
                
            if relationship["target_id"] not in valid_element_ids:
                raise ValueError(f"Invalid target_id '{relationship['target_id']}' in design element relationship")
                
            # Validate relationship type
            if relationship["relationship_type"] not in ["refines", "realizes", "depends_on"]:
                raise ValueError(f"Invalid relationship_type '{relationship['relationship_type']}' for design element relationship")
                
            validated_relationships.append(relationship)
        
        logger.info(f"Created {len(validated_relationships)} validated design element relationships")
        return validated_relationships
    
    async def _llm_create_requirement_design_links_from_sdd(self, requirements: List[RequirementModel], 
                                                       design_elements: List[DesignElementModel],
                                                       sdd_content: Dict[str, str],
                                                       sdd_traceability_matrix: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create links between requirements and design elements using SDD traceability matrix and LLM analysis"""
        if not requirements or not design_elements:
            logger.error("No requirements or design elements available for linking")
            return []
        
        # Prepare requirements and design elements data for LLM analysis
        requirements_data = []
        for req in requirements:
            requirements_data.append({
                "id": req.id,
                "reference_id": req.reference_id,
                "title": req.title,
                "description": req.description,
                "type": req.type,
                "priority": req.priority,
                "section": req.section
            })
        
        design_elements_data = []
        for elem in design_elements:
            design_elements_data.append({
                "id": elem.id,
                "reference_id": elem.reference_id,
                "name": elem.name,
                "description": elem.description,
                "type": elem.type,
                "section": elem.section
            })
            
        output_parser = JsonOutputParser(pydantic_object=RelationshipListOutput)
        
        # Get prompts from the prompts module
        system_message = prompts.requirement_design_links_system_prompt()
        human_prompt = prompts.requirement_design_links_human_prompt(requirements_data, design_elements_data, sdd_traceability_matrix, sdd_content)

        # Generate LLM response
        response = await self.llm_client.generate_response(
            prompt=human_prompt,
            system_message=system_message + "\n" + output_parser.get_format_instructions(),
            output_format="json",
            temperature=0.1  # Low temperature for consistent analysis
        )

        # Parse JSON response which is now a dict with a 'relationships' key
        llm_relationships = response.content.get('relationships', [])
        
        # Validate the response format
        if not isinstance(llm_relationships, list):
            raise ValueError(f"LLM returned non-list response for requirement-design relationships: {type(llm_relationships)}")
        
        # Validate each relationship has required fields
        validated_relationships = []
        valid_requirement_ids = {req.reference_id for req in requirements}
        valid_design_ids = {elem.reference_id for elem in design_elements}
        
        for rel in llm_relationships:
            if not isinstance(rel, dict):
                raise ValueError(f"Invalid requirement-design relationship format: {rel}")
                
            if not all(key in rel for key in ["source_id", "target_id", "relationship_type"]):
                raise ValueError(f"Requirement-design relationship missing required fields: {rel}")
            
            # Ensure source is a requirement and target is a design element
            if rel["source_id"] not in valid_requirement_ids:
                raise ValueError(f"Requirement-design relationship has invalid requirement ID: {rel}")
                
            if rel["target_id"] not in valid_design_ids:
                raise ValueError(f"Requirement-design relationship has invalid design element ID: {rel}")
                
            # Validate relationship type for R→D relationships
            valid_rd_types = {"satisfies", "realizes"}
            if rel["relationship_type"] not in valid_rd_types:
                raise ValueError(f"Invalid R→D relationship type '{rel['relationship_type']}'. Must be one of: {valid_rd_types}")
                
            validated_rel = {
                "source_id": rel["source_id"],
                "target_id": rel["target_id"],
                "relationship_type": rel.get("relationship_type", "satisfies")
            }
            validated_relationships.append(validated_rel)
        
        return validated_relationships
    
    async def _llm_create_design_code_links(self, design_elements: List[DesignElementModel], code_components: List[CodeComponentModel], code_files: List[Dict[str, Any]], design_to_design_links: List[TraceabilityLinkModel]) -> List[Dict[str, Any]]:
        """Create links between design elements and code components using LLM analysis. Raises exceptions on failure instead of using fallbacks."""
        if not design_elements or not code_components:
            logger.error("No design elements or code components available for linking")
            return []
        
        # Prepare design elements and code components data for LLM analysis
        elements_data = []
        for element in design_elements:
            elements_data.append({
                "id": element.id,
                "reference_id": element.reference_id,
                "name": element.name,
                "description": element.description,
                "type": element.type,
                "section": element.section
            })
        
        components_data = []
        code_content_map = {file_info["path"]: file_info.get("content", "") for file_info in code_files}
        for component in code_components:
            code_content = code_content_map.get(component.path, "")
            components_data.append({
                "id": component.id,
                "name": component.name,
                "path": component.path,
                "type": component.type,
                "content": code_content
            })
            
        # Convert Pydantic models to dicts for JSON serialization
        design_links_data = [link.model_dump(mode='json') for link in design_to_design_links]
            
        output_parser = JsonOutputParser(pydantic_object=RelationshipListOutput)
        
        # Get prompts from the prompts module
        system_message = prompts.design_code_links_system_prompt()
        human_prompt = prompts.design_code_links_human_prompt(elements_data, components_data, design_links_data)

        # Generate LLM response
        response = await self.llm_client.generate_response(
            prompt=human_prompt,
            system_message=system_message + "\n" + output_parser.get_format_instructions(),
            output_format="json",
            temperature=0.15  # Low-medium temperature for consistent analysis
        )

        # Parse JSON response which is now a dict with a 'relationships' key
        llm_relationships = response.content.get('relationships', [])
        
        # Validate the response format
        if not isinstance(llm_relationships, list):
            raise ValueError(f"LLM returned non-list response for design-code relationships: {type(llm_relationships)}")
        
        # Validate each relationship has required fields
        validated_relationships = []
        valid_design_ids = {elem.reference_id for elem in design_elements}
        valid_code_ids = {comp.id for comp in code_components}
        
        for rel in llm_relationships:
            if not isinstance(rel, dict):
                raise ValueError(f"Invalid design-code relationship format: {rel}")
                
            if not all(key in rel for key in ["source_id", "target_id", "relationship_type"]):
                raise ValueError(f"Design-code relationship missing required fields: {rel}")
            
            # Ensure source is a design element and target is a code component
            if rel["source_id"] not in valid_design_ids:
                raise ValueError(f"Design-code relationship has invalid design element ID: {rel}")
                
            if rel["target_id"] not in valid_code_ids:
                raise ValueError(f"Design-code relationship has invalid code component ID: {rel}")
                
            # Validate relationship type for D→C relationships
            valid_dc_types = {"implements", "realizes"}
            if rel["relationship_type"] not in valid_dc_types:
                raise ValueError(f"Invalid D→C relationship type '{rel['relationship_type']}'. Must be one of: {valid_dc_types}")
                
            validated_rel = {
                "source_id": rel["source_id"],
                "target_id": rel["target_id"],
                "relationship_type": rel.get("relationship_type", "implements")
            }
            validated_relationships.append(validated_rel)
        
        return validated_relationships

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