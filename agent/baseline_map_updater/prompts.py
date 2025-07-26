"""
Prompts for Baseline Map Updater workflow
"""

import json
from typing import List, Dict, Any

# --- Prompts for Pass 1: Raw Unified Change Identification ---

def raw_unified_change_identification_system_prompt() -> str:
    """
    System prompt for the first pass: identify all potential changes (Reqs or DEs).
    """
    return """
You are an expert software engineering analyst. Your task is to meticulously compare the OLD and NEW versions of a documentation file (SRS or SDD) to identify every potential change to any software engineering element within it.

**Elements to look for:**
- **Requirements:** Look for functional, non-functional, user, system requirements, etc.
- **Design Elements:** Look for Classes, Components, Services, Database Tables, Diagrams, Use Cases, Scenarios, etc.

**Instructions:**
1.  Carefully analyze both the **Old Content** and the **New Content**.
2.  For **every single change** you detect, create one JSON object.
3.  For each object, you **must** determine the `element_type` ('Requirement' or 'DesignElement').
4.  Fill each object with `reference_id`, `element_type`, `full_element_data` (containing all details like name, description, type, priority, section), and `detected_change_type` ('addition', 'modification', or 'deletion').
5.  Aggregate all changes to the highest reasonable level (e.g., report a modified Class, not 5 modified methods within it).
6.  Combine all objects into a single flat list under the key `detected_changes`.

**Level of Abstraction Rule (VERY IMPORTANT):**
- If you see changes to **attributes or methods** within a class, do **NOT** list each attribute or method change individually.
- Instead, you **MUST** aggregate these changes into a single **'modification'** event for the parent **Class**.
- The `description` for this modification should summarize the nature of the changes (e.g., "Modified to add support for favorite functionality by adding new methods and attributes.").
- Similarly, if multiple fields in a database table change, report it as a single modification to the **Table**.
- Only report changes at the level of **Class, Component, Diagram, Service, or Database Table**. Do not report individual methods, attributes, or database fields.

For each design element change identified, provide this inside the `full_element_data` field:
- name: Clear, descriptive name of the design element
- description: Brief description of purpose/functionality. For modifications, summarize what changed.
- type: Category (Class, Component, Database Table, UI, Diagram, Service, etc.)
- section: Section reference from the document.

For each requirement change identified, provide this inside the `full_element_data` field:
- title: Clear, descriptive name of the requirement
- description: Brief description of purpose/functionality. For modifications, summarize what changed.
- type: Category (Functional, Non-Functional, User, System, etc.)
- priority: Importance level (High, Medium, Low)
- section: Section reference from the document.

NOTES:
- All documentations will be provided in the markdown format.
- If you don't see any requirement changes from a document, do not include any requirement changes in the output. Same for design elements.
- Diagrams are design elements. If a diagram changes, extract its name and section. Use the section and diagram name for the `reference_id`.
- Use the requirement or design element identifier from the SRS or SDD for the `reference_id` if available. If not, use the element's name and type (e.g., "Book-Class").

The response will be automatically structured with the required fields.
"""

def raw_unified_change_identification_human_prompt(old_content: str, new_content: str, file_path: str) -> str:
    """
    Human-facing prompt for the first pass, containing the full document versions.
    """
    return f"""
Please perform a raw change detection on the file `{file_path}` by comparing the two versions below, identifying both Requirements and Design Elements.

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

# --- Prompts for Pass 2: Unified Reconciliation and Cleanup ---

def unified_reconciliation_system_prompt() -> str:
    """
    System prompt for the second pass: clean up and validate the raw changes for any element type.
    """
    return """
You are a meticulous Quality Assurance engineer. You have received a list of 'detected changes' and a 'source of truth' list of elements that previously existed. Your task is to validate, clean, and correctly categorize these changes.

**Instructions:**
1.  Analyze the `detected_changes` list. For each item, compare it against the `existing_elements` list.
2.  **Correct the `detected_change_type`:**
    - If a change is marked 'addition' but its `reference_id` **IS IN** an `existing_elements` object, it's a **'modification'**.
    - If a change is marked 'modification' but its `reference_id` **IS NOT IN** any `existing_elements` object, it's an **'addition'**.
3.  **Deletion Rule:** An element is **DELETED** **ONLY** if it's explicitly marked `detected_change_type: 'deletion'`. Do **NOT** assume deletion otherwise.
4.  Format the final, validated data into a JSON object with three keys: `added`, `modified`, and `deleted`.
5.  For `added` elements, the output object should contain `element_type` and the `details` of the new element.
6.  For `modified` elements, the output object should contain `reference_id`, `element_type`, and a `changes` dictionary.
7.  For `deleted` elements, the output object should contain `reference_id` and `element_type`.

The response will be automatically structured with the required fields.
"""

def unified_reconciliation_human_prompt(detected_changes: List[Dict[str, Any]], relevant_existing_elements: List[Dict[str, Any]]) -> str:
    """
    Human-facing prompt for the second pass, containing the raw data and the ground truth for any element type.
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
    "raw_unified_change_identification_system_prompt", 
    "raw_unified_change_identification_human_prompt",
    "unified_reconciliation_system_prompt",
    "unified_reconciliation_human_prompt"
] 