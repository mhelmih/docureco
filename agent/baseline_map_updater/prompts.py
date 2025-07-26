"""
Prompts for Baseline Map Updater workflow
"""

import json
from typing import List, Dict, Any

def raw_change_identification_system_prompt() -> str:
    """
    System prompt for the first pass: identify all potential changes in a flat list.
    """
    return """
You are an expert software engineering analyst. Your task is to meticulously compare the OLD and NEW versions of a software design document (SDD) to identify every potential change to a design element.

**Instructions:**
1.  Carefully analyze both the **Old Content** and the **New Content**.
2.  For **every single change** you detect (addition, modification, or deletion), create one JSON object.
3.  Fill each object with `reference_id`, `name`, `description`, `type`, `section`, and a `detected_change_type` ('addition', 'modification', or 'deletion').
4.  Your goal is to capture all potential changes. Do not worry about perfect accuracy yet.
5.  Combine all the JSON objects you create into a single flat list under the key `detected_changes`.

For each design element change identified, provide:
- reference_id: Design element identifier reference from the document (e.g., 'C01', 'UC01', 'M01', etc.)
- name: Clear, descriptive name of the design element
- description: Brief description of purpose/functionality
- type: Category (Use Case, Scenario, Class, Interface, Component, Database Table, UI, Diagram, Service, Query, Algorithm, Process, Procedure, Module, etc.)
- section: Section reference from the document. Please choose more specific section name (full with number, name, and/or title. Not just number or title). For example, if the section is "4.1.1 Class: Book", the section should be "4.1.1 Class: Book".
- detected_change_type: The type of change detected ('addition', 'modification', or 'deletion').

NOTES:
- The SDD will be provided in the markdown format. 
- Images in markdown format would look like this:
```
![Diagram Name](image_path.png)
```
- Please be aware of the diagram images in the SDD because all images in the SDD are already described textually in the SDD. Diagrams are also design elements that needs to be updated when the code changes. Diagrams often placed in a section without a caption or title. If there are changes to the diagram, extract the diagram with the section and diagram name as the reference_id. For example, if the diagram is in the section "5.2 Use Case Realization" and the diagram name is "UC01 Sequence Diagram", the reference_id should be "5.2 Use Case Realization - UC01 Sequence Diagram".
- Use the design element identifier used in the SDD for reference_id field if available. If the design element identifier is not available, use the design element name and the type as the reference_id (for example, there is a class "Book" without ID but it is in the section "4.1.1 Class: Book" then the reference_id should be "Book-Class").

The response will be automatically structured with the required fields.
"""

def raw_change_identification_human_prompt(old_content: str, new_content: str, file_path: str) -> str:
    """
    Human-facing prompt for the first pass, containing the full document versions.
    """
    return f"""
Please perform a raw change detection on the file `{file_path}` by comparing the two versions below.

---
**Old Content:**
```markdown
{old_content if old_content else "This document did not exist before."}
```
---
**New Content (Final Version):**
```markdown
{new_content if new_content else "This document has been deleted."}
```
---

Generate the JSON object containing the flat list of all detected changes.
"""

# --- Prompts for Pass 2: Reconciliation and Cleanup ---

def reconciliation_system_prompt() -> str:
    """
    System prompt for the second pass: clean up and validate the raw changes.
    """
    return """
You are a meticulous Quality Assurance engineer. You have received a list of 'detected changes' from a junior analyst and a 'source of truth' list of elements that previously existed. Your task is to validate, clean, and correctly categorize the detected changes.

**Instructions:**
1.  Analyze the `detected_changes` list provided by the user.
2.  Compare each item against the `existing_elements` list, which is the source of truth.
3.  **Crucially, correct the `detected_change_type`:**
    - If a change is marked 'addition' but its `reference_id` **IS IN** the `existing_elements` list, it is actually a **'modification'**.
    - If a change is marked 'modification' but its `reference_id` **IS NOT IN** the `existing_elements` list, it is actually an **'addition'**.
4.  Format the final, validated data into a JSON object with three distinct keys: `added`, `modified`, and `deleted`.
5.  For `modified` elements, the output should contain the `reference_id` and a `changes` dictionary detailing only the fields that were altered.
6.  For `added` elements, include all their details.
7.  For `deleted` elements, include only their `reference_id`.

The response will be automatically structured with the required fields.
"""

def reconciliation_human_prompt(detected_changes: List[Dict[str, Any]], relevant_existing_elements: List[Dict[str, Any]]) -> str:
    """
    Human-facing prompt for the second pass, containing the raw data and the ground truth.
    """
    detected_str = json.dumps(detected_changes, indent=2)
    existing_str = json.dumps(relevant_existing_elements, indent=2)

    return f"""
Please validate and categorize the following detected changes.

---
**Detected Changes:**
```json
{detected_str}
```
---
**Existing Elements (Source of Truth):**
```json
{existing_str}
```
---

Generate the final, clean JSON object with `added`, `modified`, and `deleted` lists.
"""

__all__ = [
    "raw_change_identification_system_prompt", 
    "raw_change_identification_human_prompt",
    "reconciliation_system_prompt",
    "reconciliation_human_prompt"
] 