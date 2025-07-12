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
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

# Add parent directories to path for absolute imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, root_dir)

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agent.llm.llm_client import DocurecoLLMClient, create_llm_client
from agent.database import create_baseline_map_repository
from agent.models.docureco_models import (
    BaselineMapModel, DocumentationRecommendationModel, 
    ImpactAnalysisResultModel,
    RecommendationType, ImpactSeverity, RecommendationStatus
)

logger = logging.getLogger(__name__)

@dataclass
class DocumentUpdateRecommenderState:
    """State for the Document Update Recommender workflow"""
    repository: str
    pr_number: int
    branch: str
    
    # Step 1: Scan PR - PR Event Data and Context
    pr_event_data: Dict[str, Any] = field(default_factory=dict)
    requested_repo_content: Dict[str, Any] = field(default_factory=dict)
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
        self.llm_client = llm_client or create_llm_client()
        self.baseline_map_repo = baseline_map_repo or create_baseline_map_repository()
        
        self.workflow = self._build_workflow()
        self.memory = MemorySaver()
        
        logger.info("Initialized DocumentUpdateRecommenderWorkflow")
    
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
        workflow.add_edge("scan_pr", "analyze_code_changes")
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
    
    async def _scan_pr(self, state: DocumentUpdateRecommenderState) -> DocumentUpdateRecommenderState:
        """
        Step 1: Scan PR and Repository Context
        
        Implements:
        - PR Event Data scanning
        - Requested Repository Content retrieval
        - Commit Information gathering
        - Changed Files List compilation
        """
        logger.info(f"Step 1: Scanning PR #{state.pr_number} and repository context")
        
        try:
            # Scan PR event data
            pr_event_data = await self._fetch_pr_event_data(state.repository, state.pr_number)
            state.pr_event_data = pr_event_data
            
            # Get requested repository content
            repo_content = await self._fetch_repo_content(state.repository, state.branch)
            state.requested_repo_content = repo_content
            
            # Extract commit information
            commit_info = pr_event_data.get("commit_info", {})
            state.commit_info = commit_info
            
            # Compile changed files list
            changed_files = pr_event_data.get("files", [])
            state.changed_files_list = [f.get("filename", "") for f in changed_files]
            
            # Update processing statistics
            state.processing_stats.update({
                "pr_files_changed": len(state.changed_files_list),
                "pr_commits": len(commit_info.get("commits", [])),
                "pr_additions": pr_event_data.get("additions", 0),
                "pr_deletions": pr_event_data.get("deletions", 0)
            })
            
            logger.info(f"Scanned PR with {len(state.changed_files_list)} changed files")
            
        except Exception as e:
            error_msg = f"Error scanning PR: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _analyze_code_changes(self, state: DocumentUpdateRecommenderState) -> DocumentUpdateRecommenderState:
        """
        Step 2: Analyze Code Changes
        
        Implements:
        - Code Change Classification (individual changes)
        - Changes Grouping and Contextualization
        - Logical Change Set creation
        """
        logger.info("Step 2: Analyzing and classifying code changes")
        
        try:
            # 2.1 Classify Individual Changes
            classified_changes = await self._llm_classify_individual_changes(
                state.changed_files_list, 
                state.pr_event_data,
                state.requested_repo_content
            )
            state.classified_changes = classified_changes
            
            # 2.2 Group Classified Changes into Logical Change Sets
            logical_change_sets = await self._llm_group_classified_changes(
                classified_changes,
                state.commit_info
            )
            state.logical_change_sets = logical_change_sets
            
            # Update processing statistics
            state.processing_stats.update({
                "classified_changes": len(classified_changes),
                "logical_change_sets": len(logical_change_sets)
            })
            
            logger.info(f"Classified {len(classified_changes)} changes into {len(logical_change_sets)} logical sets")
            
        except Exception as e:
            error_msg = f"Error analyzing code changes: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _assess_documentation_impact(self, state: DocumentUpdateRecommenderState) -> DocumentUpdateRecommenderState:
        """
        Step 3: Assess Documentation Impact
        
        Implements:
        - Determine Traceability Status
        - Impact Tracing through Map
        - Combine Findings
        - Assess Likelihood and Severity
        """
        logger.info("Step 3: Assessing documentation impact using traceability analysis")
        
        try:
            # 3.1 Determine Traceability Status
            baseline_map_data = await self.baseline_map_repo.get_baseline_map(state.repository, state.branch)
            if not baseline_map_data:
                return state    # Terminate workflow if no baseline map is found
                
            traceability_status = await self._determine_traceability_status(
                state.logical_change_sets,
                state.repository,
                state.branch,
                baseline_map_data
            )
            
            # 3.2 Trace Impact Through Map
            # Get changes with traceability status modification, outdated, rename
            changes_modification_outdated_rename = []
            changes_gap_anomaly = []
            for change in state.logical_change_sets:
                status = change.get("traceability_status")
                if status == "modification" or status == "outdated" or status == "rename":
                    changes_modification_outdated_rename.append(change)
                elif status == "gap" or status == "anomaly":
                    changes_gap_anomaly.append(change)
                    
            # Get potentially impacted elements
            potentially_impacted_elements = await self._trace_impact_through_map(
                changes_modification_outdated_rename,
                state.traceability_map
            )
            state.potentially_impacted_elements = potentially_impacted_elements
            
            # 3.3 Combine Findings
            findings = potentially_impacted_elements + changes_gap_anomaly
            
            # 3.4 Assess Likelihood and Severity
            prioritized_findings = await self._llm_assess_likelihood_and_severity(
                findings,
                state.logical_change_sets
            )
            state.prioritized_finding_list = prioritized_findings
            
            # Update processing statistics
            state.processing_stats.update({
                "potentially_impacted_elements": len(potentially_impacted_elements),
                "prioritized_findings": len(prioritized_findings)
            })
            
            logger.info(f"Identified {len(potentially_impacted_elements)} potentially impacted elements")
            
        except Exception as e:
            error_msg = f"Error assessing documentation impact: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
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
                state.requested_repo_content,
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
            error_msg = f"Error generating recommendations: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    # Helper methods (would implement actual GitHub API calls and LLM interactions)
    async def _parse_pr_url(self, pr_url: str) -> Dict[str, Any]:
        """Parse GitHub PR URL to extract repository and PR details"""
        # Placeholder implementation
        return {
            "repository": "example/repo",
            "pr_number": 123,
            "branch": "main"
        }
    
    async def _fetch_pr_event_data(self, repository: str, pr_number: int) -> Dict[str, Any]:
        """Fetch PR event data from GitHub API"""
        # Placeholder implementation
        return {
            "commit_info": {
                "commits": [{"sha": "abc123", "message": "Initial commit"}],
                "additions": 100,
                "deletions": 50
            },
            "files": [
                {"filename": "src/auth/service.py", "status": "modified", "additions": 15, "deletions": 3, "patch": "+def new_auth_method():\n+    pass"}
            ]
        }
    
    async def _fetch_repo_content(self, repository: str, branch: str) -> Dict[str, Any]:
        """Fetch repository content (e.g., for context)"""
        # Placeholder implementation
        return {"repo_name": repository, "branch": branch, "content": {"README.md": "Project Overview", "docs/": "Documentation"}}
    
    async def _llm_classify_individual_changes(self, changed_files: List[str], pr_data: Dict[str, Any], repo_content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Classify individual code changes into logical groups"""
        # Placeholder implementation
        return [{"filename": f, "status": "modified", "additions": 10, "deletions": 5} for f in changed_files]
    
    async def _llm_group_classified_changes(self, classified_changes: List[Dict[str, Any]], commit_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Group classified changes into logical change sets"""
        # Placeholder implementation
        return [{"changes": classified_changes, "commit_sha": commit_info["commits"][0]["sha"]}]
    
    async def _determine_traceability_status(self, logical_change_sets: List[Dict[str, Any]], repository: str, branch: str) -> Dict[str, Any]:
        """Determine if traceability status is available and if it's sufficient"""
        # Placeholder implementation
        return {"traceability_status": "sufficient", "details": "Traceability map available"}
    
    async def _trace_impact_through_map(self, changes_modification_outdated_rename: List[Dict[str, Any]], traceability_map: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Trace impact through the traceability map"""
        # Placeholder implementation
        return [{"element_id": "req1", "element_type": "Requirement", "impact_reason": "Code changes in src/auth/service.py", "likelihood": 0.9, "severity": "High", "change_details": {"file": "src/auth/service.py", "additions": 15, "deletions": 3}}]
    
    async def _llm_assess_likelihood_and_severity(self, combined_findings: List[Dict[str, Any]], logical_change_sets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Assess likelihood and severity for each combined finding"""
        # Placeholder implementation
        return [{"element_id": "req1", "element_type": "Requirement", "impact_reason": "Code changes in src/auth/service.py", "likelihood": 0.9, "severity": "High", "change_details": {"file": "src/auth/service.py", "additions": 15, "deletions": 3}}]
    
    async def _filter_high_priority_findings(self, prioritized_findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter findings to include only high-priority ones"""
        # Placeholder implementation
        return [{"element_id": "req1", "element_type": "Requirement", "impact_reason": "Code changes in src/auth/service.py", "likelihood": 0.9, "severity": "High", "change_details": {"file": "src/auth/service.py", "additions": 15, "deletions": 3}}]
    
    async def _query_existing_suggestions(self, repository: str, pr_number: int) -> List[Dict[str, Any]]:
        """Query existing documentation suggestions for the PR"""
        # Placeholder implementation
        return [{"target_document": "SRS.md", "section": "3.1 Authentication", "type": "UPDATE", "priority": "High", "what": "Update authentication requirements", "where": "Section 3.1.2", "why": "New authentication method added", "how": "Add specification for new auth method"}]
    
    async def _fetch_current_documentation(self, repo_content: Dict[str, Any], filtered_findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fetch current documentation context for suggestions"""
        # Placeholder implementation
        return {"SRS.md": {"content": "Authentication requirements are defined in Section 3.1.2."}}
    
    async def _llm_generate_suggestions(self, filtered_findings: List[Dict[str, Any]], current_docs: Dict[str, Any], logical_change_sets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate specific documentation update recommendations using LLM"""
        # Placeholder implementation
        return [{"target_document": "SRS.md", "section": "3.1 Authentication", "type": "UPDATE", "priority": "High", "what": "Update authentication requirements", "where": "Section 3.1.2", "why": "New authentication method added", "how": "Add specification for new auth method"}]
    
    async def _llm_filter_and_post_suggestions(self, generated_suggestions: List[Dict[str, Any]], existing_suggestions: List[Dict[str, Any]], repository: str, pr_number: int) -> List[DocumentationRecommendationModel]:
        """Filter generated suggestions against existing ones and post details"""
        # Placeholder implementation
        return [DocumentationRecommendationModel(
            target_document="SRS.md",
            section="3.1 Authentication",
            recommendation_type=RecommendationType.UPDATE,
            priority=RecommendationStatus.HIGH,
            what_to_update="Update authentication requirements",
            where_to_update="Section 3.1.2",
            why_update_needed="New authentication method added",
            how_to_update="Add specification for new auth method",
            affected_element_id="req1",
            affected_element_type="Requirement",
            confidence_score=0.9,
            status=RecommendationStatus.PENDING
        )]

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