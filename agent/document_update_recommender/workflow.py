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
    type: str = Field(description="Type of change (Addition, Deletion, Modification, Renaming)")
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
    changes: List[CodeChangeClassification] = Field(description="Array of files with classifications that belong to this logical change set")

class ChangeGroupingOutput(BaseModel):
    """Structured output for grouping changes into logical change sets"""
    logical_change_sets: List[LogicalChangeSet] = Field(description="List of logical change sets")

class DocumentationRecommendation(BaseModel):
    """Structured output for documentation recommendations"""
    section: str = Field(description="Specific section or location")
    recommendation_type: str = Field(description="Type of update (UPDATE, CREATE, DELETE, REVIEW)")
    priority: str = Field(description="Priority level (HIGH, MEDIUM, LOW)")
    what_to_update: str = Field(description="What needs to be changed")
    why_update_needed: str = Field(description="Rationale based on code changes")
    suggested_content: str = Field(default="", description="Specific content suggestions")

class DocumentSummary(BaseModel):
    """Summary for a target document"""
    target_document: str = Field(description="Document that needs updating")
    total_recommendations: int = Field(description="Total number of recommendations for this document")
    high_priority_count: int = Field(description="Number of high priority recommendations")
    medium_priority_count: int = Field(description="Number of medium priority recommendations")
    low_priority_count: int = Field(description="Number of low priority recommendations")
    overview: str = Field(description="Brief overview of what needs updating in this document")
    sections_affected: List[str] = Field(description="List of sections that need updates")
    traceability_anomaly_affected_files: List[str] = Field(default_factory=list, description="List of files affected by traceability anomalies")
    how_to_fix_traceability_anomaly: str = Field(default="", description="Instructions for how to fix traceability anomalies")

class DocumentRecommendationGroup(BaseModel):
    """Group of recommendations for a specific document"""
    summary: DocumentSummary = Field(description="Summary of recommendations for this document")
    recommendations: List[DocumentationRecommendation] = Field(description="List of detailed recommendations for this document")

class RecommendationGenerationOutput(BaseModel):
    """Structured output for recommendation generation grouped by target document"""
    document_groups: List[DocumentRecommendationGroup] = Field(description="Recommendations grouped by target document")

class AssessedFinding(BaseModel):
    """Finding with likelihood and severity assessment"""
    finding_type: str = Field(description="Type of finding")
    affected_element_id: str = Field(description="ID of affected element")
    affected_element_name: str = Field(description="Name of affected element")
    affected_element_description: str = Field(description="Description of affected element")
    affected_element_type: str = Field(description="Type of affected element (DesignElement or Requirement) along with the type of the element (Class, Function, etc.)") 
    source_change_set: str = Field(description="Source change set name")
    trace_path_type: Optional[str] = Field(description="Type of trace path", default=None)
    anomaly_type: Optional[str] = Field(description="Type of anomaly if applicable", default=None)
    likelihood: str = Field(description="Likelihood assessment (Very Likely, Likely, Possibly, Unlikely)")
    severity: str = Field(description="Severity assessment (Fundamental, Major, Moderate, Minor, Trivial, None)")
    reasoning: str = Field(description="Reasoning for the assessment")

