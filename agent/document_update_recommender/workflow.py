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
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
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
from agent.models.docureco_models import (
    BaselineMapModel,
    DocumentationRecommendationModel,
    RecommendationType,
    RecommendationStatus
)
from agent.database import create_baseline_map_repository
from agent.document_update_recommender.prompts import DocumentUpdateRecommenderPrompts as prompts

logger = logging.getLogger(__name__)

# Structured output models
class CodeChangeClassification(BaseModel):
    """Structured output for individual code change classification"""
    file: str = Field(description="Path to the changed file")
    type: str = Field(description="Type of change (Addition, Deletion, Modification, Rename)")
    scope: str = Field(description="Scope of change (Function/Method, Class, Module, etc.)")
    nature: str = Field(description="Nature of change (New Feature, Bug Fix, Refactoring, etc.)")
    volume: str = Field(description="Volume of change (Trivial, Small, Medium, Large, Very Large)")
    reasoning: str = Field(description="Brief explanation of the classification")

class CommitWithClassifications(BaseModel):
    """Structured output for a commit with its file classifications"""
    commit_hash: str = Field(description="SHA hash of the commit")
    commit_message: str = Field(description="Commit message")
    classifications: List[CodeChangeClassification] = Field(description="List of classified file changes for this commit")

class BatchClassificationOutput(BaseModel):
    """Structured output for batch classification organized by commits"""
    commits: List[CommitWithClassifications] = Field(description="List of commits with their classified changes")

class LogicalChangeSet(BaseModel):
    """Structured output for logical change sets"""
    name: str = Field(description="Descriptive name for the logical change set")
    description: str = Field(description="Brief description of what this change set accomplishes")
    changes: List[Dict[str, Any]] = Field(description="Array of files with classifications that belong to this logical change set")

class ChangeGroupingOutput(BaseModel):
    """Structured output for grouping changes into logical change sets"""
    logical_change_sets: List[LogicalChangeSet] = Field(description="List of logical change sets")

class DocumentationRecommendation(BaseModel):
    """Structured output for documentation recommendations"""
    target_document: str = Field(description="Document that needs updating")
    section: str = Field(description="Specific section or location")
    recommendation_type: str = Field(description="Type of update (UPDATE, CREATE, DELETE, REVIEW)")
    priority: str = Field(description="Priority level (HIGH, MEDIUM, LOW)")
    what_to_update: str = Field(description="What needs to be changed")
    where_to_update: str = Field(description="Exact location or section reference")
    why_update_needed: str = Field(description="Rationale based on code changes")
    how_to_update: str = Field(description="Step-by-step guidance")
    suggested_content: str = Field(default="", description="Specific content suggestions")

class RecommendationGenerationOutput(BaseModel):
    """Structured output for recommendation generation"""
    recommendations: List[DocumentationRecommendation] = Field(description="List of generated recommendations")

