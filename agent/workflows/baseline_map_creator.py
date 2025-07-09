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
import subprocess
import json
import tempfile
from typing import Dict, Any, List, Optional, Set
from pathlib import Path

# Add parent directories to path for absolute imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, root_dir)

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
            print("Repomix is available for repository scanning")
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("Repomix is not installed. Please install it with: npm install -g repomix")
        
        self.workflow = self._build_workflow()
        self.memory = MemorySaver()
        
        logger.info("Initialized BaselineMapCreatorWorkflow with Repomix")
    
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
            "processing_stats": {}
        }
        
        # Check if baseline map already exists
        existing_map = await self.baseline_map_repo.get_baseline_map(repository, branch)
        force_recreate = os.getenv("FORCE_RECREATE", "false").lower() == "true"
        
        if existing_map and not force_recreate:
            print(f"Baseline map already exists for {repository}:{branch}")
            print("Use FORCE_RECREATE=true to overwrite existing map")
            return initial_state
        
        # Compile and run workflow
        app = self.workflow.compile(checkpointer=self.memory)
        config = {"configurable": {"thread_id": f"baseline_{repository.replace('/', '_')}_{branch}"}}
        
        final_state = await app.ainvoke(initial_state, config=config)
        
        print(f"Baseline map creation completed for {repository}:{branch}")
        return final_state
    
    async def _scan_repository(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Scan repository for documentation and code files using Repomix
        """
        print(f"Scanning repository {state['repository']}:{state['branch']} with Repomix")
        state["current_step"] = "scanning_repository"
        
        try:
            # Use Repomix to scan the repository
            repo_data = await self._scan_repository_with_repomix(state["repository"], state["branch"])
            
            # Extract files by type
            state["sdd_content"] = self._extract_documentation_files(repo_data, [
                "design.md", "sdd.md", "software-design.md", "architecture.md",
                "docs/design.md", "docs/sdd.md", "docs/architecture.md",
                "traceability.md", "traceability-matrix.md"
            ])
            
            state["srs_content"] = self._extract_documentation_files(repo_data, [
                "requirements.md", "srs.md", "software-requirements.md",
                "docs/requirements.md", "docs/srs.md", "documentation/requirements.md"
            ])
            
            state["code_files"] = self._extract_code_files(repo_data, [
                "*.py", "*.java", "*.js", "*.ts", "*.cpp", "*.h"
            ])
            
            print(f"Found {len(state['sdd_content'])} SDD files, {len(state['srs_content'])} SRS files, {len(state['code_files'])} code files")
            print("="*100)
            print(state["sdd_content"])
            print("="*100)
            print(state["srs_content"])
            print("="*100)
            
        except Exception as e:
            print(f"Error scanning repository: {str(e)}")
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
                
                print(f"Running Repomix: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode != 0:
                    raise RuntimeError(f"Repomix failed: {result.stderr}")
                
                # Read and parse the XML output file
                with open(output_file, 'r', encoding='utf-8') as f:
                    xml_content = f.read()
                
                repo_data = self._parse_repomix_xml(xml_content)
                
                print(f"Repomix scan completed successfully")
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
            print(f"Warning: Repomix XML parsing failed ({e}), attempting fallback parsing")
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
                print(f"Found documentation file: {file_path}")
        
        if len(documentation_files) == 0:
            raise Exception("No documentation files found")
        
        return documentation_files
    
    def _extract_code_files(self, repo_data: Dict[str, Any], patterns: List[str]) -> List[Dict[str, Any]]:
        """
        Extract code files from Repomix output
        
        Args:
            repo_data: Repomix output data
            patterns: File patterns to match
            
        Returns:
            List of code file info dictionaries
        """
        code_files = []
        
        if "files" not in repo_data:
            return code_files
        
        for file_info in repo_data["files"]:
            file_path = file_info.get("path", "")
            file_content = file_info.get("content", "")
            
            if self._matches_patterns(file_path, patterns):
                code_files.append({
                    "path": file_path,
                    "content": file_content
                })
                print(f"Found code file: {file_path}")
        
        return code_files
    
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
        Identify design elements from SDD documentation using LLM
        SDD is processed first as it contains the traceability matrix between design elements and requirements
        """
        print("Identifying design elements from SDD")
        state["current_step"] = "identifying_design_elements"
        
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
        
        return state
    
    async def _design_to_design_mapping(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Create mappings between design elements (internal relationships)
        """
        print("Creating design-to-design mappings")
        state["current_step"] = "design_to_design_mapping"
        
        design_to_design_links = []
        link_counter = 1
        
        # Create relationships between design elements using LLM analysis
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
        
        return state
    
    async def _design_to_code_mapping(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Create mappings between design elements and code components
        """
        print("Creating design-to-code mappings")
        state["current_step"] = "design_to_code_mapping"
        
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
        
        return state
    
    async def _identify_requirements(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Identify requirements from SRS documentation using LLM
        """
        print("Identifying requirements from SRS")
        state["current_step"] = "identifying_requirements"
        
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
        
        return state
    
    async def _requirements_to_design_mapping(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Create mappings between requirements and design elements
        Uses the traceability matrix from SDD documentation
        """
        print("Creating requirements-to-design mappings")
        state["current_step"] = "requirements_to_design_mapping"
        
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
        
        return state
    
    async def _save_baseline_map(self, state: BaselineMapCreatorState) -> BaselineMapCreatorState:
        """
        Save baseline map to database
        """
        print("Saving baseline map to database")
        state["current_step"] = "saving_baseline_map"
        
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
        
        if not success:
            raise Exception("Failed to save baseline map to database")
        
        print(f"Successfully saved baseline map for {state['repository']}:{state['branch']}")
        state["current_step"] = "completed"
        
        return state
    
    async def _llm_extract_requirements(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract requirements using LLM"""
        try:
            # Prepare system prompt for requirements extraction
            system_message = """You are an expert business analyst analyzing Software Requirements Specification (SRS) documents. Your task is to extract functional and non-functional requirements such as:

- Functional Requirements: Features, behaviors, functions the system must provide
- Non-Functional Requirements: Performance, security, usability, reliability constraints
- Business Requirements: High-level business goals and objectives
- User Requirements: What users need to accomplish
- System Requirements: Technical constraints and specifications

For each requirement found, provide:
- title: Clear, concise title of the requirement
- description: Detailed description of what is required
- type: Category (Functional, Non-Functional, Business, User, System, etc.)
- priority: Importance level (High, Medium, Low)
- section: Section reference from the document (if available)

Return a JSON array of requirements. If no requirements are found, return an empty array."""

            # Prepare human prompt with the content
            human_prompt = f"""Analyze the following Software Requirements Specification content and extract all requirements:

File: {file_path}

Content:
{content}

Extract requirements and return them as a JSON array."""

            # Generate LLM response
            response = await self.llm_client.generate_response(
                prompt=human_prompt,
                system_message=system_message,
                task_type="code_analysis",
                output_format="json",
                temperature=0.1  # Low temperature for consistent extraction
            )

            # Parse JSON response
            requirements = response.content
            
            # Validate the response format
            if not isinstance(requirements, list):
                print(f"LLM returned non-list response for {file_path}, using empty list")
                return []
            
            # Validate each requirement has required fields
            validated_requirements = []
            for req in requirements:
                if isinstance(req, dict) and "title" in req:
                    validated_req = {
                        "title": req.get("title", "Unknown Requirement"),
                        "description": req.get("description", ""),
                        "type": req.get("type", "Functional"),
                        "priority": req.get("priority", "Medium"),
                        "section": req.get("section", file_path)
                    }
                    validated_requirements.append(validated_req)
            
            print(f"Extracted {len(validated_requirements)} requirements from {file_path}")
            return validated_requirements
            
        except Exception as e:
            print(f"Error extracting requirements from {file_path}: {str(e)}")
            # Return fallback requirement on error
            return [
                {
                    "title": f"Requirement from {Path(file_path).stem}",
                    "description": f"Requirement extracted from {file_path}",
                    "type": "Functional",
                    "priority": "Medium",
                    "section": file_path
                }
            ]
    
    async def _llm_extract_design_elements(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract design elements using LLM"""
        try:
            # Prepare system prompt for design element extraction
            system_message = """You are an expert software architect analyzing Software Design Documents (SDD). Your task is to extract design elements such as:

- Components: Services, modules, libraries, frameworks
- Classes: Entity classes, controller classes, service classes
- Interfaces: API interfaces, contracts, protocols  
- Database Elements: Tables, schemas, data models
- UI Elements: Pages, forms, dialogs, components
- Architectural Elements: Layers, patterns, architectural components

For each design element found, provide:
- name: Clear, descriptive name of the design element
- description: Brief description of purpose/functionality
- type: Category (Service, Class, Interface, Component, Database, UI, etc.)
- section: Section reference from the document (if available)

Return a JSON array of design elements. If no design elements are found, return an empty array."""

            # Prepare human prompt with the content
            human_prompt = f"""Analyze the following Software Design Document content and extract all design elements:

File: {file_path}

Content:
{content}

Extract design elements and return them as a JSON array."""

            # Generate LLM response
            response = await self.llm_client.generate_response(
                prompt=human_prompt,
                system_message=system_message,
                task_type="code_analysis",
                output_format="json",
                temperature=0.1  # Low temperature for consistent extraction
            )

            # Parse JSON response
            design_elements = response.content
            
            # Validate the response format
            if not isinstance(design_elements, list):
                print(f"LLM returned non-list response for {file_path}, using empty list")
                return []
            
            # Validate each element has required fields
            validated_elements = []
            for element in design_elements:
                if isinstance(element, dict) and "name" in element:
                    validated_element = {
                        "name": element.get("name", "Unknown"),
                        "description": element.get("description", ""),
                        "type": element.get("type", "Component"),
                        "section": element.get("section", file_path)
                    }
                    validated_elements.append(validated_element)
            
            print(f"Extracted {len(validated_elements)} design elements from {file_path}")
            return validated_elements
            
        except Exception as e:
            print(f"Error extracting design elements from {file_path}: {str(e)}")
            # Return fallback elements on error
            return [
                {
                    "name": f"Component_{Path(file_path).stem}",
                    "description": f"Component extracted from {file_path}",
                    "type": "Component",
                    "section": file_path
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