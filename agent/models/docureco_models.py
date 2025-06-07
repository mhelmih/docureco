"""
Docureco Data Models
Pydantic models for all data structures used in the Docureco Agent workflow
"""

from typing import List, Optional, Dict, Any, Union
from dataclasses import dataclass
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime

# Enums for classification values as defined in Q5 analysis

class ChangeType(str, Enum):
    """Code change types (What dimension)"""
    ADDITION = "Addition"
    DELETION = "Deletion"
    MODIFICATION = "Modification"
    RENAME = "Rename"

class ChangeScope(str, Enum):
    """Code change scope (Where dimension)"""
    FUNCTION_METHOD = "Function/Method"
    CLASS_INTERFACE = "Class/Interface/Struct/Type"
    MODULE_PACKAGE = "Module/Package/Namespace"
    FILE = "File"
    API_CONTRACT = "API Contract"
    CONFIGURATION = "Configuration"
    DEPENDENCIES = "Dependencies"
    BUILD_SCRIPTS = "Build Scripts"
    INFRASTRUCTURE = "Infrastructure Code"
    TEST_CODE = "Test Code"
    DOCUMENTATION = "Documentation"
    CROSS_CUTTING = "Cross-cutting Concerns"

class ChangeNature(str, Enum):
    """Code change nature (Why dimension)"""
    # Functionality changes
    NEW_FEATURE = "New Feature"
    FEATURE_ENHANCEMENT = "Feature Enhancement"
    BUG_FIX = "Bug Fix"
    SECURITY_FIX = "Security Fix"
    
    # Non-functional improvements
    REFACTORING = "Refactoring"
    PERFORMANCE_OPTIMIZATION = "Performance Optimization"
    CODE_STYLE = "Code Style/Formatting"
    TECH_DEBT_REDUCTION = "Technical Debt Reduction"
    READABILITY_IMPROVEMENT = "Readability Improvement"
    ERROR_HANDLING = "Error Handling Improvement"
    
    # Dependencies and build
    DEPENDENCY_MANAGEMENT = "Dependency Management"
    BUILD_IMPROVEMENT = "Build Process Improvement"
    TOOLING_CONFIG = "Tooling Configuration"
    
    # Interface and integration
    API_CHANGE = "API Change"
    EXTERNAL_INTEGRATION = "External System Integration"
    
    # Presentation and content
    DOCUMENTATION_UPDATE = "Documentation Update"
    UI_UX_ADJUSTMENT = "UI/UX Adjustment"
    STATIC_CONTENT = "Static Content Update"
    
    # Maintenance and cleanup
    CODE_DEPRECATION = "Code Deprecation/Removal"
    REVERT = "Revert"
    MERGE_CONFLICT = "Merge Conflict Resolution"
    LICENSE_UPDATE = "License Update"
    
    # Other
    EXPERIMENTAL = "Experimental"
    CHORE = "Chore"
    OTHER = "Other"

class ChangeVolume(str, Enum):
    """Code change volume (How dimension)"""
    TRIVIAL = "Trivial"
    SMALL = "Small"
    MEDIUM = "Medium"
    LARGE = "Large"
    VERY_LARGE = "Very Large"

class TraceabilityStatus(str, Enum):
    """Traceability status for code changes"""
    MODIFICATION = "Modification"
    GAP = "Gap"
    OUTDATED = "Outdated"
    RENAME = "Rename"
    ANOMALY_ADDITION_MAPPED = "Anomaly (addition mapped)"
    ANOMALY_DELETION_UNMAPPED = "Anomaly (deletion unmapped)"
    ANOMALY_MODIFICATION_UNMAPPED = "Anomaly (modification unmapped)"
    ANOMALY_RENAME_UNMAPPED = "Anomaly (rename unmapped)"

class FindingType(str, Enum):
    """Types of impact findings"""
    STANDARD_IMPACT = "Standard_Impact"
    OUTDATED_DOCUMENTATION = "Outdated_Documentation"
    DOCUMENTATION_GAP = "Documentation_Gap"
    TRACEABILITY_ANOMALY = "Traceability_Anomaly"

