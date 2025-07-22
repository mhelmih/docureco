"""
Docureco Data Models
Pydantic models for all data structures used in the Docureco Agent workflow
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class RequirementModel(BaseModel):
    """Requirement model for SRS elements"""
    id: str = Field(..., description="Unique requirement identifier")
    reference_id: Optional[str] = Field(default=None, description="Requirement identifier reference from the document (e.g., 'REQ-001', 'UC01', 'M01', etc.)")
    title: str = Field(..., description="Requirement title")
    description: str = Field(..., description="Detailed requirement description")
    type: str = Field(..., description="Requirement type (Functional/Non-functional)")
    priority: str = Field(default="Medium", description="Priority level")
    section: str = Field(..., description="Source document section")

class DesignElementModel(BaseModel):
    """Design element model for SDD components"""
    id: str = Field(..., description="Unique design element identifier")
    reference_id: Optional[str] = Field(default=None, description="Design element identifier reference from the document (e.g., 'C01', 'UC01', 'M01', etc.)")
    name: str = Field(..., description="Design element name")
    description: str = Field(..., description="Design element description")
    type: str = Field(..., description="Design element type")
    section: str = Field(..., description="Source document section")

class CodeComponentModel(BaseModel):
    """Code component model for source code elements"""
    id: str = Field(..., description="Unique code component identifier")
    path: str = Field(..., description="File path or component path")
    type: str = Field(..., description="Component type")
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

__all__ = [
    "RequirementModel", "DesignElementModel", "CodeComponentModel", 
    "TraceabilityLinkModel", "BaselineMapModel",
] 