@dataclass
class DocumentUpdateRecommenderState:
    """State for the Document Update Recommender workflow"""
    repository: str
    pr_number: int
    branch: str
    
    # Step 1: Scan PR - PR Event Data and Context
    pr_event_data: Dict[str, Any] = field(default_factory=dict)
    document_content: Dict[str, Any] = field(default_factory=dict)
    commit_info: Dict[str, Any] = field(default_factory=dict)
    changed_files_list: List[str] = field(default_factory=list)
    
    # Step 2: Analyze Code Changes - Classification and Grouping
    classified_changes: List[Dict[str, Any]] = field(default_factory=list)
    logical_change_sets: List[Dict[str, Any]] = field(default_factory=list)
    
    # Step 3: Assess Documentation Impact - Traceability and Impact Analysis
    baseline_map: Optional[BaselineMapModel] = None
    traceability_map: Dict[str, Any] = field(default_factory=dict)
    potentially_impacted_elements: List[Dict[str, Any]] = field(default_factory=list)
    prioritized_finding_list: List[Dict[str, Any]] = field(default_factory=list)
    
    # Step 4: Generate and Post Recommendations - Suggestion Generation
    filtered_high_priority_findings: List[Dict[str, Any]] = field(default_factory=list)
    existing_suggestions: List[Dict[str, Any]] = field(default_factory=list)
    generated_suggestions: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[DocumentationRecommendationModel] = field(default_factory=list)
    
    # Workflow metadata
    errors: List[str] = field(default_factory=list)
    processing_stats: Dict[str, int] = field(default_factory=dict)

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
                 baseline_map_repo = None):
        """
        Initialize Document Update Recommender workflow
        
        Args:
            llm_client: Optional LLM client for analysis and recommendations
            baseline_map_repo: Optional repository for baseline map operations
        """
        self.llm_client = llm_client or DocurecoLLMClient()
        self.baseline_map_repo = baseline_map_repo or create_baseline_map_repository()
        
        self.workflow = self._build_workflow()
        self.memory = MemorySaver()
        
        logger.info("Initialized Document Update Recommender Workflow")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow with conditional logic"""
        workflow = StateGraph(DocumentUpdateRecommenderState)
        
        # Add nodes for each step of the 5-step process
        workflow.add_node("scan_pr", self._scan_pr)
        workflow.add_node("analyze_code_changes", self._analyze_code_changes)
        workflow.add_node("assess_documentation_impact", self._assess_documentation_impact)
        # workflow.add_node("generate_and_post_recommendations", self._generate_and_post_recommendations)
        
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
        logical_change_sets = await self._llm_group_classified_changes(
            commits_with_classifications,
            state.pr_event_data.get("commit_info", {})
        )
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
            baseline_map_data = await self.baseline_map_repo.get_baseline_map(state.repository, state.branch)
            if not baseline_map_data:
                logger.warning("No baseline map found - terminating workflow")
                return state    # Terminate workflow if no baseline map is found
            
            state.baseline_map = baseline_map_data
            
            # Process all file changes in one pass to determine traceability status and detect documentation changes
            changes_with_status, documentation_changes = await self._determine_traceability_status_and_detect_docs(
                state.logical_change_sets, 
                baseline_map_data,
                state.document_content
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
            prioritized_findings = await self._assess_likelihood_and_severity(
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

    async def _determine_traceability_status_and_detect_docs(self, logical_change_sets: List[Dict[str, Any]], baseline_map_data: BaselineMapModel, document_content: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
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
        
        Returns status according to Table III.1 in BAB III.md.
        """
        is_in_baseline = file_path in code_component_lookup
        
        if change_type == "addition":
            return "anomaly (addition unmapped)" if is_in_baseline else "gap"
        elif change_type == "deletion":
            return "outdated" if is_in_baseline else "anomaly (deletion unmapped)"
        elif change_type == "modification":
            return "modification" if is_in_baseline else "anomaly (modification unmapped)"
        elif change_type == "rename":
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
        path_to_component_id = {}
        if baseline_map_data.code_components:
            for component in baseline_map_data.code_components:
                path_to_component_id[component.path] = component.id
        
        # Build mappings from traceability links (handling many-to-many relationships)
        if baseline_map_data.traceability_links:
            for link in baseline_map_data.traceability_links:
                # Code-to-design mapping (bidirectional)
                if link.source_type == "CodeComponent" and link.target_type == "DesignElement":
                    if link.source_id not in code_to_design_map:
                        code_to_design_map[link.source_id] = []
                    if link.target_id not in code_to_design_map[link.source_id]:
                        code_to_design_map[link.source_id].append(link.target_id)
                elif link.source_type == "DesignElement" and link.target_type == "CodeComponent":
                    if link.target_id not in code_to_design_map:
                        code_to_design_map[link.target_id] = []
                    if link.source_id not in code_to_design_map[link.target_id]:
                        code_to_design_map[link.target_id].append(link.source_id)
                
                # Design-to-design mapping (bidirectional)
                elif link.source_type == "DesignElement" and link.target_type == "DesignElement":
                    # Source -> Target
                    if link.source_id not in design_to_design_map:
                        design_to_design_map[link.source_id] = []
                    if link.target_id not in design_to_design_map[link.source_id]:
                        design_to_design_map[link.source_id].append(link.target_id)
                    
                    # Target -> Source (bidirectional)
                    if link.target_id not in design_to_design_map:
                        design_to_design_map[link.target_id] = []
                    if link.source_id not in design_to_design_map[link.target_id]:
                        design_to_design_map[link.target_id].append(link.source_id)
                
                # Design-to-requirement mapping (bidirectional)
                elif link.source_type == "DesignElement" and link.target_type == "Requirement":
                    if link.source_id not in design_to_requirement_map:
                        design_to_requirement_map[link.source_id] = []
                    if link.target_id not in design_to_requirement_map[link.source_id]:
                        design_to_requirement_map[link.source_id].append(link.target_id)
                elif link.source_type == "Requirement" and link.target_type == "DesignElement":
                    if link.target_id not in design_to_requirement_map:
                        design_to_requirement_map[link.target_id] = []
                    if link.source_id not in design_to_requirement_map[link.target_id]:
                        design_to_requirement_map[link.target_id].append(link.source_id)
        
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
                if status in ["modification", "anomaly (addition unmapped)", "rename", "outdated"]:
                    if file_path in path_to_component_id:
                        component_id = path_to_component_id[file_path]
                        if component_id in code_to_design_map:
                            design_elements = code_to_design_map[component_id]
                            
                            if status in ["modification", "anomaly (addition unmapped)", "rename"]:
                                dide.update(design_elements)
                            elif status == "outdated":
                                ode.update(design_elements)
                
                # Handle gap and anomaly findings directly for this change set
                elif status in ["gap", "anomaly (addition unmapped)", "anomaly (deletion unmapped)", 
                              "anomaly (modification unmapped)", "anomaly (rename unmapped)", "anomaly (unknown change type)"]:
                    
                    if status == "gap":
                        finding_type = "Documentation_Gap"
                    else:
                        finding_type = "Traceability_Anomaly"
                    
                    finding = {
                        "finding_type": finding_type,
                        "affected_element_type": "CodeComponent",
                        "affected_element_id": file_path,
                        "trace_path_type": None,
                        "source_change_set": change_set_name,
                        "anomaly_type": status if finding_type == "Traceability_Anomaly" else None
                    }
                    change_set_findings.append(finding)
            
            # Trace Indirect Impact on Design Elements (IIDE) for this change set
            iide = set()  # Indirectly Impacted Design Elements for this change set
            
            for design_element in dide:
                if design_element in design_to_design_map:
                    related_elements = design_to_design_map[design_element]
                    iide.update(related_elements)
            
            # Combine to form Potentially Impacted Design Elements (PIDE) for this change set
            pide = dide.union(iide)
            
            # Trace to Requirements for this change set
            pir = set()  # Potentially Impacted Requirements for this change set
            or_set = set()  # Outdated Requirements for this change set
            
            # Trace PIDE to requirements
            for design_element in pide:
                if design_element in design_to_requirement_map:
                    requirements = design_to_requirement_map[design_element]
                    pir.update(requirements)
            
            # Trace ODE to requirements  
            for design_element in ode:
                if design_element in design_to_requirement_map:
                    requirements = design_to_requirement_map[design_element]
                    or_set.update(requirements)
            
            # Form Finding Records for this change set
            # Standard Impact findings for PIDE and PIR
            for design_element in pide:
                finding = {
                    "finding_type": "Standard_Impact",
                    "affected_element_type": "DesignElement", 
                    "affected_element_id": design_element,
                    "trace_path_type": "Direct" if design_element in dide else "Indirect",
                    "source_change_set": change_set_name
                }
                change_set_findings.append(finding)
            
            for requirement in pir:
                finding = {
                    "finding_type": "Standard_Impact",
                    "affected_element_type": "Requirement",
                    "affected_element_id": requirement, 
                    "trace_path_type": "Direct",
                    "source_change_set": change_set_name
                }
                change_set_findings.append(finding)
            
            # Outdated Documentation findings for ODE and OR
            for design_element in ode:
                finding = {
                    "finding_type": "Outdated_Documentation",
                    "affected_element_type": "DesignElement",
                    "affected_element_id": design_element,
                    "trace_path_type": None,
                    "source_change_set": change_set_name
                }
                change_set_findings.append(finding)
            
            for requirement in or_set:
                finding = {
                    "finding_type": "Outdated_Documentation", 
                    "affected_element_type": "Requirement",
                    "affected_element_id": requirement,
                    "trace_path_type": None,
                    "source_change_set": change_set_name
                }
                change_set_findings.append(finding)
            
            # Add all findings from this change set to the overall findings
            all_findings.extend(change_set_findings)
        
        return all_findings

    async def _assess_likelihood_and_severity(self, findings: List[Dict[str, Any]], logical_change_sets: List[Dict[str, Any]], documentation_changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Assess likelihood and severity for each finding using LLM, considering existing documentation updates.
        
        Likelihood values: Very Likely, Likely, Possibly, Unlikely
        Severity values: None, Trivial, Minor, Moderate, Major, Fundamental
        """
        try:
            # Create structured assessment for LLM including documentation changes
            assessment_context = {
                "findings": findings,
                "logical_change_sets": logical_change_sets,
                "documentation_changes": documentation_changes
            }
            
            # Get prompts for likelihood and severity assessment
            system_message = prompts.likelihood_severity_assessment_system_prompt()
            human_prompt = prompts.likelihood_severity_assessment_human_prompt(assessment_context)
            
            # Generate assessment using LLM
            response = await self.llm_client.generate_response(
                prompt=human_prompt,
                system_message=system_message,
                task_type="impact_assessment",
                output_format="json",
                temperature=0.1  # Low temperature for consistent assessment
            )
            
            # Parse the response and add likelihood/severity to findings
            if isinstance(response.content, dict) and "assessments" in response.content:
                assessments = response.content["assessments"]
                
                # Match assessments back to findings
                for i, finding in enumerate(findings):
                    if i < len(assessments):
                        assessment = assessments[i]
                        finding["likelihood"] = assessment.get("likelihood", "Possibly")
                        finding["severity"] = assessment.get("severity", "Minor") 
                        finding["reasoning"] = assessment.get("reasoning", "")
            else:
                raise ValueError("Unexpected LLM response format for likelihood/severity assessment")
            
            # Filter findings based on minimum thresholds
            filtered_findings = []
            for finding in findings:
                if self._meets_minimum_criteria(finding):
                    filtered_findings.append(finding)
            
            return filtered_findings
            
        except Exception as e:
            error_msg = f"Step 3: Error in likelihood/severity assessment: {str(e)}"
            self.state.errors.append(error_msg)
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
        likelihood_threshold = likelihood in ["Very Likely", "Likely", "Possibly"]
        severity_threshold = severity in ["Fundamental", "Major", "Moderate", "Minor"]
        
        return likelihood_threshold and severity_threshold
    
    async def _generate_and_post_recommendations(self, state: DocumentUpdateRecommenderState) -> DocumentUpdateRecommenderState:
        """
        Step 4: Generate and Post Recommendations
        
        Implements:
        - Filter High-Priority Findings
        - Query Existing Suggestions
        - Findings Iteration & Suggestion Generation
        - Filter Against Existing & Post Details
        - Manage Check Status
        """
        logger.info("Step 4: Generating and posting documentation recommendations")
        
        try:
            # 4.1 Filter High-Priority Findings
            filtered_findings = await self._filter_high_priority_findings(
                state.prioritized_finding_list
            )
            state.filtered_high_priority_findings = filtered_findings
            
            # 4.2 Query Existing Suggestions
            existing_suggestions = await self._query_existing_suggestions(
                state.repository,
                state.pr_number
            )
            state.existing_suggestions = existing_suggestions
            
            # 4.3 Fetch Current Documentation Context
            current_docs = await self._fetch_current_documentation(
                state.document_content,
                filtered_findings
            )
            
            # 4.4 Findings Iteration & Suggestion Generation
            generated_suggestions = await self._llm_generate_suggestions(
                filtered_findings,
                current_docs,
                state.logical_change_sets
            )
            state.generated_suggestions = generated_suggestions
            
            # 4.5 Filter Against Existing & Post Details
            final_recommendations = await self._llm_filter_and_post_suggestions(
                generated_suggestions,
                existing_suggestions,
                state.repository,
                state.pr_number
            )
            state.recommendations = final_recommendations
            
            # Update processing statistics
            state.processing_stats.update({
                "high_priority_findings": len(filtered_findings),
                "existing_suggestions": len(existing_suggestions),
                "generated_suggestions": len(generated_suggestions),
                "final_recommendations": len(final_recommendations)
            })
            
            logger.info(f"Generated {len(final_recommendations)} final recommendations")
            
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
                            "ref": pr_data.get("head", {}).get("ref", "")
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
                
                logger.info(f"Step 1.1: Successfully fetched PR event data from GitHub REST API for {repository}:{pr_number}")
                return structured_data
                
        except Exception as e:
            raise ValueError(f"Error fetching PR event data: {str(e)}")
    
    async def _fetch_document_content(self, repository: str, branch: str) -> Dict[str, Any]:
        """Fetch documentation content using Repomix"""
        
        logger.info(f"Step 1.2: Fetching documentation content using Repomix for {repository}:{branch}")
        
        # Check if Repomix is available
        try:
            subprocess.run(["repomix", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("Repomix not available, falling back to placeholder content")
            raise ValueError("Repomix not available")
        
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
        
        logger.info(f"Step 1.2: Successfully fetched {len(srs_content)} SRS files and {len(sdd_content)} SDD files")
        
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
                task_type="code_analysis",
                output_format="json",  # Use text so we can parse into Pydantic model
                temperature=0.1  # Low temperature for consistent extraction
            )

            classification_result = response.content
            
            # Convert Pydantic model to our internal format
            commits_with_classifications = []
            for commit_data in classification_result["commits"]:
                commit_dict = {
                    "commit_hash": commit_data["commit_hash"],
                    "commit_message": commit_data["commit_message"],
                    "classifications": []
                }
                
                for classification in commit_data["classifications"]:
                    commit_dict["classifications"].append({
                        "file": classification["file"],
                        "type": classification["type"],
                        "scope": classification["scope"],
                        "nature": classification["nature"],
                        "volume": classification["volume"],
                        "reasoning": classification["reasoning"]
                    })
                
                commits_with_classifications.append(commit_dict)
            
            return commits_with_classifications
            
        except Exception as e:
            err_message = f"Step 2.1: Error in _llm_classify_individual_changes: {str(e)}"
            logger.error(err_message)
            raise
    
    async def _llm_group_classified_changes(self, commits_with_classifications: List[Dict[str, Any]], commit_info: Dict[str, Any]) -> List[Dict[str, Any]]:
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
                task_type="code_analysis",
                output_format="json",  # Use text so we can parse into Pydantic model
                temperature=0.1  # Low temperature for consistent grouping
            )

            # Parse the JSON response into Pydantic model
            grouping_result = response.content
            
            # Convert Pydantic model output to our internal format
            logical_change_sets = []
            for change_set in grouping_result["logical_change_sets"]:
                logical_change_sets.append({
                    "name": change_set["name"],
                    "description": change_set["description"],
                    "changes": change_set["changes"]
                })
            
            return logical_change_sets
                
        except Exception as e:
            err_message = f"Step 2.2: Error in _llm_group_classified_changes: {str(e)}"
            self.state.errors.append(err_message)
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
            likelihood_meets_threshold = likelihood in ["Very Likely", "Likely", "Possibly"]
            severity_meets_threshold = severity in ["Fundamental", "Major", "Moderate", "Minor"]
            
            if likelihood_meets_threshold and severity_meets_threshold:
                filtered_findings.append(finding)
                
        return filtered_findings
    
    async def _query_existing_suggestions(self, repository: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Query existing documentation suggestions for the PR by fetching previous agent comments.
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
                # Get all comments on the PR
                comments_response = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo_name}/issues/{pr_number}/comments",
                    headers=headers
                )
                comments_response.raise_for_status()
                comments_data = comments_response.json()
                
                # Filter for comments made by the bot/agent (GitHub Actions bot)
                bot_comments = []
                for comment in comments_data:
                    # Check if comment is from GitHub Actions bot or contains our agent signature
                    user_login = comment.get("user", {}).get("login", "")
                    comment_body = comment.get("body", "")
                    
                    # Look for our agent's signature or GitHub Actions bot
                    if (user_login == "github-actions[bot]" or 
                        "Docureco Agent" in comment_body or
                        "Documentation Update Recommendation" in comment_body):
                        
                        bot_comments.append({
                            "id": comment.get("id"),
                            "body": comment_body,
                            "created_at": comment.get("created_at"),
                            "updated_at": comment.get("updated_at")
                        })
                        
                return bot_comments
                
        except Exception as e:
            logger.error(f"Error fetching existing suggestions: {str(e)}")
            return []
    
    async def _fetch_current_documentation(self, repo_content: Dict[str, Any], filtered_findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Fetch current documentation context for suggestions.
        Returns relevant SRS and SDD content based on the findings.
        """
        current_docs = {}
        
        try:
            # Extract SRS and SDD content from repo_content
            srs_content = repo_content.get("srs_content", {})
            sdd_content = repo_content.get("sdd_content", {})
            
            # Add all SRS files to current docs
            for file_path, content in srs_content.items():
                current_docs[file_path] = {
                    "document_type": "SRS",
                    "content": content
                }
            
            # Add all SDD files to current docs  
            for file_path, content in sdd_content.items():
                current_docs[file_path] = {
                    "document_type": "SDD", 
                    "content": content
                }
            
            logger.info(f"Fetched current documentation context: {len(srs_content)} SRS files, {len(sdd_content)} SDD files")
            return current_docs
            
        except Exception as e:
            logger.error(f"Error fetching current documentation: {str(e)}")
            return {}
    
    async def _llm_generate_suggestions(self, filtered_findings: List[Dict[str, Any]], current_docs: Dict[str, Any], logical_change_sets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate specific documentation update recommendations using LLM.
        Iterates through each finding and generates actionable recommendations based on finding type.
        """
        all_suggestions = []
        
        try:
            for finding in filtered_findings:
                try:
                    # Determine action based on finding type (per BAB III.md Table III.2)
                    finding_type = finding.get("finding_type", "")
                    if finding_type == "Standard_Impact":
                        action = "Modification" 
                    elif finding_type == "Outdated_Documentation":
                        action = "Review/Delete"
                    elif finding_type == "Documentation_Gap":
                        action = "Create"
                    elif finding_type == "Traceability_Anomaly":
                        action = "Investigate Map"
                    else:
                        action = "Review"
                    
                    # Create comprehensive context for LLM
                    recommendation_context = {
                        "finding": finding,
                        "action": action,
                        "logical_change_sets": logical_change_sets,
                        "current_documentation": current_docs
                    }
                    
                    # Get prompts for recommendation generation
                    system_message = prompts.recommendation_generation_system_prompt()
                    human_prompt = prompts.recommendation_generation_human_prompt(recommendation_context)
                    
                    # Generate recommendation using LLM
                    response = await self.llm_client.generate_response(
                        prompt=human_prompt,
                        system_message=system_message,
                        task_type="recommendation_generation",
                        output_format="json",
                        temperature=0.2  # Slightly higher for more creative recommendations
                    )
                    
                    # Parse the response
                    if isinstance(response.content, dict) and "recommendation" in response.content:
                        suggestion = response.content["recommendation"]
                        suggestion["finding_id"] = finding.get("affected_element_id", "")
                        suggestion["finding_type"] = finding_type
                        suggestion["source_change_set"] = finding.get("source_change_set", "")
                        all_suggestions.append(suggestion)
                    else:
                        logger.warning(f"Unexpected LLM response format for finding {finding.get('affected_element_id', 'unknown')}")
                        
                except Exception as e:
                    logger.error(f"Error generating suggestion for finding {finding.get('affected_element_id', 'unknown')}: {str(e)}")
                    continue
            
            logger.info(f"Generated {len(all_suggestions)} suggestions from {len(filtered_findings)} findings")
            return all_suggestions
            
        except Exception as e:
            logger.error(f"Error in LLM suggestion generation: {str(e)}")
            return []
    
    async def _llm_filter_and_post_suggestions(self, generated_suggestions: List[Dict[str, Any]], existing_suggestions: List[Dict[str, Any]], repository: str, pr_number: int) -> List[DocumentationRecommendationModel]:
        """
        Filter generated suggestions against existing ones and post new recommendations to PR.
        Implements duplication filtering and CI/CD status management per BAB III.md.
        """
        try:
            # Filter out duplicate suggestions by comparing with existing ones
            new_suggestions = []
            existing_bodies = [comment.get("body", "") for comment in existing_suggestions]
            
            for suggestion in generated_suggestions:
                # Create suggestion content for comparison
                suggestion_content = f"""
                **Target Document**: {suggestion.get('target_document', 'Unknown')}
                **Section**: {suggestion.get('section', 'Unknown')}
                **Action**: {suggestion.get('recommendation_type', 'Unknown')}
                **What**: {suggestion.get('what_to_update', '')}
                **Where**: {suggestion.get('where_to_update', '')}
                **Why**: {suggestion.get('why_update_needed', '')}
                **How**: {suggestion.get('how_to_update', '')}
                """
                
                # Simple duplicate check - in production, could use semantic similarity
                is_duplicate = False
                for existing_body in existing_bodies:
                    if (suggestion.get('target_document', '') in existing_body and 
                        suggestion.get('section', '') in existing_body and
                        suggestion.get('what_to_update', '') in existing_body):
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    new_suggestions.append(suggestion)
            
            logger.info(f"Filtered {len(generated_suggestions)} suggestions to {len(new_suggestions)} new suggestions")
            
            # Post new suggestions as PR comments
            posted_recommendations = []
            critical_recommendations = 0
            
            for suggestion in new_suggestions:
                try:
                    # Create formatted comment for the PR
                    comment_body = self._format_recommendation_comment(suggestion)
                    
                    # Post comment to GitHub PR
                    comment_posted = await self._post_pr_comment(repository, pr_number, comment_body)
                    
                    if comment_posted:
                        # Convert to DocumentationRecommendationModel
                        recommendation = self._create_recommendation_model(suggestion)
                        posted_recommendations.append(recommendation)
                        
                        # Count critical recommendations for CI/CD status
                        if suggestion.get('priority', '').upper() in ['HIGH', 'CRITICAL']:
                            critical_recommendations += 1
                    
                except Exception as e:
                    logger.error(f"Error posting suggestion: {str(e)}")
                    continue
            
            # Update CI/CD check status based on recommendations
            await self._update_ci_cd_status(repository, pr_number, critical_recommendations, len(posted_recommendations))
            
            logger.info(f"Posted {len(posted_recommendations)} new recommendations ({critical_recommendations} critical)")
            return posted_recommendations
            
        except Exception as e:
            logger.error(f"Error in filter and post suggestions: {str(e)}")
            return []
    
    def _format_recommendation_comment(self, suggestion: Dict[str, Any]) -> str:
        """Format a recommendation as a GitHub comment with proper markdown formatting."""
        finding_type = suggestion.get('finding_type', 'Unknown')
        priority = suggestion.get('priority', 'Medium')
        
        # Create icon based on priority
        if priority.upper() == 'HIGH':
            icon = "🔴"
        elif priority.upper() == 'MEDIUM': 
            icon = "🟡"
        else:
            icon = "🟢"
        
        comment_body = f"""## {icon} Docureco Agent - Documentation Update Recommendation

**Finding Type**: {finding_type}  
**Priority**: {priority}  
**Target Document**: `{suggestion.get('target_document', 'Unknown')}`  
**Section**: {suggestion.get('section', 'Unknown')}  

### 📝 What needs to be updated
{suggestion.get('what_to_update', 'No description provided')}

### 📍 Where to update
{suggestion.get('where_to_update', 'No location specified')}

### 🔍 Why this update is needed
{suggestion.get('why_update_needed', 'No reason provided')}

### 🛠️ How to update
{suggestion.get('how_to_update', 'No instructions provided')}

---
**Source**: {suggestion.get('source_change_set', 'Unknown change set')}  
**Affected Element**: {suggestion.get('finding_id', 'Unknown')}

*This recommendation was generated automatically by Docureco Agent based on code changes in this PR.*
"""
        return comment_body
    
    async def _post_pr_comment(self, repository: str, pr_number: int, comment_body: str) -> bool:
        """Post a comment to the GitHub PR and return success status."""
        try:
            github_token = os.getenv("GITHUB_TOKEN")
            if not github_token:
                logger.error("GITHUB_TOKEN not found, cannot post comment")
                return False
            
            # Parse repository owner and name
            owner, repo_name = repository.split("/")
            
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json"
            }
            
            # Prepare comment data
            comment_data = {
                "body": comment_body
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"https://api.github.com/repos/{owner}/{repo_name}/issues/{pr_number}/comments",
                    headers=headers,
                    json=comment_data
                )
                
                if response.status_code == 201:
                    logger.info(f"Successfully posted comment to PR #{pr_number}")
                    return True
                else:
                    logger.error(f"Failed to post comment: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error posting PR comment: {str(e)}")
            return False
    
    def _create_recommendation_model(self, suggestion: Dict[str, Any]) -> DocumentationRecommendationModel:
        """Convert suggestion dict to DocumentationRecommendationModel."""
        try:
            # Map recommendation type
            rec_type_str = suggestion.get('recommendation_type', 'UPDATE').upper()
            if rec_type_str in ['CREATE', 'ADD']:
                rec_type = RecommendationType.CREATE
            elif rec_type_str in ['DELETE', 'REMOVE']:
                rec_type = RecommendationType.DELETE
            elif rec_type_str in ['REVIEW', 'INVESTIGATE']:
                rec_type = RecommendationType.REVIEW
            else:
                rec_type = RecommendationType.UPDATE
            
            # Map priority  
            priority_str = suggestion.get('priority', 'MEDIUM').upper()
            if priority_str == 'HIGH':
                priority = RecommendationStatus.HIGH
            elif priority_str == 'LOW':
                priority = RecommendationStatus.LOW
            else:
                priority = RecommendationStatus.MEDIUM
            
            return DocumentationRecommendationModel(
                target_document=suggestion.get('target_document', 'Unknown'),
                section=suggestion.get('section', 'Unknown'),
                recommendation_type=rec_type,
                priority=priority,
                what_to_update=suggestion.get('what_to_update', ''),
                where_to_update=suggestion.get('where_to_update', ''),
                why_update_needed=suggestion.get('why_update_needed', ''),
                how_to_update=suggestion.get('how_to_update', ''),
                affected_element_id=suggestion.get('finding_id', ''),
                affected_element_type=suggestion.get('finding_type', ''),
                confidence_score=suggestion.get('confidence_score', 0.5),
                status=RecommendationStatus.PENDING
            )
            
        except Exception as e:
            logger.error(f"Error creating recommendation model: {str(e)}")
            # Return a default model
            return DocumentationRecommendationModel(
                target_document="Unknown",
                section="Unknown", 
                recommendation_type=RecommendationType.REVIEW,
                priority=RecommendationStatus.MEDIUM,
                what_to_update="Error creating recommendation",
                where_to_update="Unknown",
                why_update_needed="Error occurred",
                how_to_update="Manual review needed",
                affected_element_id="unknown",
                affected_element_type="Unknown",
                confidence_score=0.1,
                status=RecommendationStatus.PENDING
            )
    
    async def _update_ci_cd_status(self, repository: str, pr_number: int, critical_count: int, total_count: int) -> None:
        """Update CI/CD check status based on recommendations."""
        try:
            github_token = os.getenv("GITHUB_TOKEN")
            if not github_token:
                logger.warning("GITHUB_TOKEN not found, cannot update CI/CD status")
                return
            
            # Determine status based on critical recommendations
            if critical_count > 0:
                conclusion = "action_required"
                summary = f"⚠️ {critical_count} critical documentation updates needed"
            elif total_count > 0:
                conclusion = "neutral"
                summary = f"📝 {total_count} documentation recommendations available"
            else:
                conclusion = "success"
                summary = "✅ No documentation updates needed"
            
            logger.info(f"CI/CD Status: {conclusion} - {summary}")
            
            # Note: Actual GitHub Check Run API implementation would go here
            # For now, we just log the intended status
            
        except Exception as e:
            logger.error(f"Error updating CI/CD status: {str(e)}")

def create_document_update_recommender(llm_client: Optional[DocurecoLLMClient] = None) -> DocumentUpdateRecommenderWorkflow:
    """
    Factory function to create Document Update Recommender workflow
    
    Args:
        llm_client: Optional LLM client
        
    Returns:
        DocumentUpdateRecommenderWorkflow: Configured workflow
    """
    return DocumentUpdateRecommenderWorkflow(llm_client)

# Export main classes
__all__ = ["DocumentUpdateRecommenderWorkflow", "DocumentUpdateRecommenderState", "create_document_update_recommender"] 