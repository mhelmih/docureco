"""
Prompts for Baseline Map Updater workflow
"""

import json
from typing import List, Dict, Any

def design_element_analysis_system_prompt() -> str:
    """
    Creates the system prompt for the design element change analysis task.
    This prompt instructs the LLM on its role, the task, and the output format.
    """
    return """
You are a meticulous software engineering analyst specializing in documentation version control. Your task is to analyze a new version of a software design document (SDD) alongside a "diff" that highlights the changes from the old version.

Based on this information, you must identify every design element that was **ADDED**, **MODIFIED**, or **DELETED**.

**Instructions:**
1.  Review the **New Content** to understand the final state of the document.
2.  Use the **Unified Diff** as a guide to understand what was changed. Lines starting with `+` are additions, and lines starting with `-` are deletions.
3.  Identify all design elements that were added, modified, or deleted based on your analysis. Pay close attention to changes in descriptions, names, or any other attributes.
4.  For **ADDED** elements, provide their full details: `reference_id`, `name`, `description`, `type`, and `section`.
5.  For **MODIFIED** elements, provide their `reference_id` and a `changes` dictionary. The keys of the dictionary should be the field names that changed (e.g., "name", "description"), and the values should be the new content for those fields.
6.  For **DELETED** elements, provide only their `reference_id`.
7.  Ensure your response is a single, valid JSON object with three keys: `added`, `modified`, and `deleted`. Each key must hold a list of the corresponding elements, even if the list is empty.

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

def design_element_analysis_human_prompt(
    new_content: str,
    diff_text: str,
    file_path: str,
    relevant_existing_elements: List[Dict[str, Any]]
) -> str:
    """
    Creates the human-facing prompt containing the data for the LLM to analyze.
    """
    # Format the list of existing elements for clear presentation in the prompt
    if relevant_existing_elements:
        existing_elements_str = json.dumps(relevant_existing_elements, indent=2)
    else:
        existing_elements_str = "None (this appears to be a new document or had no mapped elements)."

    return f"""
Please analyze the following documentation changes for the file `{file_path}`.

**Context:**
Here is a JSON array of all design elements that **previously existed in this specific document**. Use this as your primary reference.
- An element is **MODIFIED** if its `reference_id` is in this list, but its other attributes (like name or description) have changed in the "New Content".
- An element is **ADDED** if it appears in the "New Content" but its `reference_id` is **NOT** in this list.
- An element is **DELETED** if its `reference_id` is in this list but it no longer appears in the "New Content".

**Existing Elements in `{file_path}`:**
```json
{existing_elements_str}
```

---
**New Content (Final Version):**
```markdown
{new_content if new_content else "This document has been deleted."}
```
---
**Unified Diff (Summary of Changes):**
```diff
{diff_text if diff_text else "No changes detected or file is new."}
```
---

Based on the instructions provided in the system prompt and the detailed context above, generate the JSON object describing the changes.
"""

__all__ = ["design_element_analysis_system_prompt", "design_element_analysis_human_prompt"] 