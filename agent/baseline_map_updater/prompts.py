"""
Prompts for Baseline Map Updater workflow
"""

from typing import List, Dict, Any

def get_analysis_prompt_for_changes(
    element_type: str, # "Design Element" or "Requirement"
    old_content: str,
    new_content: str,
    file_path: str
) -> str:
    """
    Creates a prompt to analyze changes between old and new document content
    to identify added, modified, and deleted elements.
    """
    prompt = f"""
You are an expert software engineering documentation analyst. Your task is to compare two versions of a documentation file and identify the changes to its structured elements.

You need to identify what has been ADDED, MODIFIED, and DELETED.

File Path: {file_path}
Element Type to Analyze: {element_type}

**Old Content:**
```markdown
{old_content}
```

**New Content:**
```markdown
{new_content}
```

**Instructions:**
1.  Compare the "New Content" with the "Old Content".
2.  Identify all {element_type}s that were added, modified, or deleted.
3.  For ADDED elements, provide their full details.
4.  For MODIFIED elements, provide their identifier and the fields that have changed.
5.  For DELETED elements, provide only their identifier.
6.  Structure your response as a single JSON object with three keys: "added", "modified", and "deleted". Each key should contain a list of the corresponding elements.

**Example JSON Output Format:**
```json
{{
  "added": [
    {{
      "reference_id": "DE-005",
      "name": "New Authentication Service",
      "description": "Handles user login and session management.",
      "type": "Service",
      "section": "3.1.5"
    }}
  ],
  "modified": [
    {{
      "reference_id": "DE-002",
      "changes": {{
        "description": "Updated to include multi-factor authentication.",
        "name": "User Authentication Service"
      }}
    }}
  ],
  "deleted": [
    {{
      "reference_id": "DE-003"
    }}
  ]
}}
```

Provide only the JSON object in your response.
"""
    return prompt

__all__ = ["get_analysis_prompt_for_changes"] 