class Likelihood(str, Enum):
    """Likelihood levels for impact assessment"""
    VERY_LIKELY = "Very Likely"
    LIKELY = "Likely"
    POSSIBLY = "Possibly"
    UNLIKELY = "Unlikely"

class Severity(str, Enum):
    """Severity levels for impact assessment"""
    NONE = "None"
    TRIVIAL = "Trivial"
    MINOR = "Minor"
    MODERATE = "Moderate"
    MAJOR = "Major"
    FUNDAMENTAL = "Fundamental"

class TracePathType(str, Enum):
    """Type of traceability path"""
    DIRECT = "Direct"
    INDIRECT = "Indirect"

# Additional enums for new workflow
class ImpactSeverity(str, Enum):
    """Impact severity levels"""
    LOW = "Low"
    MEDIUM = "Medium" 
    HIGH = "High"

class RecommendationType(str, Enum):
    """Types of documentation recommendations"""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    REVIEW = "REVIEW"

class RecommendationStatus(str, Enum):
    """Status of documentation recommendations"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"

# Main data models

@dataclass
class CodeChangeClassification:
    """
    Classification of a single code change according to 4W framework
    Corresponds to output of Process 2.1 in DFD
    """
    file: str
    type: str  # ChangeType
    scope: str  # ChangeScope
    nature: str  # ChangeNature
    volume: str  # ChangeVolume
    reasoning: str
    commit_hash: str
    patch: str

@dataclass
class LogicalChangeSet:
    """
    Logical grouping of related code changes
    Corresponds to output of Process 2.2 in DFD
    """
    id: str
    description: str
    classifications: List[CodeChangeClassification]
    commit_messages: List[str]

@dataclass
class ImpactFindings:
    """
    Impact finding from traceability analysis
    Corresponds to output of Process 3.x in DFD
    """
    finding_type: str  # FindingType
    affected_element_type: str  # "Requirement", "DesignElement", "CodeComponent"
    affected_element_id: str
    source_change_set_id: str
    trace_path_type: Optional[str] = None  # TracePathType
    likelihood: str = "Possibly"  # Likelihood
    severity: str = "Minor"  # Severity

@dataclass
class DocumentationRecommendation:
    """
    Documentation update recommendation
    Corresponds to output of Process 4.x in DFD
    """
    id: str
    finding_id: str
    recommendation_text: str
    action_type: str  # "create", "modify", "delete", "review"
    priority: str  # Severity
    affected_document: str  # "SRS", "SDD", "Both"
    affected_section: str

# Baseline Map Models (for FR-E requirements)

class RequirementModel(BaseModel):
    """Requirement from SRS"""
    id: str = Field(..., description="Unique requirement identifier")
    title: str = Field(..., description="Requirement title")
    description: str = Field(..., description="Requirement description")
    type: str = Field(..., description="Functional or Non-functional")
    priority: str = Field(default="Medium", description="Requirement priority")
    section: str = Field(..., description="SRS section containing this requirement")

class DesignElementModel(BaseModel):
    """Design element from SDD"""
    id: str = Field(..., description="Unique design element identifier")
    name: str = Field(..., description="Design element name")
    description: str = Field(..., description="Design element description")
    type: str = Field(..., description="Type of design element (class, module, component, etc.)")
    section: str = Field(..., description="SDD section containing this element")

class CodeComponentModel(BaseModel):
    """Code component (file, class, function)"""
    id: str = Field(..., description="Unique code component identifier")
    path: str = Field(..., description="File path or component path")
    type: str = Field(..., description="Type of component (file, class, function)")
    name: Optional[str] = Field(None, description="Component name if applicable")

class TraceabilityLinkModel(BaseModel):
    """Traceability link between artifacts"""
    id: str = Field(..., description="Unique link identifier")
    source_type: str = Field(..., description="Source artifact type")
    source_id: str = Field(..., description="Source artifact ID")
    target_type: str = Field(..., description="Target artifact type")
    target_id: str = Field(..., description="Target artifact ID")
    relationship_type: str = Field(..., description="Type of relationship")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class BaselineMapModel(BaseModel):
    """Complete baseline traceability map"""
    requirements: List[RequirementModel] = Field(default_factory=list)
    design_elements: List[DesignElementModel] = Field(default_factory=list)
    code_components: List[CodeComponentModel] = Field(default_factory=list)
    traceability_links: List[TraceabilityLinkModel] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    repository: str = Field(..., description="Repository this map belongs to")
    branch: str = Field(default="main", description="Branch this map represents")

# GitHub Integration Models

class PREventModel(BaseModel):
    """GitHub Pull Request event model"""
    pr_number: int
    repository: str
    action: str  # opened, synchronize, reopened
    base_ref: str
    head_ref: str
    base_sha: str
    head_sha: str
    title: str
    body: Optional[str] = None
    author: str
    created_at: datetime
    updated_at: datetime

class CommitModel(BaseModel):
    """Git commit model"""
    sha: str
    message: str
    author: str
    timestamp: datetime
    changed_files: List[str] = Field(default_factory=list)

class FileChangeModel(BaseModel):
    """File change in a commit/PR"""
    filename: str
    status: str  # added, modified, removed, renamed
    additions: int = 0
    deletions: int = 0
    patch: Optional[str] = None
    previous_filename: Optional[str] = None  # For renames

# Response Models for API/Output

class ClassificationResponseModel(BaseModel):
    """Response model for code change classification"""
    file: str
    classification: CodeChangeClassification
    timestamp: datetime = Field(default_factory=datetime.now)

class RecommendationResponseModel(BaseModel):
    """Response model for documentation recommendations"""
    pr_number: int
    repository: str
    recommendations: List[DocumentationRecommendation]
    total_findings: int
    high_priority_count: int
    processing_time_seconds: float
    timestamp: datetime = Field(default_factory=datetime.now)

class WorkflowStatusModel(BaseModel):
    """Workflow execution status model"""
    pr_number: int
    repository: str
    status: str  # running, completed, failed
    current_step: str
    progress_percentage: float = 0.0
    errors: List[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

class ImpactAnalysisResultModel(BaseModel):
    """Result of impact analysis for a specific element"""
    element_type: str = Field(..., description="Type of impacted element")
    element_id: str = Field(..., description="ID of impacted element")
    impact_reason: str = Field(..., description="Reason for impact")
    likelihood: float = Field(..., ge=0.0, le=1.0, description="Likelihood score (0-1)")
    severity: ImpactSeverity = Field(..., description="Impact severity")
    change_details: Dict[str, Any] = Field(default_factory=dict, description="Details about the change")

class DocumentationRecommendationModel(BaseModel):
    """Enhanced documentation recommendation model for new workflow"""
    target_document: str = Field(..., description="Target document to update")
    section: str = Field(..., description="Specific section to update")
    recommendation_type: RecommendationType = Field(..., description="Type of recommendation")
    priority: str = Field(..., description="Priority level")
    what_to_update: str = Field(..., description="What needs to be updated")
    where_to_update: str = Field(..., description="Where to make the update")
    why_update_needed: str = Field(..., description="Why update is needed")
    how_to_update: str = Field(..., description="How to perform the update")
    affected_element_id: str = Field(..., description="ID of affected element")
    affected_element_type: str = Field(..., description="Type of affected element")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    status: RecommendationStatus = Field(default=RecommendationStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.now)

# Export all models
__all__ = [
    # Enums
    "ChangeType", "ChangeScope", "ChangeNature", "ChangeVolume",
    "TraceabilityStatus", "FindingType", "Likelihood", "Severity", "TracePathType",
    
    # Core workflow models
    "CodeChangeClassification", "LogicalChangeSet", "ImpactFindings", "DocumentationRecommendation",
    
    # Baseline map models
    "RequirementModel", "DesignElementModel", "CodeComponentModel", 
    "TraceabilityLinkModel", "BaselineMapModel",
    
    # GitHub integration models
    "PREventModel", "CommitModel", "FileChangeModel",
    
    # Response models
    "ClassificationResponseModel", "RecommendationResponseModel", "WorkflowStatusModel",
    
    # New workflow models
    "ImpactAnalysisResultModel", "DocumentationRecommendationModel"
] 