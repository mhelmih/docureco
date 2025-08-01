"""
Document Update Recommender Workflow for Docureco Agent
Main LangGraph workflow that analyzes GitHub PR code changes and recommends documentation updates
Implements the Document Update Recommender component from the system architecture
"""

import asyncio
import logging
import re
import sys
import os
import httpx
import subprocess
import tempfile
import fnmatch
from typing import Dict, Any, List, Optional, Tuple
from langchain_core.output_parsers import JsonOutputParser

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, root_dir)

# LangGraph imports
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Agent imports
from agent.llm.llm_client import DocurecoLLMClient
from agent.models.docureco_models import BaselineMapModel
from agent.database import create_baseline_map_repository
from agent.document_update_recommender.prompts import DocumentUpdateRecommenderPrompts as prompts

# Structured output models
from .models import (
    BatchClassificationOutput,
    ChangeGroupingOutput,
    RecommendationGenerationOutput,
    LikelihoodSeverityAssessmentOutput,
    DocumentUpdateRecommenderState,
    FilteredSuggestionsOutput
)

logger = logging.getLogger(__name__)

class DocumentUpdateRecommenderWorkflow:
    """
    Main LangGraph workflow for analyzing GitHub PR code changes and recommending documentation updates.
    
    This workflow implements the Document Update Recommender component following the 5-step process:
    1. Scan PR - Scan PR event data and repo context
    2. Analyze Code Changes - Code change classification, grouping, and contextualization
    3. Assess Documentation Impact - Determine traceability status, impact tracing, and prioritization
    4. Generate and Post Recommendations - Filter findings, generate suggestions, and manage status
    5. End - Complete workflow
    """
    
    def __init__(self, 
                 llm_client: Optional[DocurecoLLMClient] = None,
                 baseline_map_repo = None,
                 primary_baseline_branch: str = "main"):
        """
        Initialize Document Update Recommender workflow
        
        Args:
            llm_client: Optional LLM client for analysis and recommendations
            baseline_map_repo: Optional repository for baseline map operations
            primary_baseline_branch: Primary branch to look for baseline maps (default: "main")
        """
        self.llm_client = llm_client or DocurecoLLMClient()
        self.baseline_map_repo = baseline_map_repo or create_baseline_map_repository()
        self.primary_baseline_branch = primary_baseline_branch
        
        # Check if Repomix is available
        try:
            subprocess.run(["repomix", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("Repomix not available, falling back to placeholder content")
            raise ValueError("Repomix not available")
        
        self.workflow = self._build_workflow()
        self.memory = MemorySaver()
        
        logger.info("Initialized Document Update Recommender Workflow")
        logger.info(f"Primary baseline branch: {primary_baseline_branch}")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow with conditional logic"""
        workflow = StateGraph(DocumentUpdateRecommenderState)
        
        # Add nodes for each step of the 5-step process
        workflow.add_node("scan_pr", self._scan_pr)
        workflow.add_node("analyze_code_changes", self._analyze_code_changes)
        workflow.add_node("assess_documentation_impact", self._assess_documentation_impact)
        workflow.add_node("generate_and_post_recommendations", self._generate_and_post_recommendations)
        
        # Define workflow edges following the exact sequence
        workflow.set_entry_point("scan_pr")
        workflow.add_conditional_edges("scan_pr", self._route_after_scan, {
            "analyze_code_changes": "analyze_code_changes",
            "end": END
        })
        workflow.add_edge("analyze_code_changes", "assess_documentation_impact")
        workflow.add_edge("assess_documentation_impact", "generate_and_post_recommendations")
        workflow.add_edge("generate_and_post_recommendations", END)
        
        return workflow
    
    async def execute(self, pr_url: str) -> DocumentUpdateRecommenderState:
        """
        Execute the Document Update Recommender workflow for PR analysis
        
        Args:
            pr_url: GitHub PR URL to analyze
            
        Returns:
            DocumentUpdateRecommenderState: Final state with recommendations
        """
        # Initialize state with PR information
        pr_info = await self._parse_pr_url(pr_url)
        initial_state = DocumentUpdateRecommenderState(
            repository=pr_info["repository"],
            pr_number=pr_info["pr_number"],
            branch=pr_info["branch"]
        )
        
        try:
            # Compile and run workflow
            app = self.workflow.compile(checkpointer=self.memory)
            config = {"configurable": {"thread_id": f"pr_{pr_info['repository'].replace('/', '_')}_{pr_info['pr_number']}"}}
            
            final_state = await app.ainvoke(initial_state, config=config)
            
            logger.info(f"Document Update Recommender completed for PR {pr_info['repository']}#{pr_info['pr_number']}")
            return final_state
            
        except Exception as e:
            logger.error(f"Document Update Recommender failed: {str(e)}")
            initial_state.errors.append(str(e))
            raise
    
    def _route_after_scan(self, state: DocumentUpdateRecommenderState) -> str:
        """Route after scan"""
        if state.processing_stats["srs_count"] <= 0 or state.processing_stats["sdd_count"] <= 0 or state.processing_stats["commit_count"] <= 0 or state.processing_stats["files_changed"] <= 0:
            return "end"
        return "analyze_code_changes"
    
    async def _scan_pr(self, state: DocumentUpdateRecommenderState) -> DocumentUpdateRecommenderState:
        """
        Step 1: Scan PR and Documentation Context
        
        Implements:
        - PR Event Data scanning
        - Fetch documentation content
        """
        logger.info(f"Step 1: Scanning PR #{state.pr_number} and documentation context")
        
        try:
            # Scan PR event data
            pr_event_data = await self._fetch_pr_event_data(state.repository, state.pr_number)
            state.pr_event_data = pr_event_data
            
            # Get documentation content
            document_content = await self._fetch_document_content(state.repository, state.branch)
            state.document_content = document_content
            
            commit_count = len(pr_event_data["commit_info"]["commits"])
            files_changed = sum(len(commit.get("files", [])) for commit in pr_event_data["commit_info"]["commits"])
            additions = sum(commit.get("additions", 0) for commit in pr_event_data["commit_info"]["commits"])
            deletions = sum(commit.get("deletions", 0) for commit in pr_event_data["commit_info"]["commits"])
            
            srs_count = len(document_content.get("srs_content", {}))
            sdd_count = len(document_content.get("sdd_content", {}))
            
            # Update processing statistics
            state.processing_stats.update({
                "files_changed": files_changed,
                "commit_count": commit_count,
                "pr_additions": additions,
                "pr_deletions": deletions,
                "srs_count": srs_count,
                "sdd_count": sdd_count
            })
            
            logger.info(f"Step 1: Successfully scanned PR #{state.pr_number} and documentation context")
            logger.info(f"  - {files_changed} changed files")
            logger.info(f"  - {commit_count} commits")
            logger.info(f"  - {additions} additions")
            logger.info(f"  - {deletions} deletions")
            logger.info(f"  - {srs_count} SRS files")
            logger.info(f"  - {sdd_count} SDD files")
                
        except Exception as e:
            error_msg = f"Step 1: Error scanning PR: {str(e)}"
            state.errors.append(error_msg)
            raise
        
        return state
    
    async def _analyze_code_changes(self, state: DocumentUpdateRecommenderState) -> DocumentUpdateRecommenderState:
        """
        Step 2: Analyze code changes from PR event data, classify them, and group them into logical change sets.
        
        This workflow step:
        1. Classifies individual code changes from PR event data
        2. Groups classified changes into logical change sets using commit semantics
        
        Args:
            state: Current workflow state containing PR event data
            
        Returns:
            Logical change sets
        """        
        logger.info("Step 2: Analyzing code changes")
        
        # Step 2.1: Classify changes organized by commit
        logger.info("Step 2.1: Classifying changes organized by commit")
        commits_with_classifications = await self._llm_classify_individual_changes(state.pr_event_data)
        state.classified_changes = commits_with_classifications

        # Step 2.2: Group classified changes into logical change sets
        logger.info("Step 2.2: Grouping classified changes into logical change sets")
        logical_change_sets = await self._llm_group_classified_changes(commits_with_classifications)
        state.logical_change_sets = logical_change_sets
            
        total_files = sum(len(change_set["changes"]) for change_set in logical_change_sets)
        logger.info(f"Step 2: Successfully analyzed {total_files} file classifications across {len(commits_with_classifications)} commits into {len(logical_change_sets)} logical change sets")
        
        return state
    
    async def _assess_documentation_impact(self, state: DocumentUpdateRecommenderState) -> DocumentUpdateRecommenderState:
        """
        Step 3: Assess Documentation Impact
        
        Implements the comprehensive impact analysis process:
        1. Determine Traceability Status and Detect Documentation Changes (combined)
        2. Trace Code Impact Through Map  
        3. Assess Likelihood and Severity (considering existing documentation updates)
        """
        logger.info("Step 3: Assessing documentation impact using traceability analysis")
        
        try:
            # 3.1 Determine Traceability Status and Detect Documentation Changes
            logger.info("Step 3.1: Determining traceability status and detecting documentation changes")
            
            baseline_map_data = await self.baseline_map_repo.get_baseline_map(state.repository, self.primary_baseline_branch)
            
            if not baseline_map_data and state.branch != self.primary_baseline_branch:
                baseline_map_data = await self.baseline_map_repo.get_baseline_map(state.repository, state.branch)
            
            if not baseline_map_data:
                logger.warning(f"No baseline map found on {self.primary_baseline_branch} or {state.branch} - terminating workflow")
                return state    # Terminate workflow if no baseline map is found
                
            state.baseline_map = baseline_map_data
            
            # Process all file changes in one pass to determine traceability status and detect documentation changes
            changes_with_status, documentation_changes = await self._determine_traceability_status_and_detect_docs(
                state.logical_change_sets,
                baseline_map_data
            )
            
            # 3.2 Trace Code Impact Through Map
            logger.info("Step 3.2: Tracing code impact through baseline map")
            # Get potentially impacted elements through traceability map tracing
            # Process each logical change set separately to maintain source attribution
            potentially_impacted_elements = await self._trace_code_impact_through_map(
                changes_with_status,
                baseline_map_data
            )
            state.potentially_impacted_elements = potentially_impacted_elements
            
            # 3.3 Assess Likelihood and Severity (considering existing documentation updates)
            logger.info("Step 3.3: Assessing likelihood and severity with consideration of existing documentation updates")
            prioritized_findings = await self._llm_assess_likelihood_and_severity(
                potentially_impacted_elements,
                state.logical_change_sets,
                documentation_changes
            )
            state.prioritized_finding_list = prioritized_findings
            
            # Update processing statistics
            state.processing_stats.update({
                "potentially_impacted_elements": len(potentially_impacted_elements),
                "documentation_changes_detected": len(documentation_changes),
                "total_findings": len(potentially_impacted_elements),
                "prioritized_findings": len(prioritized_findings)
            })
            
            logger.info(f"Step 3: Successfully assessed documentation impact")
            logger.info(f"  - {len(potentially_impacted_elements)} potentially impacted elements")
            logger.info(f"  - {len(documentation_changes)} documentation changes detected in PR")
            logger.info(f"  - {len(prioritized_findings)} prioritized findings")
            
        except Exception as e:
            error_msg = f"Step 3: Error assessing documentation impact: {str(e)}"
            state.errors.append(error_msg)
            raise
        
        return state

    async def _determine_traceability_status_and_detect_docs(self, logical_change_sets: List[Dict[str, Any]], baseline_map_data: BaselineMapModel) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Efficiently determine traceability status for code files and detect documentation changes in one pass.
        
        Traceability status:
        - Addition + not in map = Gap
        - Addition + in map = Anomaly (addition mapped) - treat as modification
        - Deletion + in map = Outdated 
        - Deletion + not in map = Anomaly (deletion unmapped)
        - Modification + in map = Modification
        - Modification + not in map = Anomaly (modification unmapped)
        - Rename + old file in map = Rename
        - Rename + old file not in map = Anomaly (rename unmapped)
        
        Returns:
            tuple: (changes_with_status, documentation_changes)
        """
        # Convert baseline map to lookup structure for efficiency
        code_component_lookup = set()
        if baseline_map_data.code_components:
            for component in baseline_map_data.code_components:
                code_component_lookup.add(component.path)
        
        # Define patterns for SRS and SDD files
        srs_patterns = [
            "**/srs.md", "**/requirements.md", "**/software-requirements.md",
            "**/SRS.md", "**/REQUIREMENTS.md", 
            "srs.md", "requirements.md", "software-requirements.md"
        ]
        
        sdd_patterns = [
            "**/sdd.md", "**/design.md", "**/software-design.md", "**/architecture.md",
            "**/SDD.md", "**/DESIGN.md", "**/ARCHITECTURE.md",
            "sdd.md", "design.md", "software-design.md", "architecture.md"
        ]
        
        changes_with_status = []
        documentation_changes = []
        
        for change_set in logical_change_sets:
            change_set_name = change_set.get("name", "Unknown Change Set")
            new_change_set = {
                "name": change_set_name,
                "description": change_set["description"],
                "changes": []
            }
            
            for change in change_set.get("changes", []):
                file_path = change.get("file", "")
                change_type = change.get("type", "").lower()
                
                # Check if this is a documentation file
                doc_type = None
                if self._matches_patterns(file_path, srs_patterns):
                    doc_type = "SRS"
                elif self._matches_patterns(file_path, sdd_patterns):
                    doc_type = "SDD"
                
                if doc_type:
                    # This is a documentation file - add to documentation changes
                    doc_change = {
                        "file_path": file_path,
                        "document_type": doc_type,
                        "change_type": change_type,
                        "scope": change.get("scope", ""),
                        "nature": change.get("nature", ""),
                        "volume": change.get("volume", ""),
                        "source_change_set": change_set_name,
                        "reasoning": change.get("reasoning", "")
                    }
                    documentation_changes.append(doc_change)
                    
                    # Also add to changes_with_status for completeness, but mark as documentation
                    change_with_status = change.copy()
                    change_with_status["traceability_status"] = "documentation_file"
                    change_with_status["is_documentation"] = True
                    new_change_set["changes"].append(change_with_status)
                else:
                    # This is a code file - determine traceability status
                    traceability_status = self._get_traceability_status(
                        change_type, 
                        file_path, 
                        code_component_lookup
                    )
                    
                    # Add status to change record
                    change_with_status = change.copy()
                    change_with_status["traceability_status"] = traceability_status
                    change_with_status["is_documentation"] = False
                    new_change_set["changes"].append(change_with_status)
            
            changes_with_status.append(new_change_set)
        
        return changes_with_status, documentation_changes

    def _get_traceability_status(self, change_type: str, file_path: str, code_component_lookup: set) -> str:
        """
        Get traceability status based on change type and baseline map presence.
        
        Returns status
        """
        is_in_baseline = file_path in code_component_lookup
        
        if change_type.lower() == "addition":
            return "anomaly (addition mapped)" if is_in_baseline else "gap"
        elif change_type.lower() == "deletion":
            return "outdated" if is_in_baseline else "anomaly (deletion unmapped)"
        elif change_type.lower() == "modification":
            return "modification" if is_in_baseline else "anomaly (modification unmapped)"
        elif change_type.lower() == "renaming":
            # For rename, we should check if the old file name was in baseline
            # For simplicity, using current file path - in practice would need old path
            return "rename" if is_in_baseline else "anomaly (rename unmapped)"
        else:
            # Unknown change type - treat as anomaly
            return "anomaly (unknown change type)"

    async def _trace_code_impact_through_map(self, changes_with_status: List[Dict[str, Any]], baseline_map_data: BaselineMapModel) -> List[Dict[str, Any]]:
        """
        Trace code impact through the traceability map by processing each logical change set separately.
        This ensures accurate source attribution even when the same file appears in multiple change sets.
        
        Process:
        1. For each logical change set:
           a. Identify Directly Impacted Design Elements (DIDE) and Outdated Design Elements (ODE)
           b. Trace Indirect Impact on Design Elements (IIDE)
           c. Combine to form Potentially Impacted Design Elements (PIDE)
           d. Trace to Requirements (PIR and OR)
           e. Form Finding Records with proper source attribution
        2. Combine all findings from all change sets
        """
        all_findings = []
        
        # Create lookup structures for efficient access (build once, use for all change sets)
        code_to_design_map = {}
        design_to_design_map = {}
        design_to_requirement_map = {}
        
        # Create path-to-component-id mapping for efficient lookups
        path_to_component_ref_id = {}
        if baseline_map_data.code_components:
            for component in baseline_map_data.code_components:
                path_to_component_ref_id[component.path] = component.id
        
        # Build mappings from traceability links (handling many-to-many relationships)
        if baseline_map_data.traceability_links:
            for link in baseline_map_data.traceability_links:
                if link.source_type == "DesignElement" and link.target_type == "CodeComponent":
                    if link.target_id not in code_to_design_map:
                        code_to_design_map[link.target_id] = []
                    if link.source_id not in code_to_design_map[link.target_id]:
                        code_to_design_map[link.target_id].append(link.source_id)
                
                elif link.source_type == "DesignElement" and link.target_type == "DesignElement":
                    if link.source_id not in design_to_design_map:
                        design_to_design_map[link.source_id] = []
                    if link.target_id not in design_to_design_map[link.source_id]:
                        design_to_design_map[link.source_id].append(link.target_id)
                    
                    if link.target_id not in design_to_design_map:
                        design_to_design_map[link.target_id] = []
                    if link.source_id not in design_to_design_map[link.target_id]:
                        design_to_design_map[link.target_id].append(link.source_id)
                
                elif link.source_type == "Requirement" and link.target_type == "DesignElement":
                    if link.target_id not in design_to_requirement_map:
                        design_to_requirement_map[link.target_id] = []
                    if link.source_id not in design_to_requirement_map[link.target_id]:
                        design_to_requirement_map[link.target_id].append(link.source_id)
        
        # Build lookup dictionaries for design elements and requirements
        design_elements_by_ref_id = {de.reference_id: de for de in getattr(baseline_map_data, "design_elements", []) if de.reference_id}
        requirements_by_ref_id = {req.reference_id: req for req in getattr(baseline_map_data, "requirements", []) if req.reference_id}
        
        # Process each logical change set separately
        for change_set in changes_with_status:
            change_set_name = change_set.get("name", "Unknown Change Set")
            change_set_findings = []
            
            # Identify Directly Impacted Design Elements (DIDE) and Outdated Design Elements (ODE) for this change set
            dide = set()  # Directly Impacted Design Elements for this change set
            ode = set()   # Outdated Design Elements for this change set
            
            # Process changes in this change set that need traceability map tracing
            for change in change_set.get("changes", []):
                file_path = change.get("file", "")
                status = change.get("traceability_status", "")
                
                # Skip documentation files - they're handled separately
                if change.get("is_documentation", False):
                    continue
                
                # Only process changes that can be traced through the map
                if status in ["modification", "anomaly (addition mapped)", "rename", "outdated"]:
                    if file_path in path_to_component_ref_id:
                        component_ref_id = path_to_component_ref_id[file_path]
                        if component_ref_id in code_to_design_map:
                            design_element_ref_ids = code_to_design_map[component_ref_id]
                            
                            if status in ["modification", "anomaly (addition mapped)", "rename"]:
                                dide.update(design_element_ref_ids)
                            elif status == "outdated":
                                ode.update(design_element_ref_ids)
                
                # Handle gap and anomaly findings directly for this change set
                elif status in ["gap", "anomaly (deletion unmapped)", 
                              "anomaly (modification unmapped)", "anomaly (rename unmapped)", "anomaly (unknown change type)"]:
                    
                    if status == "gap":
                        finding_type = "Documentation_Gap"
                    else:
                        finding_type = "Traceability_Anomaly"
                    
                    finding = {
                        "finding_type": finding_type,
                        "affected_element_id": file_path,
                        "affected_element_reference_id": file_path,
                        "affected_element_name": file_path,
                        "affected_element_description": file_path,
                        "affected_element_type": "CodeComponent",
                        "trace_path_type": None,
                        "source_change_set": change_set_name,
                        "anomaly_type": status if finding_type == "Traceability_Anomaly" else None
                    }
                    change_set_findings.append(finding)
            
            # Trace Indirect Impact on Design Elements (IIDE) for this change set
            iide = set()  # Indirectly Impacted Design Elements for this change set
            
            for design_element_ref_id in dide:
                if design_element_ref_id in design_to_design_map:
                    related_element_ids = design_to_design_map[design_element_ref_id]
                    iide.update(related_element_ids)
            
            # Combine to form Potentially Impacted Design Elements (PIDE) for this change set
            pide = dide.union(iide)
            
            # Trace to Requirements for this change set
            pir = set()  # Potentially Impacted Requirements for this change set
            or_set = set()  # Outdated Requirements for this change set
            
            # Trace PIDE to requirements
            for design_element_ref_id in pide:
                if design_element_ref_id in design_to_requirement_map:
                    requirement_ids = design_to_requirement_map[design_element_ref_id]
                    pir.update(requirement_ids)
            
            # Trace ODE to requirements  
            for design_element_ref_id in ode:
                if design_element_ref_id in design_to_requirement_map:
                    requirement_ids = design_to_requirement_map[design_element_ref_id]
                    or_set.update(requirement_ids)
            
            # Form Finding Records for this change set
            # Standard Impact findings for PIDE and PIR
            for design_element_ref_id in pide:
                finding = {
                    "finding_type": "Standard_Impact",
                    "affected_element_id": design_elements_by_ref_id[design_element_ref_id].id,
                    "affected_element_reference_id": design_element_ref_id,
                    "affected_element_name": design_elements_by_ref_id[design_element_ref_id].name,
                    "affected_element_description": design_elements_by_ref_id[design_element_ref_id].description,
                    "affected_element_type": "DesignElement - " + design_elements_by_ref_id[design_element_ref_id].type,
                    "trace_path_type": "Direct" if design_element_ref_id in dide else "Indirect",
                    "source_change_set": change_set_name
                }
                change_set_findings.append(finding)
            
            for requirement_ref_id in pir:
                finding = {
                    "finding_type": "Standard_Impact",
                    "affected_element_id": requirements_by_ref_id[requirement_ref_id].id, 
                    "affected_element_reference_id": requirement_ref_id,
                    "affected_element_name": requirements_by_ref_id[requirement_ref_id].title,
                    "affected_element_description": requirements_by_ref_id[requirement_ref_id].description,
                    "affected_element_type": "Requirement - " + requirements_by_ref_id[requirement_ref_id].type,
                    "trace_path_type": "Direct",
                    "source_change_set": change_set_name
                }
                change_set_findings.append(finding)
            
            # Outdated Documentation findings for ODE and OR
            for design_element_ref_id in ode:
                finding = {
                    "finding_type": "Outdated_Documentation",
                    "affected_element_id": design_elements_by_ref_id[design_element_ref_id].id,
                    "affected_element_reference_id": design_element_ref_id,
                    "affected_element_name": design_elements_by_ref_id[design_element_ref_id].name,
                    "affected_element_description": design_elements_by_ref_id[design_element_ref_id].description,
                    "affected_element_type": "DesignElement - " + design_elements_by_ref_id[design_element_ref_id].type,
                    "trace_path_type": None,
                    "source_change_set": change_set_name
                }
                change_set_findings.append(finding)
            
            for requirement_ref_id in or_set:
                finding = {
                    "finding_type": "Outdated_Documentation", 
                    "affected_element_id": requirements_by_ref_id[requirement_ref_id].id,
                    "affected_element_reference_id": requirement_ref_id,
                    "affected_element_name": requirements_by_ref_id[requirement_ref_id].title,
                    "affected_element_description": requirements_by_ref_id[requirement_ref_id].description,
                    "affected_element_type": "Requirement - " + requirements_by_ref_id[requirement_ref_id].type,
                    "trace_path_type": None,
                    "source_change_set": change_set_name
                }
                change_set_findings.append(finding)
            
            # Add all findings from this change set to the overall findings
            all_findings.extend(change_set_findings)
        
        return all_findings

    async def _assess_findings_batch(self, findings_batch: List[Dict[str, Any]], logical_change_sets: List[Dict[str, Any]], documentation_changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Helper to assess a single batch of findings."""
        try:
            # Create structured assessment for LLM including documentation changes
            assessment_context = {
                "findings": findings_batch,
                "logical_change_sets": logical_change_sets,
                "documentation_changes": documentation_changes
            }
            
            # Create output parser for structured response
            output_parser = JsonOutputParser(pydantic_object=LikelihoodSeverityAssessmentOutput)
            
            # Get prompts for likelihood and severity assessment
            system_message = prompts.likelihood_severity_assessment_system_prompt()
            human_prompt = prompts.likelihood_severity_assessment_human_prompt(assessment_context)
            
            # Generate assessment using LLM with structured output
            response = await self.llm_client.generate_response(
                prompt=human_prompt,
                system_message=system_message + "\n" + output_parser.get_format_instructions(),
                output_format="json",
                temperature=0.1  # Low temperature for consistent assessment
            )
            
            # Parse the structured response
            assessed_findings_models = response.content["assessed_findings"]
            
            # Convert Pydantic models back to dictionaries
            assessed_findings_dicts = []
            for assessed_finding in assessed_findings_models:
                # The response from the LLM client is already a dict
                finding_dict = {
                    "finding_type": assessed_finding["finding_type"],
                    "affected_element_id": assessed_finding["affected_element_id"],
                    "affected_element_reference_id": assessed_finding.get("affected_element_reference_id"),
                    "affected_element_name": assessed_finding["affected_element_name"],
                    "affected_element_description": assessed_finding["affected_element_description"],
                    "affected_element_type": assessed_finding["affected_element_type"],
                    "source_change_set": assessed_finding["source_change_set"],
                    "trace_path_type": assessed_finding.get("trace_path_type"),
                    "anomaly_type": assessed_finding.get("anomaly_type"),
                    "likelihood": assessed_finding["likelihood"],
                    "severity": assessed_finding["severity"],
                    "reasoning": assessed_finding["reasoning"]
                }
                assessed_findings_dicts.append(finding_dict)
            
            return assessed_findings_dicts
            
        except Exception as e:
            logger.error(f"Error assessing a batch of findings: {str(e)}")
            # Return an empty list for this batch on error to not fail the whole process
            return []

    async def _llm_assess_likelihood_and_severity(self, findings: List[Dict[str, Any]], logical_change_sets: List[Dict[str, Any]], documentation_changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Assess likelihood and severity for each finding using LLM in parallel batches.
        """
        if not findings:
            return []
            
        # Define batch size
        batch_size = 10
        
        # Create batches of findings
        finding_batches = [findings[i:i + batch_size] for i in range(0, len(findings), batch_size)]
        
        logger.info(f"Assessing {len(findings)} findings in {len(finding_batches)} parallel batches.")
        
        # Create async tasks for each batch
        tasks = []
        for batch in finding_batches:
            task = self._assess_findings_batch(batch, logical_change_sets, documentation_changes)
            tasks.append(task)
            
        try:
            # Run all assessment tasks in parallel
            list_of_results = await asyncio.gather(*tasks)
            
            # Flatten the list of lists into a single list of assessed findings
            all_assessed_findings = [finding for sublist in list_of_results for finding in sublist]
            
            # Filter the final list based on minimum criteria
            filtered_findings = []
            for finding_dict in all_assessed_findings:
                if self._meets_minimum_criteria(finding_dict):
                    filtered_findings.append(finding_dict)
            
            logger.info(f"Completed assessment. Got {len(all_assessed_findings)} results, filtered down to {len(filtered_findings)} findings.")
            return filtered_findings
            
        except Exception as e:
            error_msg = f"Step 3: Error in parallel likelihood/severity assessment: {str(e)}"
            raise ValueError(error_msg)
    
    def _meets_minimum_criteria(self, finding: Dict[str, Any]) -> bool:
        """Check if finding meets minimum criteria for inclusion"""
        likelihood = finding.get("likelihood", "")
        severity = finding.get("severity", "")
        finding_type = finding.get("finding_type", "")
        
        # Always include certain critical finding types
        if finding_type in ["Documentation_Gap", "Outdated_Documentation", "Traceability_Anomaly"]:
            return True
        
        # For Standard_Impact, check minimum thresholds
        likelihood_threshold = likelihood in ["Very Likely", "Likely"]
        severity_threshold = severity in ["Fundamental", "Major", "Moderate"]
        
        return likelihood_threshold and severity_threshold
    
    async def _generate_and_post_recommendations(self, state: DocumentUpdateRecommenderState) -> DocumentUpdateRecommenderState:
        """
        Step 4: Generate and Post Recommendations
        
        Implements:
        - Filter High-Priority Findings and separate anomalies
        - Handle anomalies with a manual, templated review
        - Use LLM to generate suggestions for standard findings
        - Post LLM-generated recommendations
        """
        logger.info("Step 4: Generating and posting documentation recommendations")
        
        try:
            # 4.1 Filter High-Priority Findings
            logger.info("Step 4.1: Filtering high-priority findings")
            prioritized_findings = await self._filter_high_priority_findings(
                state.prioritized_finding_list
            )
            state.filtered_high_priority_findings = prioritized_findings

            # Separate anomaly findings from standard findings
            anomaly_findings = [f for f in prioritized_findings if f.get("finding_type") == "Traceability_Anomaly"]
            standard_findings = [f for f in prioritized_findings if f.get("finding_type") != "Traceability_Anomaly"]
            
            # 4.2 Query Existing Suggestions
            logger.info("Step 4.2: Fetching existing suggestions")
            existing_suggestions = await self._query_existing_suggestions(
                state.repository,
                state.pr_number
            )
            state.existing_suggestions = existing_suggestions
            
            # Handle anomaly findings manually
            if anomaly_findings:
                logger.info(f"Handling {len(anomaly_findings)} traceability anomaly finding(s) manually.")
                await self._post_anomaly_review(
                    anomaly_findings,
                    state.repository,
                    state.pr_number,
                    existing_suggestions,
                    state.baseline_map
                )

            # Handle standard findings with LLM
            final_recommendations = []
            generated_suggestions = []

            if standard_findings:
                logger.info(f"Processing {len(standard_findings)} standard finding(s) with LLM.")
                
                # 4.3 Use Current Documentation Context from state
                logger.info("Step 4.3: Using current documentation context from state")
                current_docs = {}
                srs_content = state.document_content.get("srs_content", {})
                sdd_content = state.document_content.get("sdd_content", {})
                for file_path, content in srs_content.items():
                    current_docs[file_path] = {"document_type": "SRS", "content": content}
                for file_path, content in sdd_content.items():
                    current_docs[file_path] = {"document_type": "SDD", "content": content}
                
                # 4.4 Findings Iteration & Suggestion Generation
                logger.info("Step 4.4: Generating suggestions")
                generated_suggestions = await self._llm_generate_suggestions(
                    standard_findings,
                    current_docs,
                    state.logical_change_sets
                )
                state.generated_suggestions = generated_suggestions
                
                # 4.5 Filter Against Existing & Post Details
                logger.info("Step 4.5: Filtering and posting suggestions")
                head_sha = state.pr_event_data.get("pull_request", {}).get("head", {}).get("sha")
                if not head_sha:
                    raise ValueError("Could not determine head SHA for status update.")

                final_recommendations = await self._llm_filter_and_post_suggestions(
                    generated_suggestions,
                    existing_suggestions,
                    state.repository,
                    state.pr_number,
                    state.baseline_map,
                    head_sha
                )
                state.recommendations = final_recommendations
            else:
                logger.info("No standard findings to generate LLM recommendations for.")
                # If there are no standard findings, we might still need to update the CI status
                head_sha = state.pr_event_data.get("pull_request", {}).get("head", {}).get("sha")
                if not head_sha:
                    raise ValueError("Could not determine head SHA for status update.")
                
                # Update CI/CD status based on whether there were anomalies
                critical_generated_count = len(anomaly_findings)
                await self._update_ci_cd_status(state.repository, head_sha, critical_generated_count, 0)

            # Update processing statistics
            state.processing_stats.update({
                "high_priority_findings": len(prioritized_findings),
                "anomaly_findings": len(anomaly_findings),
                "standard_findings_for_llm": len(standard_findings),
                "existing_suggestions": len(existing_suggestions),
                "generated_suggestions": len(generated_suggestions),
                "final_recommendations": len(final_recommendations)
            })
            
            logger.info(f"Step 4: Successfully processed {len(standard_findings)} standard findings and {len(anomaly_findings)} anomalies.")
            
        except Exception as e:
            error_msg = f"Step 4: Error generating recommendations: {str(e)}"
            state.errors.append(error_msg)
            raise
        
        return state
    
    async def _parse_pr_url(self, pr_url: str) -> Dict[str, Any]:
        """Parse GitHub PR URL to extract repository and PR details"""
        
        # Parse the PR URL using regex
        # Supports formats like:
        # https://github.com/owner/repo/pull/123
        # https://github.com/owner/repo/pull/123#issuecomment-123456
        # https://github.com/owner/repo/pull/123/files
        pattern = r'https://github\.com/([^/]+)/([^/]+)/pull/(\d+)'
        match = re.match(pattern, pr_url)
        
        if not match:
            raise ValueError(f"Invalid GitHub PR URL format: {pr_url}")
        
        owner, repo, pr_number = match.groups()
        repository = f"{owner}/{repo}"
        pr_number = int(pr_number)
        
        # Get branch information from GitHub API
        github_token = os.getenv("GITHUB_TOKEN")
        if not github_token:
            logger.warning("GITHUB_TOKEN not found, using default branch 'main'")
            return {
                "repository": repository,
                "pr_number": pr_number,
                "branch": "main"
            }
        
        try:
            # Make API call to get PR details
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"token {github_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
                
                response = await client.get(
                    f"https://api.github.com/repos/{repository}/pulls/{pr_number}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    pr_data = response.json()
                    branch = pr_data.get("base", {}).get("ref", "main")
                    
                    return {
                        "repository": repository,
                        "pr_number": pr_number,
                        "branch": branch
                    }
                else:
                    logger.warning(f"Failed to fetch PR details from GitHub API: {response.status_code}")
                    return {
                        "repository": repository,
                        "pr_number": pr_number,
                        "branch": "main"
                    }
        except Exception as e:
            raise ValueError(f"Error fetching PR details: {str(e)}")
    
    async def _fetch_pr_event_data(self, repository: str, pr_number: int) -> Dict[str, Any]:
        """Fetch PR event data from GitHub REST API with per-commit file changes"""
        
        logger.info(f"Step 1.1: Fetching PR event data from GitHub REST API for {repository}:{pr_number}")
        
        try:
            github_token = os.getenv("GITHUB_TOKEN")
            if not github_token:
                raise ValueError("GITHUB_TOKEN not found")
            
            # Parse repository owner and name
            owner, repo_name = repository.split("/")
            
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
                
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Get PR details
                pr_response = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{pr_number}",
                    headers=headers
                )
                pr_response.raise_for_status()
                pr_data = pr_response.json()
                
                # Get commits for this PR
                commits_response = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{pr_number}/commits",
                    headers=headers
                )
                commits_response.raise_for_status()
                commits_data = commits_response.json()
                
                # Step 2: Get file changes for each commit (N+1 approach)
                enhanced_commits = []
                
                # Process commits with controlled concurrency
                semaphore = asyncio.Semaphore(5)  # Limit concurrent requests
                
                async def fetch_commit_files(commit_data):
                    async with semaphore:
                        try:
                            commit_sha = commit_data["sha"]
                            commit_response = await client.get(
                                f"https://api.github.com/repos/{owner}/{repo_name}/commits/{commit_sha}",
                                headers=headers
                            )
                            commit_response.raise_for_status()
                            commit_details = commit_response.json()
                            
                            # Extract file changes
                            files = commit_details.get("files", [])
                            
                            # Structure commit data with files
                            enhanced_commit = {
                                "sha": commit_data["sha"],
                                "message": commit_data["commit"]["message"],
                                "author": {
                                    "name": commit_data["commit"]["author"]["name"],
                                    "date": commit_data["commit"]["author"]["date"]
                                },
                                "additions": commit_details.get("stats", {}).get("additions", 0),
                                "deletions": commit_details.get("stats", {}).get("deletions", 0),
                                "total_changes": commit_details.get("stats", {}).get("total", 0),
                                "files": []
                            }
                            
                            # Process each file
                            for file_data in files:
                                file_info = {
                                    "filename": file_data.get("filename", ""),
                                    "status": file_data.get("status", ""),
                                    "additions": file_data.get("additions", 0),
                                    "deletions": file_data.get("deletions", 0),
                                    "changes": file_data.get("changes", 0),
                                    "patch": file_data.get("patch", ""),
                                    "blob_url": file_data.get("blob_url", ""),
                                    "raw_url": file_data.get("raw_url", "")
                                }
                                enhanced_commit["files"].append(file_info)
                
                            return enhanced_commit
                            
                        except Exception as e:
                            logger.error(f"Error fetching commit {commit_data['sha']}: {str(e)}")
                            # Return minimal commit data if file fetch fails
                            return {
                                "sha": commit_data["sha"],
                                "message": commit_data["commit"]["message"],
                                "author": {
                                    "name": commit_data["commit"]["author"]["name"],
                                    "date": commit_data["commit"]["author"]["date"]
                                },
                                "additions": 0,
                                "deletions": 0,
                                "total_changes": 0,
                                "files": []
                            }
                
                # Fetch all commit files concurrently
                enhanced_commits = await asyncio.gather(
                    *[fetch_commit_files(commit) for commit in commits_data]
                )
                
                # Structure the data according to expected format
                structured_data = {
                    "action": "opened",
                    "number": pr_number,
                    "pull_request": {
                        "title": pr_data.get("title", ""),
                        "body": pr_data.get("body", ""),
                        "user": {
                            "login": pr_data.get("user", {}).get("login", "")
                        },
                        "base": {
                            "ref": pr_data.get("base", {}).get("ref", "")
                        },
                        "head": {
                            "ref": pr_data.get("head", {}).get("ref", ""),
                            "sha": pr_data.get("head", {}).get("sha", "")
                        }
                    },
                    "repository": {
                        "name": repo_name,
                        "full_name": repository
                    },
                    # Enhanced commit info with per-commit file details
                    "commit_info": {
                        "commits": enhanced_commits,
                        "count": len(enhanced_commits)
                    }
                }
                
                return structured_data
                
        except Exception as e:
            raise ValueError(f"Error fetching PR event data: {str(e)}")
    
    async def _fetch_document_content(self, repository: str, branch: str) -> Dict[str, Any]:
        """Fetch documentation content using Repomix"""
        
        logger.info(f"Step 1.2: Fetching documentation content using Repomix for {repository}:{branch}")
        
        # Use Repomix to scan the repository
        repo_data = await self._scan_repository_with_repomix(repository, branch)
            
        # Extract SDD (Software Design Documents) files
        sdd_content = self._extract_documentation_files(repo_data, [
            "design.md", "sdd.md", "software-design.md", "architecture.md",
            "docs/design.md", "docs/sdd.md", "docs/architecture.md", "doc/sdd.md",
            "traceability.md", "traceability-matrix.md"
        ])
        
        # Extract SRS (Software Requirements Specification) files  
        srs_content = self._extract_documentation_files(repo_data, [
            "requirements.md", "srs.md", "software-requirements.md",
            "docs/requirements.md", "docs/srs.md", "doc/srs.md",
            "documentation/requirements.md"
        ])
        
        # Structure the documentation content
        document_content = {
            "repo_name": repository,
            "branch": branch,
            "sdd_content": sdd_content,
            "srs_content": srs_content,
        }
        
        return document_content         
    
    async def _scan_repository_with_repomix(self, repository: str, branch: str) -> Dict[str, Any]:
        """
        Scan repository using Repomix (borrowed from Baseline Map Creator)
        
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
                    "--ignore", "node_modules,__pycache__,.git,.venv,venv,env,target,build,dist,.next,coverage,.github,.vscode,.env,.env.local,.env.development.local,.env.test.local,.env.production.local"
                ]
                
                logger.debug(f"Running Repomix: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode != 0:
                    raise RuntimeError(f"Repomix failed: {result.stderr}")
                
                # Read and parse the XML output file
                with open(output_file, 'r', encoding='utf-8') as f:
                    xml_content = f.read()
                
                repo_data = self._parse_repomix_xml(xml_content)
                
                logger.debug(f"Repomix scan completed successfully for {repository}:{branch}")
                return repo_data
                
            except subprocess.TimeoutExpired:
                raise RuntimeError("Repomix scan timed out after 5 minutes")
            except Exception as e:
                raise RuntimeError(f"Failed to scan repository with Repomix: {str(e)}")
    
    def _parse_repomix_xml(self, xml_content: str) -> Dict[str, Any]:
        """
        Parse Repomix XML-like output into structured data (borrowed from Baseline Map Creator)
        
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
            logger.warning(f"Repomix XML parsing failed ({e}), attempting fallback parsing")
            return self._parse_repomix_fallback(xml_content)
    
    def _parse_repomix_fallback(self, content: str) -> Dict[str, Any]:
        """
        Fallback parser for Repomix Markdown-style output (borrowed from Baseline Map Creator)
        
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
        
        for _, line in enumerate(lines):
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
    
    async def _llm_classify_individual_changes(self, pr_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Classify individual code changes by passing the entire PR data directly to the LLM.
        Returns classifications organized by commit.
        
        Args:
            pr_data: Complete PR event data with all commits and file changes
            
        Returns:
            List of commits with their classifications
        """
        try:
            # Create output parser for JSON format
            output_parser = JsonOutputParser(pydantic_object=BatchClassificationOutput)

            # Get prompts
            system_message = prompts.individual_code_classification_system_prompt()
            human_prompt = prompts.individual_code_classification_human_prompt(pr_data)

            # Generate JSON response
            response = await self.llm_client.generate_response(
                prompt=human_prompt,
                system_message=system_message + "\n" + output_parser.get_format_instructions(),
                output_format="json",  # Use text so we can parse into Pydantic model
                temperature=0.1  # Low temperature for consistent extraction
            )

            classification_result = response.content
            
            # Create a lookup map for patches from the original PR data
            patch_lookup = {}
            for commit in pr_data.get("commit_info", {}).get("commits", []):
                for file_change in commit.get("files", []):
                    patch_lookup[(commit["sha"], file_change["filename"])] = file_change.get("patch", "")
            
            # Convert Pydantic model to our internal format and add the patch back
            commits_with_classifications = []
            for commit_data in classification_result["commits"]:
                commit_dict = {
                    "commit_hash": commit_data["commit_hash"],
                    "commit_message": commit_data["commit_message"],
                    "classifications": []
                }
                
                for classification in commit_data["classifications"]:
                    commit_hash = commit_data["commit_hash"]
                    file_path = classification["file"]
                    
                    # Add the patch from the lookup map
                    patch = patch_lookup.get((commit_hash, file_path), "")
                    
                    commit_dict["classifications"].append({
                        "file": file_path,
                        "type": classification["type"],
                        "scope": classification["scope"],
                        "nature": classification["nature"],
                        "volume": classification["volume"],
                        "reasoning": classification["reasoning"],
                        "patch": patch
                    })
                
                commits_with_classifications.append(commit_dict)
            
            return commits_with_classifications
            
        except Exception as e:
            err_message = f"Step 2.1: Error in _llm_classify_individual_changes: {str(e)}"
            logger.error(err_message)
            raise
    
    async def _llm_group_classified_changes(self, commits_with_classifications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Group classified changes into logical change sets using commit messages as semantic keys.
        
        This method uses commit messages to understand the development intent and groups
        file changes that serve the same logical purpose or feature development goal.
        
        Args:
            commits_with_classifications: List of commits with their file classifications
            commit_info: Commit information containing messages and metadata
            
        Returns:
            List of logical change sets with grouped changes
        """
        try:
            # Create output parser for JSON format
            output_parser = JsonOutputParser(pydantic_object=ChangeGroupingOutput)

            # Get prompts
            system_message = prompts.change_grouping_system_prompt()
            human_prompt = prompts.change_grouping_human_prompt(commits_with_classifications)
            
            # Generate JSON response
            response = await self.llm_client.generate_response(
                prompt=human_prompt,
                system_message=system_message + "\n" + output_parser.get_format_instructions(),
                output_format="json",  # Use text so we can parse into Pydantic model
                temperature=0.1  # Low temperature for consistent grouping
            )

            # Parse the JSON response into Pydantic model
            grouping_result = response.content
            
            # Create a lookup map for patches from the original classifications using a composite key
            patch_lookup = {}
            for commit in commits_with_classifications:
                for classification in commit.get("classifications", []):
                    # Create a unique composite key from the classification details
                    composite_key = (
                        classification["file"],
                        classification["type"],
                        classification["scope"],
                        classification["nature"],
                        classification["volume"],
                        classification["reasoning"]
                    )
                    patch_lookup[composite_key] = classification.get("patch", "")

            logical_change_sets = []
            for change_set_data in grouping_result["logical_change_sets"]:
                changes_with_patch = []
                for change in change_set_data["changes"]:
                    change_dict = change
                    
                    # Recreate the same composite key to find the correct patch
                    composite_key = (
                        change_dict["file"],
                        change_dict["type"],
                        change_dict["scope"],
                        change_dict["nature"],
                        change_dict["volume"],
                        change_dict["reasoning"]
                    )
                    change_dict["patch"] = patch_lookup.get(composite_key, "")
                    changes_with_patch.append(change_dict)
                
                logical_change_sets.append({
                    "name": change_set_data["name"],
                    "description": change_set_data["description"],
                    "changes": changes_with_patch
                })
            
            return logical_change_sets
                
        except Exception as e:
            raise
    
    async def _filter_high_priority_findings(self, prioritized_findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter findings to include only high-priority ones based on the criteria:
        - Likelihood >= 'Possibly' AND Severity >= 'Minor' 
        - OR critical finding types (Documentation_Gap, Outdated_Documentation, Traceability_Anomaly)
        """
        filtered_findings = []
        
        for finding in prioritized_findings:
            likelihood = finding.get("likelihood", "")
            severity = finding.get("severity", "")
            finding_type = finding.get("finding_type", "")
            
            # Always include critical finding types
            if finding_type in ["Documentation_Gap", "Outdated_Documentation", "Traceability_Anomaly"]:
                filtered_findings.append(finding)
                continue
            
            # For Standard_Impact, check minimum thresholds
            likelihood_meets_threshold = likelihood in ["Very Likely", "Likely"]
            severity_meets_threshold = severity in ["Fundamental", "Major", "Moderate"]
            
            if likelihood_meets_threshold and severity_meets_threshold:
                filtered_findings.append(finding)
                
        return filtered_findings
    
    async def _query_existing_suggestions(self, repository: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Query existing documentation suggestions for the PR by fetching previous agent reviews.
        This prevents posting duplicate recommendations.
        """
        try:
            github_token = os.getenv("GITHUB_TOKEN")
            if not github_token:
                logger.warning("GITHUB_TOKEN not found, cannot fetch existing suggestions")
                return []
            
            # Parse repository owner and name
            owner, repo_name = repository.split("/")
            
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Get all reviews on the PR, as recommendations are posted as reviews
                reviews_response = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{pr_number}/reviews",
                    headers=headers
                )
                reviews_response.raise_for_status()
                reviews_data = reviews_response.json()
                
                # Filter for reviews made by the bot/agent (GitHub Actions bot)
                bot_reviews = []
                for review in reviews_data:
                    # Check if the review is from our agent
                    user_login = review.get("user", {}).get("login", "")
                    review_body = review.get("body", "")
                    
                    # Look for our agent's signature or the GitHub Actions bot username
                    if (user_login == "github-actions[bot]" or 
                        "Docureco Agent" in review_body):
                        
                        # Use 'submitted_at' as reviews don't have a separate 'updated_at'
                        bot_reviews.append({
                            "id": review.get("id"),
                            "body": review_body,
                            "created_at": review.get("submitted_at"),
                            "updated_at": review.get("submitted_at")
                        })
                
                logger.info(f"Found {len(bot_reviews)} existing review comments from the agent.")
                return bot_reviews
                
        except Exception as e:
            logger.error(f"Error fetching existing suggestions: {str(e)}")
            return []
    
    async def _llm_generate_suggestions(self, filtered_findings: List[Dict[str, Any]], current_docs: Dict[str, Any], logical_change_sets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate specific documentation update recommendations using LLM.
        Processes each target document in parallel for focused, high-quality recommendations.
        """
        try:
            if not filtered_findings or not current_docs:
                return []

            # Create a lookup map from document path to relevant findings
            doc_to_findings_map: Dict[str, List[Dict[str, Any]]] = {doc_path: [] for doc_path in current_docs}
            
            # Separate documentation gaps, as they are relevant to all documents
            doc_gap_findings = [f for f in filtered_findings if f.get("finding_type") == "Documentation_Gap"]
            other_findings = [f for f in filtered_findings if f.get("finding_type") != "Documentation_Gap"]

            # Add documentation gaps to all documents
            for doc_path in doc_to_findings_map:
                doc_to_findings_map[doc_path].extend(doc_gap_findings)

            # Distribute other findings to the relevant document based on affected_element_id
            for finding in other_findings:
                affected_id = finding.get("affected_element_id", "")
                if not affected_id:
                    continue
                
                # Use regex to extract the file path from the ID (e.g., "REQ-path/to/doc.md-001")
                match = re.match(r'^(?:REQ|DE)-(.+)-\d{3}$', affected_id)
                if match:
                    file_path_from_id = match.group(1)
                    
                    # Check if this extracted path corresponds to a known document
                    if file_path_from_id in doc_to_findings_map:
                        doc_to_findings_map[file_path_from_id].append(finding)

            # Create a list of async tasks, one for each document that has relevant findings
            tasks = []
            for doc_path, relevant_findings in doc_to_findings_map.items():
                if not relevant_findings:
                    logger.info(f"No relevant findings for document {doc_path}, skipping task creation.")
                    continue

                doc_info = current_docs[doc_path]
                task = self._generate_suggestions_for_document(
                    doc_path,
                    doc_info,
                    relevant_findings, # Pass only the filtered list
                    logical_change_sets
                )
                tasks.append(task)
            
            if not tasks:
                logger.info("No documents with relevant findings to generate suggestions for.")
                return []
            
            # Run all tasks in parallel
            document_group_results = await asyncio.gather(*tasks)
            
            # Combine results from all tasks
            all_document_groups = []
            for group_list in document_group_results:
                if group_list:
                    all_document_groups.extend(group_list)
            
            logger.info(f"Generated recommendations for {len(all_document_groups)} document(s) from {len(filtered_findings)} findings.")
            return all_document_groups
            
        except Exception as e:
            logger.error(f"Error in parallel suggestion generation: {str(e)}")
            return []

    async def _generate_suggestions_for_document(self, doc_path: str, doc_info: Dict[str, Any], relevant_findings: List[Dict[str, Any]], logical_change_sets: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        """Helper function to generate suggestions for a single document."""
        try:
            # The filtering is now done in the calling function, `_llm_generate_suggestions`
            output_parser = JsonOutputParser(pydantic_object=RecommendationGenerationOutput)
            
            system_message = prompts.recommendation_generation_system_prompt()
            human_prompt = prompts.recommendation_generation_human_prompt(
                relevant_findings, doc_path, doc_info, logical_change_sets
            )
            
            response = await self.llm_client.generate_response(
                prompt=human_prompt,
                system_message=system_message + "\n" + output_parser.get_format_instructions(),
                output_format="json",
                temperature=0.1
            )
            
            # Parse the structured response
            recommendation_result = response.content
            document_groups = recommendation_result.get("document_groups", [])
            
            if document_groups:
                logger.info(f"Successfully generated {len(document_groups[0].get('recommendations', []))} recommendations for {doc_path}")
                return document_groups
            else:
                logger.info(f"No relevant recommendations generated for {doc_path}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating suggestions for document {doc_path}: {str(e)}")
            return None
    
    async def _llm_filter_and_post_suggestions(self, generated_suggestions: List[Dict[str, Any]], existing_suggestions: List[Dict[str, Any]], repository: str, pr_number: int, baseline_map: Optional[BaselineMapModel], head_sha: str) -> List[Dict[str, Any]]:
        """
        Filter generated suggestions against existing ones and post new recommendations to PR.
        Implements duplication filtering and CI/CD status management
        """
        try:
            # Filter out duplicate suggestions by comparing with existing ones
            output_parser = JsonOutputParser(pydantic_object=FilteredSuggestionsOutput)
            
            system_message = prompts.suggestion_filtering_system_prompt()
            human_prompt = prompts.suggestion_filtering_human_prompt(generated_suggestions, existing_suggestions)
            
            response = await self.llm_client.generate_response(
                prompt=human_prompt,
                system_message=system_message + "\n" + output_parser.get_format_instructions(),
                output_format="json",
                temperature=0.1
            )
            
            filtered_suggestions = response.content["new_suggestions"]
            
            # Base CI/CD status on pre-filtered suggestions to reflect true documentation state
            critical_generated_count = 0
            total_generated_count = 0
            for document_group in generated_suggestions:
                for suggestion in document_group.get('recommendations', []):
                    total_generated_count += 1
                    if suggestion.get('priority', '').upper() in ['HIGH', 'CRITICAL']:
                        critical_generated_count += 1
            
            await self._update_ci_cd_status(
                repository, 
                head_sha,
                critical_generated_count, 
                total_generated_count
            )
            
            # Use GitHub Review API for the filtered (posted) suggestions
            logger.info(f"Creating comprehensive PR review for {len(filtered_suggestions)} new suggestions")
            review_posted = await self._create_pr_review_with_suggestions(repository, pr_number, filtered_suggestions, baseline_map)
            
            # Log statistics based on what was actually posted
            critical_posted_count = 0
            total_posted_count = 0
            if review_posted:
                for document_group in filtered_suggestions:
                    for suggestion in document_group.get('recommendations', []):
                        total_posted_count += 1
                        if suggestion.get('priority', '').upper() in ['HIGH', 'CRITICAL']:
                            critical_posted_count += 1
            
            logger.info(f"Posted {total_posted_count} new recommendations ({critical_posted_count} critical) for {len(filtered_suggestions)} document(s)")
            return filtered_suggestions
            
        except Exception as e:
            logger.error(f"Error in filter and post suggestions: {str(e)}")
            return []
    
    async def _update_ci_cd_status(self, repository: str, head_sha: str, critical_count: int, total_count: int) -> None:
        """Update CI/CD check status based on recommendations."""
        try:
            github_token = os.getenv("GITHUB_TOKEN")
            if not github_token:
                logger.warning("GITHUB_TOKEN not found, cannot update CI/CD status")
                return
            
            owner, repo_name = repository.split("/")
            
            # Determine status based on critical recommendations
            if critical_count > 0:
                conclusion = "failure"
                title = "Critical Documentation Updates Required"
                summary = f"⚠️ Found {critical_count} critical documentation issue(s) that need to be addressed."
            elif total_count > 0:
                conclusion = "neutral"
                title = "Documentation Recommendations Available"
                summary = f"📝 Found {total_count} documentation recommendation(s)."
            else:
                conclusion = "success"
                title = "No Documentation Updates Needed"
                summary = "✅ All relevant documentation appears to be up-to-date."
            
            logger.info(f"CI/CD Status for {head_sha}: {conclusion} - {summary}")
            
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json"
            }
            
            check_run_data = {
                "name": "Docureco Agent",
                "head_sha": head_sha,
                "status": "completed",
                "conclusion": conclusion,
                "output": {
                    "title": title,
                    "summary": summary
                }
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"https://api.github.com/repos/{owner}/{repo_name}/check-runs",
                    headers=headers,
                    json=check_run_data
                )
                
                if response.status_code == 201:
                    logger.info(f"Successfully created check run for commit {head_sha}")
                else:
                    logger.error(f"Failed to create check run: {response.status_code} - {response.text}")
            
        except Exception as e:
            logger.error(f"Error updating CI/CD status: {str(e)}")

    async def _post_pr_comment_with_id(self, repository: str, pr_number: int, comment_body: str) -> Optional[int]:
        """Post a comment and return the comment ID for threading"""
        try:
            github_token = os.getenv("GITHUB_TOKEN")
            if not github_token:
                logger.error("GITHUB_TOKEN not found, cannot post comment")
                return None
            
            owner, repo_name = repository.split("/")
            
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json"
            }
            
            comment_data = {"body": comment_body}
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"https://api.github.com/repos/{owner}/{repo_name}/issues/{pr_number}/comments",
                    headers=headers,
                    json=comment_data
                )
                
                if response.status_code == 201:
                    comment_data = response.json()
                    logger.info(f"Successfully posted comment to PR #{pr_number}")
                    return comment_data.get("id")
                else:
                    logger.error(f"Failed to post comment: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error posting PR comment: {str(e)}")
            return None

    async def _create_pr_review_with_suggestions(self, repository: str, pr_number: int, document_groups: List[Dict[str, Any]], baseline_map: Optional[BaselineMapModel]) -> bool:
        """
        Post a separate PR review for each document group. Use 'REQUEST_CHANGES' if any recommendation in the group is high/critical priority, otherwise 'COMMENT'.
        """
        try:
            github_token = os.getenv("GITHUB_TOKEN")
            if not github_token:
                logger.error("GITHUB_TOKEN not found, cannot create review")
                return False
            
            owner, repo_name = repository.split("/")
            
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json"
            }
            
            all_success = True
            for group in document_groups:
                summary = group.get('summary', {})
                recommendations = group.get('recommendations', [])

                has_critical = any(r.get('priority', '').upper() in ['HIGH', 'CRITICAL'] for r in recommendations)
                event_type = 'REQUEST_CHANGES' if has_critical else 'COMMENT'
                
                review_body = await self._create_review_summary([group], baseline_map)
                review_data = {
                    "body": review_body,
                    "event": event_type
                }
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{pr_number}/reviews",
                        headers=headers,
                        json=review_data
                    )
                    if response.status_code == 200:
                        review_data = response.json()
                        review_id = review_data.get("id")
                        logger.info(f"Successfully created PR review #{review_id} for document group {summary.get('target_document', 'Unknown')}")
                    else:
                        logger.error(f"Failed to create review for document group {summary.get('target_document', 'Unknown')}: {response.status_code} - {response.text}")
                        all_success = False
                        
            return all_success
        
        except Exception as e:
            logger.error(f"Error creating PR reviews: {str(e)}")
            return False

    async def _create_review_summary(self, document_groups: List[Dict[str, Any]], baseline_map: Optional[BaselineMapModel]) -> str:
        """Create the main review summary with detailed suggestions and copy-paste ready content"""
        # Extract all recommendations from document groups
        all_suggestions = []
        for group in document_groups:
            all_suggestions.extend(group.get('recommendations', []))
        
        total_suggestions = len(all_suggestions)
        high_priority = sum(1 for s in all_suggestions if s.get('priority', '').upper() == 'HIGH')
        
        # Create detailed breakdown by document group
        group_details = []
        suggestion_counter = 1
        
        for group in document_groups:
            summary = group.get('summary', {})
            recommendations = group.get('recommendations', [])
            target_document = summary.get('target_document', 'Unknown')
            group_text = f"""# 🤖 Docureco Agent - 📄 `{target_document}` Recommendations ({len(recommendations)} total)

{summary.get('overview', 'No overview provided')} Affected sections: `{', '.join(summary.get('sections_affected', []))}`.
"""
            
            # Add individual recommendations
            for recommendation in recommendations:
                priority = recommendation.get('priority', 'Medium').upper()
                priority_icon = "🔴" if priority in ['HIGH', 'CRITICAL'] else "🟡" if priority == 'MEDIUM' else "🟢"
                
                suggested_content = recommendation.get('suggested_content', 'No content provided').strip()
                section = recommendation.get('section', 'Unknown')
                action = recommendation.get('recommendation_type', 'Unknown').upper()
                
                # Ensure the diff block is correctly formatted, whether the LLM provided the fence or not
                if suggested_content.startswith('```diff'):
                    diff_block = suggested_content
                else:
                    diff_block = f"```diff\n{suggested_content}\n```"

                # Create the suggestion with clean, consistent markdown
                suggestion_parts = [
                    f"### {priority_icon} Suggestion {suggestion_counter}: {action} in `{section}`",
                    f"**[{priority}]** {recommendation.get('what_to_update', 'No description provided')}",
                    recommendation.get('why_update_needed', 'No reason provided'),
                    f"\n**📝 Suggested Change:**",
                    diff_block,
                    f"> 💡 **How to apply:** Add lines with `+`, remove lines with `-`, and keep context lines unchanged."
                ]
                
                group_text += "\n\n---\n\n" + "\n\n".join(suggestion_parts)
                suggestion_counter += 1       
            
            group_details.append(group_text)
        
        suggestions_text = "".join(group_details)
        
        return f"""
{suggestions_text}

### 📊 Summary:
- **Total Suggestions**: {total_suggestions}
- **High Priority**: {high_priority}
- **Medium/Low Priority**: {total_suggestions - high_priority}
---
*This review was generated automatically by Docureco Agent based on code changes in this PR*"""

    async def _post_anomaly_review(self, anomaly_findings: List[Dict[str, Any]], repository: str, pr_number: int, existing_suggestions: List[Dict[str, Any]], baseline_map: Optional[BaselineMapModel]) -> bool:
        """
        Posts a separate, templated PR review for traceability anomaly findings.
        This process is manual and does not involve the LLM.
        """
        logger.info("Creating a dedicated review for traceability anomalies.")

        # Check if a similar comment already exists to avoid spam
        for review in existing_suggestions:
            if "Traceability Anomaly Detected" in review.get("body", ""):
                logger.info("An existing traceability anomaly review was found. Skipping posting a new one.")
                return False

        # Extract affected files from the anomaly findings
        affected_files = sorted(list(set([
            finding.get("affected_element_reference_id") 
            for finding in anomaly_findings 
            if finding.get("affected_element_reference_id")
        ])))

        # Create the templated review body
        review_body = f"""# 🤖 Docureco Agent - 🔴 Traceability Anomaly Detected

A traceability anomaly means there is a mismatch between the code files and the documentation map (the baseline map). This is **not** an issue with the documentation files (like `sdd.md` or `srs.md`) themselves, but with the map that connects them to the code.

**📁 Affected Files with Anomalies:**
"""
        for file in affected_files:
            review_body += f"- `{file}`\n"

        review_body += """
**🛠️ How to Fix**
To resolve this, the baseline map needs to be regenerated. This will re-scan the repository and fix the broken links.

**Please re-run the `Docureco Agent: Baseline Map` GitHub Action on the `main` branch to regenerate the map.**

<details>
<summary>Why this happens</summary>
Traceability anomalies can occur when:
- Files are moved or renamed without the change being tracked correctly.
- The baseline map is outdated due to recent merges that were not processed.
- There are manual changes to the repository structure that the system did not anticipate.
</details>
"""
        # Add the formatted baseline map for context
        review_body += "\n\n" + self._format_baseline_map_for_comment(baseline_map, affected_files, "")

        # Post the review to GitHub
        try:
            github_token = os.getenv("GITHUB_TOKEN")
            if not github_token:
                logger.error("GITHUB_TOKEN not found, cannot create review")
                return False
            
            owner, repo_name = repository.split("/")
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json",
            }
            
            review_data = {
                "body": review_body,
                "event": "REQUEST_CHANGES"  # Anomalies should block changes
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{pr_number}/reviews",
                    headers=headers,
                    json=review_data
                )
                response.raise_for_status()
                logger.info(f"Successfully posted traceability anomaly review to PR #{pr_number}.")
                return True
        except Exception as e:
            logger.error(f"Failed to post traceability anomaly review: {str(e)}")
            return False

    def _format_baseline_map_for_comment(self, baseline_map: Optional[BaselineMapModel], affected_files: List[str], how_to_fix: str) -> str:
        """Format baseline map into a collapsible markdown block for GitHub comments"""
        if not baseline_map:
            return """
<details>
<summary>📋 Current Traceability Map</summary>

No baseline map found. Please run the Docureco Agent: Baseline Map GitHub Action to create one.

</details>
"""
        
        # Check if baseline map is completely empty
        req_count = len(baseline_map.requirements or [])
        de_count = len(baseline_map.design_elements or [])
        cc_count = len(baseline_map.code_components or [])
        tl_count = len(baseline_map.traceability_links or [])
        
        if req_count == 0 and de_count == 0 and cc_count == 0 and tl_count == 0:
            return """
<details>
<summary>📋 Current Traceability Map</summary>

**⚠️ Empty Baseline Map Found**

The baseline map exists but contains no elements. This usually indicates:
1. The baseline map was not properly generated
2. The repository has no documentation files (SRS/SDD) to map
3. The baseline map creation process failed

**Recommended Action**: Re-run the Docureco Agent: Baseline Map GitHub Action to properly generate the traceability map.

**Total Elements**: 0 requirements, 0 design elements, 0 code components, 0 traceability links

</details>
"""
        
        # Format requirements
        requirements_section = ""
        if baseline_map.requirements:
            requirements_section = "### Requirements\n"
            for req in baseline_map.requirements:
                requirements_section += f"- **{req.id}**: {req.title}\n"
        
        # Format design elements
        design_elements_section = ""
        if baseline_map.design_elements:
            design_elements_section = "\n### Design Elements\n"
            for de in baseline_map.design_elements:
                design_elements_section += f"- **{de.id}**: {de.name} ({de.type})\n"
        
        # Format code components
        code_components_section = ""
        if baseline_map.code_components:
            code_components_section = "\n### Code Components\n"
            for cc in baseline_map.code_components:
                code_components_section += f"- **{cc.id}**: {cc.path}\n"
        
        # Format traceability links
        traceability_links_section = ""
        if baseline_map.traceability_links:
            traceability_links_section = "\n### Traceability Links\n"
            for link in baseline_map.traceability_links:
                traceability_links_section += f"- {link.source_id} → {link.target_id}\n"
        
        return f"""
**Traceability Anomaly Detected for the following files**: 
{', '.join([f'`{file}`' for file in affected_files])}

**How to Fix**
{how_to_fix}

<details>
<summary>📋 Current Traceability Map</summary>

{requirements_section}{design_elements_section}{code_components_section}{traceability_links_section}

**Total Elements**: {req_count} requirements, {de_count} design elements, {cc_count} code components, {tl_count} traceability links

</details>
"""

def create_document_update_recommender(
    llm_client: Optional[DocurecoLLMClient] = None,
    primary_baseline_branch: str = "main"
) -> DocumentUpdateRecommenderWorkflow:
    """
    Factory function to create Document Update Recommender workflow
    
    Args:
        llm_client: Optional LLM client
        primary_baseline_branch: Primary branch to look for baseline maps (default: "main")
        
    Returns:
        DocumentUpdateRecommenderWorkflow: Configured workflow
    """
    return DocumentUpdateRecommenderWorkflow(
        llm_client=llm_client,
        primary_baseline_branch=primary_baseline_branch
    )

# Export main classes
__all__ = ["DocumentUpdateRecommenderWorkflow", "DocumentUpdateRecommenderState", "create_document_update_recommender"] 