class LikelihoodSeverityAssessmentOutput(BaseModel):
    """Structured output for likelihood and severity assessment"""
    assessed_findings: List[AssessedFinding] = Field(description="List of findings with likelihood and severity assessments")

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
                 baseline_map_repo = None,
                 use_review_mode: bool = True,
                 review_threshold: int = 2,
                 primary_baseline_branch: str = "main"):
        """
        Initialize Document Update Recommender workflow
        
        Args:
            llm_client: Optional LLM client for analysis and recommendations
            baseline_map_repo: Optional repository for baseline map operations
            use_review_mode: Whether to use GitHub Review API for comprehensive reviews
            review_threshold: Minimum number of suggestions to trigger review mode (default: 2)
            primary_baseline_branch: Primary branch to look for baseline maps (default: "main")
        """
        self.llm_client = llm_client or DocurecoLLMClient()
        self.baseline_map_repo = baseline_map_repo or create_baseline_map_repository()
        self.use_review_mode = use_review_mode
        self.review_threshold = review_threshold
        self.primary_baseline_branch = primary_baseline_branch
        
        self.workflow = self._build_workflow()
        self.memory = MemorySaver()
        
        logger.info("Initialized Document Update Recommender Workflow")
        logger.info(f"Review mode: {'enabled' if use_review_mode else 'disabled'}")
        logger.info(f"Review threshold: {review_threshold} suggestions")
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
                        
        # Build lookup dictionaries for design elements and requirements
        design_elements_by_id = {de.id: de for de in getattr(baseline_map_data, "design_elements", [])}
        requirements_by_id = {req.id: req for req in getattr(baseline_map_data, "requirements", [])}
        
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
                    if file_path in path_to_component_id:
                        component_id = path_to_component_id[file_path]
                        if component_id in code_to_design_map:
                            design_element_ids = code_to_design_map[component_id]
                            
                            if status in ["modification", "anomaly (addition mapped)", "rename"]:
                                dide.update(design_element_ids)
                            elif status == "outdated":
                                ode.update(design_element_ids)
                
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
            
            for design_element_id in dide:
                if design_element_id in design_to_design_map:
                    related_element_ids = design_to_design_map[design_element_id]
                    iide.update(related_element_ids)
            
            # Combine to form Potentially Impacted Design Elements (PIDE) for this change set
            pide = dide.union(iide)
            
            # Trace to Requirements for this change set
            pir = set()  # Potentially Impacted Requirements for this change set
            or_set = set()  # Outdated Requirements for this change set
            
            # Trace PIDE to requirements
            for design_element_id in pide:
                if design_element_id in design_to_requirement_map:
                    requirement_ids = design_to_requirement_map[design_element_id]
                    pir.update(requirement_ids)
            
            # Trace ODE to requirements  
            for design_element_id in ode:
                if design_element_id in design_to_requirement_map:
                    requirement_ids = design_to_requirement_map[design_element_id]
                    or_set.update(requirement_ids)
            
            # Form Finding Records for this change set
            # Standard Impact findings for PIDE and PIR
            for design_element_id in pide:
                finding = {
                    "finding_type": "Standard_Impact",
                    "affected_element_id": design_element_id,
                    "affected_element_name": design_elements_by_id[design_element_id].name,
                    "affected_element_description": design_elements_by_id[design_element_id].description,
                    "affected_element_type": "DesignElement - " + design_elements_by_id[design_element_id].type,
                    "trace_path_type": "Direct" if design_element_id in dide else "Indirect",
                    "source_change_set": change_set_name
                }
                change_set_findings.append(finding)
            
            for requirement_id in pir:
                finding = {
                    "finding_type": "Standard_Impact",
                    "affected_element_id": requirement_id, 
                    "affected_element_name": requirements_by_id[requirement_id].title,
                    "affected_element_description": requirements_by_id[requirement_id].description,
                    "affected_element_type": "Requirement - " + requirements_by_id[requirement_id].type,
                    "trace_path_type": "Direct",
                    "source_change_set": change_set_name
                }
                change_set_findings.append(finding)
            
            # Outdated Documentation findings for ODE and OR
            for design_element_id in ode:
                finding = {
                    "finding_type": "Outdated_Documentation",
                    "affected_element_id": design_element_id,
                    "affected_element_name": design_elements_by_id[design_element_id].name,
                    "affected_element_description": design_elements_by_id[design_element_id].description,
                    "affected_element_type": "DesignElement - " + design_elements_by_id[design_element_id].type,
                    "trace_path_type": None,
                    "source_change_set": change_set_name
                }
                change_set_findings.append(finding)
            
            for requirement_id in or_set:
                finding = {
                    "finding_type": "Outdated_Documentation", 
                    "affected_element_id": requirement_id,
                    "affected_element_name": requirements_by_id[requirement_id].title,
                    "affected_element_description": requirements_by_id[requirement_id].description,
                    "affected_element_type": "Requirement - " + requirements_by_id[requirement_id].type,
                    "trace_path_type": None,
                    "source_change_set": change_set_name
                }
                change_set_findings.append(finding)
            
            # Add all findings from this change set to the overall findings
            all_findings.extend(change_set_findings)
        
        return all_findings

    async def _llm_assess_likelihood_and_severity(self, findings: List[Dict[str, Any]], logical_change_sets: List[Dict[str, Any]], documentation_changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
            assessed_findings = response.content["assessed_findings"]
            
            # Convert Pydantic models back to dictionaries and filter
            filtered_findings = []
            for assessed_finding in assessed_findings:
                # Convert to dict format
                finding_dict = {
                    "finding_type": assessed_finding["finding_type"],
                    "affected_element_id": assessed_finding["affected_element_id"],
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
                
                # Apply filtering based on minimum criteria
                if self._meets_minimum_criteria(finding_dict):
                    filtered_findings.append(finding_dict)
            
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
            logger.info("Step 4.1: Filtering high-priority findings")
            filtered_findings = await self._filter_high_priority_findings(
                state.prioritized_finding_list
            )
            state.filtered_high_priority_findings = filtered_findings
            
            # 4.2 Query Existing Suggestions
            logger.info("Step 4.2: Fetching existing suggestions")
            existing_suggestions = await self._query_existing_suggestions(
                state.repository,
                state.pr_number
            )
            state.existing_suggestions = existing_suggestions
            
            # 4.3 Use Current Documentation Context from state
            logger.info("Step 4.3: Using current documentation context from state")
            current_docs = {}
            
            # Extract SRS and SDD content from state.document_content
            srs_content = state.document_content.get("srs_content", {})
            sdd_content = state.document_content.get("sdd_content", {})
            
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
            
            # 4.4 Findings Iteration & Suggestion Generation
            logger.info("Step 4.4: Generating suggestions")
            generated_suggestions = await self._llm_generate_suggestions(
                filtered_findings,
                current_docs,
                state.logical_change_sets
            )
            state.generated_suggestions = generated_suggestions
            
            # 4.5 Filter Against Existing & Post Details
            logger.info("Step 4.5: Filtering and posting suggestions")
            final_recommendations = await self._llm_filter_and_post_suggestions(
                generated_suggestions,
                existing_suggestions,
                state.repository,
                state.pr_number,
                state.baseline_map
            )
            
            state.recommendations = final_recommendations
            
            # Update processing statistics
            state.processing_stats.update({
                "high_priority_findings": len(filtered_findings),
                "existing_suggestions": len(existing_suggestions),
                "generated_suggestions": len(generated_suggestions),
                "final_recommendations": len(final_recommendations)
            })
            
            logger.info(f"Step 4: Successfully generated {len(final_recommendations)} final recommendations")
            
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
    

    
    async def _llm_generate_suggestions(self, filtered_findings: List[Dict[str, Any]], current_docs: Dict[str, Any], logical_change_sets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate specific documentation update recommendations using LLM.
        Processes all findings at once for efficient batch recommendation generation.
        """
        try:
            if not filtered_findings:
                return []
            
            # Add action type to each finding based on finding type (per BAB III.md Table III.2)
            findings_with_actions = []
            for finding in filtered_findings:
                finding_with_action = finding.copy()
                finding_type = finding.get("finding_type", "")
                
                if finding_type == "Standard_Impact":
                    finding_with_action["recommended_action"] = "Modification" 
                elif finding_type == "Outdated_Documentation":
                    finding_with_action["recommended_action"] = "Review/Delete"
                elif finding_type == "Documentation_Gap":
                    finding_with_action["recommended_action"] = "Create"
                elif finding_type == "Traceability_Anomaly":
                    finding_with_action["recommended_action"] = "Investigate Map"
                else:
                    finding_with_action["recommended_action"] = "Review"
                
                findings_with_actions.append(finding_with_action)
            
            # Create output parser for structured response
            output_parser = JsonOutputParser(pydantic_object=RecommendationGenerationOutput)
            
            # Get prompts for recommendation generation
            system_message = prompts.recommendation_generation_system_prompt()
            human_prompt = prompts.recommendation_generation_human_prompt(
                findings_with_actions, current_docs, logical_change_sets
            )
            
            # Generate recommendations using LLM with structured output
            response = await self.llm_client.generate_response(
                prompt=human_prompt,
                system_message=system_message + "\n" + output_parser.get_format_instructions(),
                output_format="json",
                temperature=0.2  # Slightly higher for more creative recommendations
            )
            
            # Parse the structured response
            recommendation_result = response.content
            document_groups = recommendation_result["document_groups"]
            
            logger.info(f"Generated recommendations for {len(document_groups)} document groups from {len(filtered_findings)} findings")
            return document_groups
            
        except Exception as e:
            logger.error(f"Error in LLM suggestion generation: {str(e)}")
            return []
    
    async def _llm_filter_and_post_suggestions(self, generated_suggestions: List[Dict[str, Any]], existing_suggestions: List[Dict[str, Any]], repository: str, pr_number: int, baseline_map: Optional[BaselineMapModel]) -> List[DocumentationRecommendationModel]:
        """
        Filter generated suggestions against existing ones and post new recommendations to PR.
        Implements duplication filtering and CI/CD status management per BAB III.md.
        """
        try:
            # # Extract flat list of recommendations from document groups
            # all_recommendations = []
            # for group in generated_suggestions:
            #     all_recommendations.extend(group.get('recommendations', []))
            
            # # Filter out duplicate suggestions by comparing with existing ones
            # new_suggestions = []
            # existing_bodies = [comment.get("body", "") for comment in existing_suggestions]
            
            # for suggestion in all_recommendations:                
            #     # Simple duplicate check - in production, could use semantic similarity
            #     is_duplicate = False
            #     for existing_body in existing_bodies:
            #         if (suggestion.get('section', '') in existing_body and
            #             suggestion.get('what_to_update', '') in existing_body):
            #             is_duplicate = True
            #             break
                
            #     if not is_duplicate:
            #         new_suggestions.append(suggestion)
            
            # Post new suggestions
            posted_recommendations = []
            critical_recommendations = 0
            
            # Use GitHub Review API for suggestions (Copilot-style)
            logger.info(f"Creating comprehensive PR review for {len(generated_suggestions)} suggestions")
            review_posted = await self._create_pr_review_with_suggestions(repository, pr_number, generated_suggestions, baseline_map)
            
            if review_posted:
                # Extract individual recommendations from document groups
                for document_group in generated_suggestions:
                    target_document = document_group.get('summary', {}).get('target_document', 'Unknown')
                    recommendations = document_group.get('recommendations', [])
                    
                    for suggestion in recommendations:
                        recommendation = self._create_recommendation_model(suggestion, target_document)
                        posted_recommendations.append(recommendation)
                        
                        if suggestion.get('priority', '').upper() in ['HIGH', 'CRITICAL']:
                            critical_recommendations += 1
            
            # Update CI/CD check status based on recommendations
            await self._update_ci_cd_status(repository, pr_number, critical_recommendations, len(posted_recommendations))
            
            logger.info(f"Posted {len(posted_recommendations)} new recommendations ({critical_recommendations} critical)")
            return posted_recommendations
            
        except Exception as e:
            logger.error(f"Error in filter and post suggestions: {str(e)}")
            return []
    
    def _create_recommendation_model(self, suggestion: Dict[str, Any], target_document: str = "Unknown") -> DocumentationRecommendationModel:
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
            
            # Map priority (priority is a string field, not an enum)
            priority_str = suggestion.get('priority', 'MEDIUM').upper()
            # Normalize priority values
            if priority_str in ['HIGH', 'CRITICAL']:
                priority = 'HIGH'
            elif priority_str in ['LOW', 'MINOR']:
                priority = 'LOW'
            else:
                priority = 'MEDIUM'
            
            # Generate where_to_update and how_to_update based on the suggestion
            section = suggestion.get('section', 'Unknown')
            where_to_update = f"{target_document} - {section}" if target_document != "Unknown" else section
            how_to_update = suggestion.get('suggested_content', suggestion.get('what_to_update', 'Manual review needed'))
            
            return DocumentationRecommendationModel(
                target_document=target_document,
                section=section,
                recommendation_type=rec_type,
                priority=priority,
                what_to_update=suggestion.get('what_to_update', ''),
                where_to_update=where_to_update,
                why_update_needed=suggestion.get('why_update_needed', ''),
                how_to_update=how_to_update,
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
                priority="MEDIUM",  # String value, not enum
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
            
            if not recommendations:
                # Handle traceability anomaly case
                affected_files = summary.get('traceability_anomaly_affected_files', [])
                how_to_fix = summary.get('how_to_fix_traceability_anomaly', '')
                
                if affected_files:
                    group_text = f"""
# 🤖 Docureco Agent - 🔴 Traceability Anomaly Detected

**📁 Affected Files**: {', '.join([f'`{file}`' for file in affected_files])}

**💭 Issue**: {summary.get('overview', 'Traceability anomaly detected')}

**🛠️ How to Fix**: {how_to_fix}

---"""
                    group_details.append(group_text)
                continue
            
            # Regular document recommendations
            target_document = summary.get('target_document', 'Unknown')
            group_text = f"""
# 🤖 Docureco Agent - 📄 `{target_document}` Recommendations ({len(recommendations)} total)

{summary.get('overview', 'No overview provided')} Affected sections: `{', '.join(summary.get('sections_affected', []))}`.

---
"""
            
            # Add individual recommendations
            for recommendation in recommendations:
                priority_icon = "🔴" if recommendation.get('priority', '').upper() == 'HIGH' else "🟡" if recommendation.get('priority', '').upper() == 'MEDIUM' else "🟢"
                
                # Use the documentation content generated by the main LLM call
                suggested_content = recommendation.get('suggested_content', 'No content provided')
                
                section = recommendation.get('section', 'Unknown')
                action = recommendation.get('recommendation_type', 'Unknown').upper()
                
                # Create the suggestion with copy-paste ready content
                suggestion_text = f"""
### {priority_icon} Suggestion #{suggestion_counter}: {action} in {section}

[{recommendation.get('priority', 'Medium')}] {recommendation.get('what_to_update', 'No description provided')}. {recommendation.get('why_update_needed', 'No reason provided')}.

**📝 Suggested Change**:
```diff
{suggested_content}
```

> 💡 **How to apply**: Add lines with `+`, remove lines with `-`, keep context lines unchanged
---"""
                
                group_text += suggestion_text
                suggestion_counter += 1
            
            group_details.append(group_text)
        
        suggestions_text = "".join(group_details)
        
        # Add traceability map for context
        traceability_map_section = self._format_baseline_map_for_comment(baseline_map)
        
        return f"""
{suggestions_text}

### 📊 Summary:
- **Total Suggestions**: {total_suggestions}
- **High Priority**: {high_priority}
- **Medium/Low Priority**: {total_suggestions - high_priority}

{traceability_map_section}

---
*This review was generated automatically by Docureco Agent based on code changes in this PR*"""

    def _format_baseline_map_for_comment(self, baseline_map: Optional[BaselineMapModel]) -> str:
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
<details>
<summary>📋 Current Traceability Map</summary>

{requirements_section}{design_elements_section}{code_components_section}{traceability_links_section}

**Total Elements**: {req_count} requirements, {de_count} design elements, {cc_count} code components, {tl_count} traceability links

</details>
"""

def create_document_update_recommender(
    llm_client: Optional[DocurecoLLMClient] = None,
    use_review_mode: bool = True,
    review_threshold: int = 2,
    primary_baseline_branch: str = "main"
) -> DocumentUpdateRecommenderWorkflow:
    """
    Factory function to create Document Update Recommender workflow
    
    Args:
        llm_client: Optional LLM client
        use_review_mode: Whether to use GitHub Review API for comprehensive reviews  
        review_threshold: Minimum number of suggestions to trigger review mode
        primary_baseline_branch: Primary branch to look for baseline maps (default: "main")
        
    Returns:
        DocumentUpdateRecommenderWorkflow: Configured workflow
    """
    return DocumentUpdateRecommenderWorkflow(
        llm_client=llm_client,
        use_review_mode=use_review_mode, 
        review_threshold=review_threshold,
        primary_baseline_branch=primary_baseline_branch
    )

# Export main classes
__all__ = ["DocumentUpdateRecommenderWorkflow", "DocumentUpdateRecommenderState", "create_document_update_recommender"] 