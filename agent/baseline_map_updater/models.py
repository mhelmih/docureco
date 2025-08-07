from typing import List, Dict, Any, Union
from pydantic import BaseModel, Field

class AddedElement(BaseModel):
    """Represents any element (Requirement or Design Element) that has been added."""
    reference_id: str = Field(description="The unique identifier of the newly added element.")
    element_type: str = Field(description="The type of the element: 'Requirement' or 'DesignElement'.")
    details: Dict[str, Any] = Field(description="The full details of the newly added element.")

class ModifiedElement(BaseModel):
    """Represents any element that has been modified."""
    reference_id: str = Field(description="The unique identifier of the element that was modified.")
    element_type: str = Field(description="The type of the element: 'Requirement' or 'DesignElement'.")
    changes: Dict[str, Union[Any, Dict[str, Any]]] = Field(description="A dictionary detailing the changes, which can include 'from'/'to' structures.")

class DeletedElement(BaseModel):
    """Represents any element that has been deleted."""
    reference_id: str = Field(description="The unique identifier of the element that was deleted.")
    element_type: str = Field(description="The type of the element: 'Requirement' or 'DesignElement'.")

class UnifiedChangesOutput(BaseModel):
    """Structured output for all identified changes to any type of element."""
    added: List[AddedElement] = Field(default_factory=list)
    modified: List[ModifiedElement] = Field(default_factory=list)
    deleted: List[DeletedElement] = Field(default_factory=list)

class DetectedUnifiedChange(BaseModel):
    """Represents a single, unverified change of any type detected in the first pass."""
    reference_id: str = Field(description="The identifier of the element.")
    element_type: str = Field(description="The detected type of the element: 'Requirement' or 'DesignElement'.")
    full_element_data: Dict[str, Any] = Field(description="All extracted data for the element (name, description, etc.).")
    detected_change_type: str = Field(description="The type of change detected ('addition', 'modification', or 'deletion').")

class RawUnifiedChangeDetectionOutput(BaseModel):
    """The output of the first-pass raw change detection for any element type."""
    detected_changes: List[DetectedUnifiedChange] = Field(description="A flat list of all detected, unverified changes.")

class FoundLink(BaseModel):
    """Represents a single traceability link found by the LLM."""
    target_id: str = Field(description="The `reference_id` of the element that the source element traces to.")
    target_type: str = Field(description="The type of the target element, e.g., 'Requirement' or 'DesignElement'.")
    relationship_type: str = Field(description="The type of relationship, like 'realizes' or 'implements'.")

class LinkFindingOutput(BaseModel):
    """Structured output for the link finding process for a single source element."""
    links: List[FoundLink] = Field(description="A list of traceability links found for the source element.")

class BatchLinkFindingOutput(BaseModel):
    """Structured output for finding links for multiple source elements at once."""
    links_by_source: Dict[str, List[FoundLink]] = Field(
        description="A dictionary where keys are the `reference_id` of the source elements, and values are the lists of links found for each source."
    )


__all__ = [
    "AddedElement",
    "ModifiedElement",
    "DeletedElement",
    "UnifiedChangesOutput",
    "DetectedUnifiedChange",
    "RawUnifiedChangeDetectionOutput",
    "FoundLink",
    "LinkFindingOutput",
    "BatchLinkFindingOutput"
] 