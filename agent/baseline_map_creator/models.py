from typing import List
from pydantic import BaseModel, Field

class DesignElementOutput(BaseModel):
    """Structured output for design elements"""
    reference_id: str = Field(description="Design element identifier reference from the document (e.g., 'C01', 'UC01', 'M01', etc.)")
    name: str = Field(description="Clear, descriptive name of the design element")
    description: str = Field(description="Brief description of purpose/functionality")
    type: str = Field(description="Category (Service, Class, Interface, Component, Database, UI, etc.)")
    section: str = Field(description="Section reference from the document")

class TraceabilityMatrixEntry(BaseModel):
    """Structured output for traceability matrix entries"""
    source_id: str = Field(description="ID of the source artifact (e.g., 'REQ-001', 'DE-001', etc.)")
    target_id: str = Field(description="ID of the target artifact (e.g., 'DE-002', 'UC01', etc.)")
    relationship_type: str = Field(default="unclassified", description="Relationship type (will be classified later)")
    source_file: str = Field(description="File path where this relationship was found")

class DesignElementsWithMatrixOutput(BaseModel):
    """Structured output for design elements and traceability matrix extraction"""
    design_elements: List[DesignElementOutput] = Field(description="List of design elements found")
    traceability_matrix: List[TraceabilityMatrixEntry] = Field(description="List of traceability relationships found")

class RequirementOutput(BaseModel):
    """Structured output for requirements"""
    reference_id: str = Field(description="Requirement identifier reference from the document (e.g., 'REQ-001', 'UC01', 'M01', etc.)")
    title: str = Field(description="Clear, concise title of the requirement")
    description: str = Field(description="Detailed description of what is required")
    type: str = Field(description="Category (Functional, Non-Functional, Business, User, System, etc.)")
    priority: str = Field(description="Importance level (High, Medium, Low)")
    section: str = Field(description="Section reference from the document")

class RequirementsWithDesignElementsOutput(BaseModel):
    """Structured output for requirements and design elements extraction"""
    requirements: List[RequirementOutput] = Field(description="List of requirements found")
    design_elements: List[DesignElementOutput] = Field(description="List of design elements found")

class RelationshipOutput(BaseModel):
    """Structured output for relationships"""
    source_id: str = Field(description="ID of the source element")
    target_id: str = Field(description="ID of the target element")
    relationship_type: str = Field(description="Type of relationship")

class RelationshipListOutput(BaseModel):
    """A list of relationship outputs."""
    relationships: List[RelationshipOutput] = Field(description="A list of identified relationships between elements.")


__all__ = [
    "DesignElementOutput", 
    "TraceabilityMatrixEntry", 
    "DesignElementsWithMatrixOutput", 
    "RequirementOutput", 
    "RequirementsWithDesignElementsOutput", 
    "RelationshipOutput",
    "RelationshipListOutput"
] 