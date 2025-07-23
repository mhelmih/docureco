from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

from agent.models.docureco_models import BaselineMapModel

class CodeChangeClassification(BaseModel):
    """Structured output for individual code change classification"""
    file: str = Field(description="Path to the changed file")
    type: str = Field(description="Type of change (Addition, Deletion, Modification, Renaming)")
    scope: str = Field(description="Scope of change (Function/Method, Class, Module, etc.)")
    nature: str = Field(description="Nature of change (New Feature, Bug Fix, Refactoring, etc.)")
    volume: str = Field(description="Volume of change (Trivial, Small, Medium, Large, Very Large)")
    reasoning: str = Field(description="Brief explanation of the classification")
    patch: Optional[str] = Field(default=None, description="Patch of the change")

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

class FilteredSuggestionsOutput(BaseModel):
    """Structured output for the suggestion filtering process."""
    new_suggestions: List[DocumentRecommendationGroup] = Field(description="A list of new, non-duplicate document groups with recommendations.")

class AssessedFinding(BaseModel):
    """Finding with likelihood and severity assessment"""
    finding_type: str = Field(description="Type of finding")
    affected_element_id: str = Field(description="ID of affected element")
    affected_element_reference_id: str = Field(description="Reference ID of affected element")
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
    recommendations: List[Dict[str, Any]] = field(default_factory=list)
    
    # Workflow metadata
    errors: List[str] = field(default_factory=list)
    processing_stats: Dict[str, int] = field(default_factory=dict) 


__all__ = ["CodeChangeClassification", "CommitWithClassifications", "BatchClassificationOutput", "LogicalChangeSet", "ChangeGroupingOutput", "DocumentationRecommendation", "DocumentSummary", "DocumentRecommendationGroup", "RecommendationGenerationOutput", "AssessedFinding", "LikelihoodSeverityAssessmentOutput", "DocumentUpdateRecommenderState"] 