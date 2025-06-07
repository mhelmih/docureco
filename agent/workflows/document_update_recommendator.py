"""
Document Update Recommendator Workflow for Docureco Agent
Main LangGraph workflow that analyzes GitHub PR code changes and recommends documentation updates
Implements the Document Update Recommendator component from the system architecture
"""

import asyncio
import logging
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..llm.llm_client import DocurecoLLMClient, create_llm_client
from ..database import create_baseline_map_repository, create_vector_search_repository
from ..models.docureco_models import (
    BaselineMapModel, DocumentationRecommendationModel, 
    ImpactAnalysisResultModel, RequirementModel, DesignElementModel,
    RecommendationType, ImpactSeverity, RecommendationStatus
)

logger = logging.getLogger(__name__)

@dataclass
class DocumentUpdateRecommendatorState:
    """State for the Document Update Recommendator workflow"""
    repository: str
    pr_number: int
    branch: str
    
    # PR Analysis Data
    baseline_map: Optional[BaselineMapModel] = None
    code_changes: List[Dict[str, Any]] = field(default_factory=list)
    
    # Impact Analysis Results  
    impacted_elements: List[ImpactAnalysisResultModel] = field(default_factory=list)
    
    # Generated Recommendations
    recommendations: List[DocumentationRecommendationModel] = field(default_factory=list)
    
    # Workflow metadata
    pr_summary: str = ""
    errors: List[str] = field(default_factory=list)
    processing_stats: Dict[str, int] = field(default_factory=dict)

class DocumentUpdateRecommendatorWorkflow:
    """
    Main LangGraph workflow for analyzing GitHub PR code changes and recommending documentation updates.
    
    This workflow implements the Document Update Recommendator component which is responsible for:
    1. Loading baseline traceability maps
    2. Analyzing code changes from GitHub PRs  
    3. Identifying impacted documentation elements using semantic search
    4. Generating specific documentation update recommendations
    5. Providing actionable insights using the 4W framework (What, Where, Why, How)
    
    Research Questions Addressed: Q1-Q10 from BAB III
    """
    
    def __init__(self, 
                 llm_client: Optional[DocurecoLLMClient] = None,
                 baseline_map_repo = None,
                 vector_search_repo = None):
        """
        Initialize Document Update Recommendator workflow
        
        Args:
            llm_client: Optional LLM client for analysis and recommendations
            baseline_map_repo: Optional repository for baseline map operations
            vector_search_repo: Optional repository for vector similarity search
        """
        self.llm_client = llm_client or create_llm_client()
        self.baseline_map_repo = baseline_map_repo or create_baseline_map_repository()
        self.vector_search_repo = vector_search_repo or create_vector_search_repository()
        
        self.workflow = self._build_workflow()
        self.memory = MemorySaver()
        
        logger.info("Initialized DocumentUpdateRecommendatorWorkflow")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow with conditional logic"""
        workflow = StateGraph(DocumentUpdateRecommendatorState)
        
        # Add nodes for each major process step
        workflow.add_node("load_baseline_map", self._load_baseline_map)
        workflow.add_node("analyze_code_changes", self._analyze_code_changes)
        workflow.add_node("identify_impacted_elements", self._identify_impacted_elements)
        workflow.add_node("analyze_semantic_impact", self._analyze_semantic_impact)
        workflow.add_node("generate_recommendations", self._generate_recommendations)
        workflow.add_node("create_pr_summary", self._create_pr_summary)
        
        # Define workflow edges with conditional logic
        workflow.set_entry_point("load_baseline_map")
        workflow.add_edge("load_baseline_map", "analyze_code_changes")
        workflow.add_edge("analyze_code_changes", "identify_impacted_elements")
        workflow.add_edge("identify_impacted_elements", "analyze_semantic_impact")
        workflow.add_edge("analyze_semantic_impact", "generate_recommendations")
        workflow.add_edge("generate_recommendations", "create_pr_summary")
        workflow.add_edge("create_pr_summary", END)
        
        return workflow
    
    async def execute(self, pr_url: str) -> DocumentUpdateRecommendatorState:
        """
        Execute the Document Update Recommendator workflow for PR analysis
        
        Args:
            pr_url: GitHub PR URL to analyze
            
        Returns:
            DocumentUpdateRecommendatorState: Final state with recommendations
        """
        # Initialize state with PR information
        pr_info = await self._parse_pr_url(pr_url)
        initial_state = DocumentUpdateRecommendatorState(
            repository=pr_info["repository"],
            pr_number=pr_info["pr_number"],
            branch=pr_info["branch"],
            baseline_map=None,
            code_changes=[],
            impacted_elements=[],
            recommendations=[],
            pr_summary="",
            errors=[],
            processing_stats={}
        )
        
        try:
            # Compile and run workflow
            app = self.workflow.compile(checkpointer=self.memory)
            config = {"configurable": {"thread_id": f"pr_{pr_info['repository'].replace('/', '_')}_{pr_info['pr_number']}"}}
            
            final_state = await app.ainvoke(initial_state, config=config)
            
            logger.info(f"Document Update Recommendator completed for PR {pr_info['repository']}#{pr_info['pr_number']}")
            return final_state
            
        except Exception as e:
            logger.error(f"Document Update Recommendator failed: {str(e)}")
            initial_state.errors.append(str(e))
            raise
    
    async def _load_baseline_map(self, state: DocumentUpdateRecommendatorState) -> DocumentUpdateRecommendatorState:
        """
        Load baseline traceability map for the repository
        Implements Q1: How to retrieve existing traceability relationships?
        """
        logger.info(f"Loading baseline map for {state.repository}:{state.branch}")
        
        try:
            # Load baseline map from database
            baseline_map_data = await self.baseline_map_repo.get_baseline_map(state.repository, state.branch)
            
            if baseline_map_data:
                state.baseline_map = BaselineMapModel(**baseline_map_data)
                logger.info(f"Loaded baseline map with {len(state.baseline_map.requirements)} requirements, "
                           f"{len(state.baseline_map.design_elements)} design elements, "
                           f"{len(state.baseline_map.code_components)} code components")
                
                # Update statistics
                state.processing_stats.update({
                    "baseline_requirements": len(state.baseline_map.requirements),
                    "baseline_design_elements": len(state.baseline_map.design_elements),
                    "baseline_code_components": len(state.baseline_map.code_components),
                    "baseline_traceability_links": len(state.baseline_map.traceability_links)
                })
            else:
                logger.warning(f"No baseline map found for {state.repository}:{state.branch}")
                state.errors.append("No baseline traceability map available - recommendations will be limited")
                
        except Exception as e:
            error_msg = f"Error loading baseline map: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _analyze_code_changes(self, state: DocumentUpdateRecommendatorState) -> DocumentUpdateRecommendatorState:
        """
        Analyze code changes from the GitHub PR
        Implements Q2: How to extract and categorize code changes?
        """
        logger.info(f"Analyzing code changes for PR #{state.pr_number}")
        
        try:
            # Fetch PR details from GitHub API (placeholder implementation)
            pr_data = await self._fetch_pr_data(state.repository, state.pr_number)
            
            if pr_data:
                state.code_changes = pr_data.get("files", [])
                
                # Analyze change characteristics
                change_stats = {
                    "files_modified": len([f for f in state.code_changes if f.get("status") == "modified"]),
                    "files_added": len([f for f in state.code_changes if f.get("status") == "added"]), 
                    "files_deleted": len([f for f in state.code_changes if f.get("status") == "removed"]),
                    "total_additions": sum(f.get("additions", 0) for f in state.code_changes),
                    "total_deletions": sum(f.get("deletions", 0) for f in state.code_changes)
                }
                
                state.processing_stats.update(change_stats)
                logger.info(f"Analyzed {len(state.code_changes)} changed files: {change_stats}")
            else:
                error_msg = f"Could not fetch PR data for {state.repository}#{state.pr_number}"
                logger.error(error_msg)
                state.errors.append(error_msg)
                
        except Exception as e:
            error_msg = f"Error analyzing code changes: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _identify_impacted_elements(self, state: DocumentUpdateRecommendatorState) -> DocumentUpdateRecommendatorState:
        """
        Identify documentation elements impacted by code changes using traceability links
        Implements Q3: How to determine which documentation elements are affected?
        """
        logger.info("Identifying impacted documentation elements using traceability analysis")
        
        try:
            impacted_elements = []
            
            if state.baseline_map and state.code_changes:
                # Direct traceability analysis
                for change in state.code_changes:
                    file_path = change.get("filename", "")
                    
                    # Find code components that match the changed file
                    matching_components = [
                        comp for comp in state.baseline_map.code_components 
                        if comp.path == file_path or file_path.endswith(comp.path)
                    ]
                    
                    for component in matching_components:
                        # Find traceability links from this code component
                        related_links = [
                            link for link in state.baseline_map.traceability_links
                            if (link.source_type == "CodeComponent" and link.source_id == component.id) or
                               (link.target_type == "CodeComponent" and link.target_id == component.id)
                        ]
                        
                        # Determine impact severity based on change size
                        severity = self._calculate_impact_severity(change)
                        
                        # Create impact analysis results
                        for link in related_links:
                            impact = ImpactAnalysisResultModel(
                                element_type=link.source_type if link.target_id == component.id else link.target_type,
                                element_id=link.source_id if link.target_id == component.id else link.target_id,
                                impact_reason=f"Code changes in {file_path}",
                                likelihood=0.8,  # High likelihood for direct traceability
                                severity=severity,
                                change_details={
                                    "file": file_path,
                                    "additions": change.get("additions", 0),
                                    "deletions": change.get("deletions", 0),
                                    "status": change.get("status", "modified")
                                }
                            )
                            impacted_elements.append(impact)
            
            state.impacted_elements = impacted_elements
            state.processing_stats["impacted_elements_count"] = len(impacted_elements)
            logger.info(f"Identified {len(impacted_elements)} potentially impacted elements via traceability")
            
        except Exception as e:
            error_msg = f"Error identifying impacted elements: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _analyze_semantic_impact(self, state: DocumentUpdateRecommendatorState) -> DocumentUpdateRecommendatorState:
        """
        Analyze semantic impact using vector similarity search for broader coverage
        Implements Q4: How to detect indirect documentation impacts using semantic analysis?
        """
        logger.info("Performing semantic impact analysis using vector similarity")
        
        try:
            semantic_impacts = []
            
            if state.code_changes:
                # Use vector search to find semantically related elements
                for change in state.code_changes:
                    filename = change.get("filename", "")
                    patch = change.get("patch", "")
                    
                    if filename and patch:
                        # Find related elements using semantic similarity
                        related_elements = await self.vector_search_repo.find_related_elements_by_code_change(
                            filename=filename,
                            patch=patch,
                            commit_message=change.get("commit_message", ""),
                            repository=state.repository,
                            branch=state.branch,
                            similarity_threshold=0.6,  # Configurable threshold
                            max_results_per_type=5
                        )
                        
                        # Create impact analysis results for semantic matches
                        for req_data in related_elements.get("requirements", []):
                            impact = ImpactAnalysisResultModel(
                                element_type="Requirement",
                                element_id=req_data.get("id"),
                                impact_reason=f"Semantic similarity to changes in {filename}",
                                likelihood=req_data.get("similarity", 0.6),
                                severity=ImpactSeverity.MEDIUM,
                                change_details={
                                    "file": filename,
                                    "similarity_score": req_data.get("similarity"),
                                    "semantic_match": True
                                }
                            )
                            semantic_impacts.append(impact)
                        
                        for de_data in related_elements.get("design_elements", []):
                            impact = ImpactAnalysisResultModel(
                                element_type="DesignElement", 
                                element_id=de_data.get("id"),
                                impact_reason=f"Semantic similarity to changes in {filename}",
                                likelihood=de_data.get("similarity", 0.6),
                                severity=ImpactSeverity.MEDIUM,
                                change_details={
                                    "file": filename,
                                    "similarity_score": de_data.get("similarity"),
                                    "semantic_match": True
                                }
                            )
                            semantic_impacts.append(impact)
            
            # Merge with existing impacts (avoid duplicates)
            existing_ids = {(impact.element_type, impact.element_id) for impact in state.impacted_elements}
            for semantic_impact in semantic_impacts:
                if (semantic_impact.element_type, semantic_impact.element_id) not in existing_ids:
                    state.impacted_elements.append(semantic_impact)
            
            semantic_count = len(semantic_impacts)
            state.processing_stats["semantic_impacts_count"] = semantic_count
            logger.info(f"Found {semantic_count} additional semantic impacts")
            
        except Exception as e:
            error_msg = f"Error in semantic impact analysis: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _generate_recommendations(self, state: DocumentUpdateRecommendatorState) -> DocumentUpdateRecommendatorState:
        """
        Generate specific documentation update recommendations using LLM
        Implements Q5-Q10: How to generate actionable recommendations with 4W framework?
        """
        logger.info("Generating documentation update recommendations")
        
        try:
            recommendations = []
            
            if state.impacted_elements:
                # Group impacts by element type for better organization
                grouped_impacts = {}
                for impact in state.impacted_elements:
                    element_type = impact.element_type
                    if element_type not in grouped_impacts:
                        grouped_impacts[element_type] = []
                    grouped_impacts[element_type].append(impact)
                
                # Generate recommendations for each impacted element
                for element_type, impacts in grouped_impacts.items():
                    for impact in impacts:
                        # Use LLM to generate detailed recommendations
                        recommendation_data = await self._llm_generate_recommendation(
                            impact, state.baseline_map, state.code_changes
                        )
                        
                        if recommendation_data:
                            recommendation = DocumentationRecommendationModel(
                                target_document=recommendation_data.get("target_document"),
                                section=recommendation_data.get("section"),
                                recommendation_type=RecommendationType(recommendation_data.get("type", "UPDATE")),
                                priority=recommendation_data.get("priority", "Medium"),
                                what_to_update=recommendation_data.get("what"),
                                where_to_update=recommendation_data.get("where"), 
                                why_update_needed=recommendation_data.get("why"),
                                how_to_update=recommendation_data.get("how"),
                                affected_element_id=impact.element_id,
                                affected_element_type=impact.element_type,
                                confidence_score=impact.likelihood,
                                status=RecommendationStatus.PENDING
                            )
                            recommendations.append(recommendation)
            
            # If no specific impacts found, generate general recommendations
            if not recommendations and state.code_changes:
                general_recommendations = await self._llm_generate_general_recommendations(state.code_changes)
                recommendations.extend(general_recommendations)
            
            state.recommendations = recommendations
            state.processing_stats["recommendations_count"] = len(recommendations)
            logger.info(f"Generated {len(recommendations)} documentation recommendations")
            
        except Exception as e:
            error_msg = f"Error generating recommendations: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _create_pr_summary(self, state: DocumentUpdateRecommendatorState) -> DocumentUpdateRecommendatorState:
        """
        Create a comprehensive PR summary with recommendations
        """
        logger.info("Creating PR analysis summary")
        
        try:
            # Use LLM to create a comprehensive summary
            summary_data = await self._llm_create_pr_summary(
                state.code_changes, state.impacted_elements, state.recommendations
            )
            
            state.pr_summary = summary_data.get("summary", "Analysis completed")
            logger.info("PR summary created successfully")
            
        except Exception as e:
            error_msg = f"Error creating PR summary: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
            # Create a basic summary as fallback
            state.pr_summary = f"Analyzed {len(state.code_changes)} file changes and generated {len(state.recommendations)} recommendations"
        
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
    
    async def _fetch_pr_data(self, repository: str, pr_number: int) -> Optional[Dict[str, Any]]:
        """Fetch PR data from GitHub API"""
        # Placeholder implementation
        return {
            "files": [
                {
                    "filename": "src/auth/service.py",
                    "status": "modified", 
                    "additions": 15,
                    "deletions": 3,
                    "patch": "+def new_auth_method():\n+    pass"
                }
            ]
        }
    
    def _calculate_impact_severity(self, change: Dict[str, Any]) -> ImpactSeverity:
        """Calculate impact severity based on change characteristics"""
        additions = change.get("additions", 0)
        deletions = change.get("deletions", 0)
        total_changes = additions + deletions
        
        if total_changes > 50:
            return ImpactSeverity.HIGH
        elif total_changes > 10:
            return ImpactSeverity.MEDIUM
        else:
            return ImpactSeverity.LOW
    
    async def _llm_generate_recommendation(self, impact: ImpactAnalysisResultModel, 
                                         baseline_map: BaselineMapModel,
                                         code_changes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Generate recommendation using LLM"""
        # Placeholder implementation
        return {
            "target_document": "SRS.md",
            "section": "3.1 Authentication",
            "type": "UPDATE",
            "priority": "High",
            "what": "Update authentication requirements",
            "where": "Section 3.1.2",
            "why": "New authentication method added",
            "how": "Add specification for new auth method"
        }
    
    async def _llm_generate_general_recommendations(self, code_changes: List[Dict[str, Any]]) -> List[DocumentationRecommendationModel]:
        """Generate general recommendations when no specific impacts found"""
        # Placeholder implementation
        return []
    
    async def _llm_create_pr_summary(self, code_changes: List[Dict[str, Any]],
                                   impacted_elements: List[ImpactAnalysisResultModel],
                                   recommendations: List[DocumentationRecommendationModel]) -> Dict[str, Any]:
        """Create PR summary using LLM"""
        # Placeholder implementation
        return {
            "summary": f"Analyzed {len(code_changes)} changes, identified {len(impacted_elements)} impacts, generated {len(recommendations)} recommendations"
        }

def create_document_update_recommendator(llm_client: Optional[DocurecoLLMClient] = None) -> DocumentUpdateRecommendatorWorkflow:
    """
    Factory function to create Document Update Recommendator workflow
    
    Args:
        llm_client: Optional LLM client
        
    Returns:
        DocumentUpdateRecommendatorWorkflow: Configured workflow
    """
    return DocumentUpdateRecommendatorWorkflow(llm_client)

# Export main classes
__all__ = ["DocumentUpdateRecommendatorWorkflow", "DocumentUpdateRecommendatorState", "create_document_update_recommendator"] 