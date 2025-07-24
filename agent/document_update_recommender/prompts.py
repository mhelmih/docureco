"""
Prompts for Document Update Recommender workflow
"""

from typing import Dict, Any, List
import json


class DocumentUpdateRecommenderPrompts:
    """Collection of prompts for document update recommender workflow"""
    
    @staticmethod
    def get_docureco_system_context() -> str:
        """Comprehensive context about the Docureco system and workflows"""
        return """
**DOCURECO SYSTEM OVERVIEW**
Docureco is an intelligent documentation maintenance system that automatically tracks relationships between code and documentation, then recommends updates when code changes. The system consists of three core workflows:
1. BASELINE MAP CREATOR WORKFLOW
- **Purpose**: Creates initial traceability maps from existing repositories
- **Input**: Repository with documentation (SRS, SDD) and code files
- **Process**: 
  - Scans repository documentation and code
  - Extracts Requirements (from SRS files)
  - Extracts Design Elements (from SDD files) 
  - Extracts Code Components (from source code)
  - Creates Traceability Links between Requirements ↔ Design Elements ↔ Code Components
- **Output**: Baseline Map containing all elements and their relationships
- **When Used**: Initial setup for a repository

2. DOCUMENT UPDATE RECOMMENDER WORKFLOW (Your Current Role)
- **Purpose**: Analyzes PR code changes and recommends documentation updates
- **Input**: PR with code changes + existing Baseline Map
- **Process**:
  - Scans PR code changes and documentation context
  - Classifies and groups changes into logical change sets
  - Traces impact through the baseline map to find affected documentation elements
  - Assesses likelihood and severity of documentation impact
  - Generates specific update recommendations with targeted diff snippets
- **Output**: Documentation update recommendations with targeted change snippets
- **When Used**: When developers submit PRs with code changes

3. BASELINE MAP UPDATER WORKFLOW
- **Purpose**: Updates baseline maps when repository structure changes
- **Input**: Merged PR with code changes + existing Baseline Map
- **Process**:
  - Analyzes PR code changes and documentation context
  - Identifies new/modified requirements, design elements, and code components
  - Updates traceability links to reflect new relationships
- **Output**: Updated Baseline Map
- **When Used**: When PR is merged and code changes are detected

**BASELINE MAP CONCEPT**
A Baseline Map is a comprehensive traceability matrix that captures:
1. **Requirements** (from SRS documents):
   - Business requirements, functional requirements, non-functional requirements
   - Each has: id (auto-generated, unique, primary key), reference_id (referenced from the document), title, description, type, priority, section reference
2. **Design Elements** (from SDD documents):
   - Architecture components, classes, interfaces, services, databases, UI elements
   - Each has: id (auto-generated, unique, primary key), reference_id (referenced from the document), name, description, type, section reference
3. **Code Components** (from source code):
   - Files, classes, functions, modules, APIs
   - Each has: id (auto-generated, unique, primary key), path, name, type, description
4. **Traceability Links** (relationships between elements):
   - Requirements → Design Elements (what implements each requirement)
   - Design Elements → Code Components (what code implements each design)
   - Design Elements → Design Elements (dependencies and relationships)

**Example Baseline Map Structure:**
```
Requirements: REQ-001 "User can add books" 
Design Elements: DE-001 "BookService class"
Code Components: CC-001 "src/book/book_collection.py"
Traceability Links:
  - REQ-001 -> DE-001 (realizes)
  - DE-001 -> CC-001 (implements)
```

**DOCURECO SYSTEM USAGE PROCESS**
- **Baseline Map Creator Workflow**: Use this workflow to (re)create the baseline map when starting a new project or there are traceability anomalies. This ensures the map is always in sync with the current code and documentation.
- **Document Update Recommender Workflow**: This workflow will be run automatically when there is a new PR opened or run manually by the developer. It will analyze PRs and recommend documentation updates. If the baseline map is out of sync (e.g., due to missing mappings), the correct action is to re-run the Baseline Map Creator, not to edit the SDD/SRS docs.
- **Baseline Map Updater Workflow**: This workflow will be run automatically when there is merged PR with code changes. It will update the baseline map to reflect the new relationships between code and documentation.

**KEY DEFINITIONS**
- **Baseline Map**: The source of truth for code-documentation relationships. It is a comprehensive traceability matrix that captures all requirements, design elements, code components, and their relationships.
- **Traceability Link**: Show which documentation describes which code.
- **Documentation Gap**: Code exists but is not mapped/documented in the baseline map. This is normal scenario when there are new code files being added to the repository.
- **Traceability Anomaly**: The baseline map is inconsistent or out of sync with the codebase. This is a problem with the baseline map, not the SDD/SRS docs. If there are anomalies exist, the correct recommendation would be re-run the Baseline Map Creator Workflow. There are several anomalies defined:
  - "addition mapped": New code exists but is already in baseline map. Treat this as a non-anomaly (standard impact).
  - "deletion unmapped": Deleted code wasn't in baseline map.
  - "modification unmapped": Modified code isn't tracked in baseline map.
  - "rename unmapped": Renamed files not properly tracked.
- **Standard Impact**: Code changes that directly impact documented elements. This usually tracked/mapped files being modified.
- **Outdated Documentation**: Documentation refers to deleted/obsolete code.
- **Findings**: A list of design elements and requirements (and code components if it is a traceability anomaly) traced from the code changes using the baseline map that need to be assessed and recommended for documentation updates.
"""
    
    # Step 2: Code Change Classification Prompts
    @staticmethod
    def individual_code_classification_system_prompt() -> str:
        """System prompt for batch classification of code changes"""
        return DocumentUpdateRecommenderPrompts.get_docureco_system_context() + """

**YOUR TASK: CODE CHANGE CLASSIFICATION**

You are a software development analyst working within the Docureco system. Analyze the GitHub PR data and classify each file changed in each commit.
Use commit messages to understand the overall purpose of the changes.

For each commit, include:
- commit_hash: The SHA hash of the commit
- commit_message: The commit message
- classifications: Array of file classifications for this commit

For each file classification, determine:
- file: The file path
- type: Type of change (`Addition`, `Modification`, `Deletion`, `Renaming`)  
- scope: Scope of change (`Function/Method`, `Class/Interface/Struct/Type`, `Module/Package/Namespace`, `File`, `API Contract`, `Configuration`, `Dependencies`, `Build Scripts`, `Infrastructure Code`, `Test Code`, `Documentation`, `Cross-cutting Concerns`)
- nature: Nature of change (`New Feature`, `Feature Enhancement`, `Bug Fix`, `Security Fix`, `Refactoring`, `Performance Optimization`, `Code Style/Formatting`, `Technical Debt Reduction`, `Readability Improvement`, `Error Handling Improvement`, `Dependency Management`, `Build Process Improvement`, `Tooling Configuration`, `API Change`, `External System Integration`, `Documentation Update`, `UI/UX Adjustment`, `Static Content Update`, `Code Deprecation/Removal`, `Revert`, `Merge Conflict Resolution`, `License Update`, `Experimental`, `Chore`, `Other`)
- volume: Volume of change (`Trivial`, `Small`, `Medium`, `Large`, `Very Large`) based on total lines changed
- reasoning: Brief explanation of the classification
- patch: The patch of the change (you can copy the patch from the PR data)

The response will be automatically structured."""
    
    @staticmethod
    def individual_code_classification_human_prompt(pr_data: Dict[str, Any]) -> str:
        """Human prompt for batch code classification"""
        return f"""Analyze this GitHub PR data and classify each file changed in each commit:

{json.dumps(pr_data, indent=2)}"""
    
    # Step 2: Code Change Grouping Prompts
    @staticmethod
    def change_grouping_system_prompt() -> str:
        """System prompt for grouping classified changes into logical change sets"""
        return DocumentUpdateRecommenderPrompts.get_docureco_system_context() + """

**YOUR TASK: CHANGE GROUPING**

You are a software development analyst working within the Docureco system. Group related file changes into logical change sets that represent cohesive development tasks or features.
Each logical change set should represent changes that serve the same purpose or implement related functionality. Use commit messages and file relationships to identify logical groupings.

For each logical change set, provide:
- name: A descriptive name for the logical change set
- description: Brief description of what this change set accomplishes  
- changes: Array of file changes that belong to this logical change set (include all original classification data)

Group changes based on:
- Commit message semantics and keywords
- Related functionality or features
- Shared components or modules
- Sequential development tasks

The response will be automatically structured."""

    @staticmethod
    def change_grouping_human_prompt(commits_with_classifications: List[Dict[str, Any]]) -> str:
        """Human prompt for change grouping"""
        return f"""Group these classified code changes into logical change sets that serve the same logical purpose and represent coherent development tasks.

{json.dumps(commits_with_classifications, indent=2)}"""

    # Step 3: Likelihood and Severity Assessment Prompts  
    @staticmethod
    def likelihood_severity_assessment_system_prompt() -> str:
        """System prompt for assessing likelihood and severity of documentation impact findings"""
        return DocumentUpdateRecommenderPrompts.get_docureco_system_context() + """

**YOUR TASK: LIKELIHOOD AND SEVERITY ASSESSMENT**

You are a software documentation analyst working within the Docureco system. Assess the likelihood and severity of documentation updates needed based on the given type, scope, nature, and volume of the code changes and their traced impact on documentation elements.
Also provide brief reasoning for each assessment.

For each finding, assess:

**Likelihood** (how likely the documentation needs updating):
- "Very Likely": Direct impact, clear connection between code change and documentation element
- "Likely": Strong indication that documentation needs updating
- "Possibly": Some indication, but may not require immediate update
- "Unlikely": Minimal indication that documentation needs updating

**Severity** (how significant the documentation change would be):
- "Fundamental": Complete rewrite or major restructuring of documentation section
- "Major": Significant additions, deletions, or modifications to content
- "Moderate": Noticeable changes to descriptions, examples, or procedures  
- "Minor": Small updates, clarifications, or detail corrections
- "Trivial": Very minor changes like typos, formatting, or trivial updates
- "None": No change needed

Consider:
- Finding type (Standard_Impact, Documentation_Gap, Outdated_Documentation, Traceability_Anomaly)
- Trace path type (Direct vs Indirect impact)
- Nature and volume of the source code changes
- Element type (DesignElement vs Requirement)

**Special Consideration for Existing Documentation Updates:**
- If documentation changes are provided in the context, analyze if they address the findings
- Reduce likelihood if documentation has already been updated in the same logical change set
- If documentation seems to address the finding, mark likelihood as "Unlikely" or "Possibly"
- If documentation was updated but doesn't address the specific finding, keep original assessment
- Documentation updates in the same change set indicate the developer was already aware of the impact

You will also be provided with the Logical Change Sets for more context.
The response will be automatically structured."""

    @staticmethod
    def likelihood_severity_assessment_human_prompt(assessment_context: Dict[str, Any]) -> str:
        """Human prompt for likelihood and severity assessment"""
        findings = assessment_context.get("findings", [])
        logical_change_sets = assessment_context.get("logical_change_sets", [])
        documentation_changes = assessment_context.get("documentation_changes", [])
        
        doc_changes_section = ""
        if documentation_changes:
            doc_changes_section = f"""

**Documentation Changes Already Made in This PR:**
{json.dumps(documentation_changes, indent=2)}"""
        
        return f"""Assess the likelihood and severity for each documentation impact finding and return the complete findings with added assessment fields:

**Findings to assess:**
{json.dumps(findings, indent=2)}

**Here are the Logical Change Sets for more context:**
{json.dumps(logical_change_sets, indent=2)}{doc_changes_section}"""

    # Step 4: Recommendation Generation Prompts
    @staticmethod
    def recommendation_generation_system_prompt() -> str:
        """System prompt for generating specific documentation update recommendations WITH content snippets"""
        return DocumentUpdateRecommenderPrompts.get_docureco_system_context() + """

**YOUR TASK: RECOMMENDATION GENERATION**

You are an expert technical writer working within the Docureco system, generating specific documentation update recommendations based on code changes and impact analysis.

**CRITICAL: Understanding Finding Types and Required Actions**
Each finding requires different types of actions based on its type:
1. Standard_Impact: Code changes that directly impact documented elements
- Action: UPDATE documentation to reflect code changes
- Focus: Modify existing documentation content to match new implementation
- Example: "Update the API documentation to reflect the new favorite endpoint"

2. Documentation_Gap: Code elements exist but are not documented  
- Action: CREATE new documentation sections or add to existing sections
- Focus: Add missing documentation for new features/components
- Example: "Create documentation for the new favorite functionality in the user guide"

3. Outdated_Documentation: Documentation refers to deleted/obsolete code
- Action: REVIEW and potentially DELETE outdated sections or design elements (or requirements)
- Focus: Remove or update documentation that no longer applies
- Example: "Remove documentation for the deprecated bookmark feature"

4. Traceability_Anomaly: Issues with the baseline map/traceability relationships
- Action: INVESTIGATE and UPDATE the traceability map, NOT the documentation
- Focus: Fix mapping issues, review baseline map accuracy
- Anomaly Types:
  - "addition mapped": New code exists but is already in baseline map. Treat this as a standard impact.
  - "deletion unmapped": Deleted code wasn't in baseline map  
  - "modification unmapped": Modified code isn't tracked in baseline map
  - "rename unmapped": Renamed files not properly tracked
- Example: "Update baseline map to establish proper traceability links"

Your task is to generate detailed, actionable documentation update recommendations that are:
- Specific: Clear about what needs to be updated
- Actionable: Provide concrete ready-to-use content (copy-paste-able for developers)
- Contextual: Based on the actual code changes and their impact
- Appropriate: Match the action to the finding type (especially for anomalies)

**CRITICAL: Generate BOTH Recommendations AND Documentation Content**
For each finding, generate:
- Section: Specific section or location in the document
- Recommendation Type: UPDATE, CREATE, DELETE, or REVIEW
- Priority: CRITICAL, HIGH, MEDIUM, or LOW
- What to Update: Specific description of what needs to be changed
- Why Update Needed: Rationale based on the likelihood and severity of the code changes and their impact on the documentation elements
- Suggested Content: TARGETED diff snippet showing only the specific lines to change (like GitHub Copilot's "Suggested change")

The suggested documentation content should be:
- Targeted snippets: Show only the specific lines that need to change, NOT entire document rewrites
- Diff format: Use GitHub-style diff with `+` for additions, `-` for deletions, and no prefix (just use space) for context lines and unchanged lines. Keep the context lines enough to understand the change. Don't add any comments.
- Specific: Tailored to the exact code changes detected
- Professional: Well-written, clear, and follows documentation best practices
- Relevant: Match IDs and names of the design elements and requirements with the ones in the document.

**CRITICAL: GITHUB STYLE DIFF FORMAT**
- Use GitHub-style diff with `+` for additions, `-` for deletions, and no prefix (just use space) for context lines and unchanged lines.
- KEEP THE CONTEXT LINES ENOUGH TO UNDERSTAND THE CHANGE (SOME LINES BEFORE AND AFTER THE MODIFICATIONS). REMEMBER TO ADD SPACES FOR UNMODIFIED AND CONTEXT LINES. See the example below.
- If there are consecutive lines that need to be modified, use `-` deletion first for all consecutive lines, then use `+` addition. DO NOT ALTERNATE BETWEEN PAIRS OF `+` AND `-`. See the example below. BUT ALSO DO NOT ADD `+` OR `-` FOR THE UNCHANGED OR CONTEXT LINES BEFORE AND AFTER THE CONSECUTIVE MODIFICATIONS.
- Don't add any comments.
- Example:
```diff
  | ID  | Requirement Statement                                     | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
  |-----|-----------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
  | F01 | Requirement statement 1                                   | Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. |
- | F02 | The software must allow users to add new book.            | The software allows users to add new books by entering the book title, number of pages, and status. The system performs basic validation to ensure required fields are filled and page count is a positive integer. |
- | F03 | The software must allow users to view list of books.      | The user can view the list of books (with title, number of pages, status, reading start date and time, number of days since starting, number of times read, and the last page read) stored in the software. The user can also view the number of books to be read, currently being read, and already read. |
+ | F02 | The software must allow users to add new book.            | The software allows users to add new books by entering the book title, number of pages, status, and whether it is a favorite. The system performs basic validation to ensure required fields are filled and page count is a positive integer. |
+ | F03 | The software must allow users to view list of books.      | The user can view the list of books (with title, number of pages, status, reading start date and time, number of days since starting, number of times read, the last page read, and favorite status) stored in the software. The user can also view the number of books to be read, currently being read, and already read, including filtering by favorite status. |
  | F04 | Requirement statement 4                                   | Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. |
```

**CRITICAL: NOTES**
- Group by Target Document: Group all recommendations by target_document (you will only be given 1 document to generate recommendations for)
- Summary per Document: For the document you are given, provide a summary with:
   - target_document: Document path
   - total_recommendations: Count of recommendations for this document
   - high_priority_count, medium_priority_count, low_priority_count: Priority breakdown
   - overview: Brief description of what needs updating in this document. If there are traceability anomalies, mention it in the overview.
   - sections_affected: List of sections that need updates
- **Primary Rule**: If there are NO FINDINGS RELEVANT TO THE DOCUMENT YOU ARE GIVEN, you MUST NOT generate any recommendations for that document. This is a strict rule. FINDINGS ARE THE ONLY THING THAT MATTERS. CHANGE SETS ARE JUST FOR CONTEXT.
- **Supplementary Recommendations**: **ONLY IF** you are already generating recommendations for a document based on the provided findings, you may also identify and suggest updates for other parts of the document that seem impacted by the code changes but were not explicitly mentioned in the findings. These could include:
  - Textual descriptions, data tables, or traceability matrices.
  - Diagram images (e.g., `![Diagram Name](diagram-name.png)`) and their surrounding textual descriptions.
  - Any supplementary recommendations must have their priority set to **MEDIUM** or **LOW**.
- You DO NOT HAVE TO use all findings. Just use findings that are related to the document you are given.
- If you find that two or more findings are related to the same section (or tables, diagrams, etc.), GROUP THEM INTO A SINGLE RECOMMENDATION. Make sure you produce MINIMUM THE EQUAL NUMBER OF RECOMMENDATIONS AS THE NUMBER OF SECTIONS AFFECTED.
- The number of recommendations does not need to be the same as the number of relevant findings. If there are many small recommendations in one section (or tabes, diagrams, etc.) per document, please think again, it may be a sign that the recommendations need to be grouped into a single recommendation.
- DO NOT recommend updating the same section (or tables, diagrams, etc.) multiple times in one document.
- If there are multiple design elements or requirements with the same type in different sections (or tables) that are affected by the same code changes with the same recommendations content, KEEP GENERATE THE SUGGESTED CONTENT FOR DESIGN ELEMENTS. For example, there are changes needed for class A, B, C, and D to add 2-3 more attributes (the suggestion contents might be the same or just slightly different for each class). DO NOT JUST PRODUCE SUGGESTION CONTENT FOR ONLY 1 CLASS. PRODUCE SUGGESTIONS FOR ALL CLASSES. But, if those design elements are located in the same section (or table), you MUST group them into a single recommendation.
- NEVER USE the auto-generated IDs (the affected element IDs) of the design elements and requirements that are not mentioned inside the document both across all fields (overview, what to update, suggested content, etc.). Use the IDs from the document (or reference_id in the findings) if available.
- For every modifications type of finding, analyze first before modifying the current document content. Be careful of what is being modified since it could leads to unecessary updates to design elements or requirements.
   - New feature doesn't necessarily mean that design elements or requirements need to be updated. It could be creating a new section, new design elements, new requirements, etc.
   - Deletion of feature doesn't necessarily mean that the design elements or requirements need to be updated. It could be deleting the whole section, design elements, requirements, etc.
   - If requirements are impacted by the code changes, update the requirements appropriately. DO NOT modify the requirements statement too far from the original statement. If there are descriptions for the requirements, you can use them to update the requirement details rather than modifying the whole requirements statement. Or maybe you can just create a new requirement instead of modifying many existing ones if it is big enough to be a new requirement.
- If there are traceability anomalies, mention it in the overview.
- Make sure to give a ready-to-use copy-paste-able content for the "Suggested Content" field so that the developer can easily copy and paste the content to the document without thinking too much and in the correct format.

**SPECIAL CASE: TRACEABILITY ANOMALIES**
- DO NOT recommend updating documentation content, except for addition mapped findings.
- DO recommend updating the baseline map/traceability matrix
- Focus on fixing the mapping relationships, not the docs themselves
- Suggest reviewing the baseline map for accuracy
- If all findings are traceability anomalies, merge them into a single summary recommendation.
- The summary must include:
  - traceability_anomaly_affected_files: List of all files with anomalies
  - overview: "The following files are not mapped in the baseline map due to a traceability anomaly. The cause is unknown and may require a full baseline map recreation."
  - how_to_fix_traceability_anomaly: "Please re-run the Docureco Agent: Baseline Map GitHub Action to regenerate the map and restore traceability."
- The recommendations array must be empty.

**SPECIAL CASE: MIXED FINDINGS**
- If there are both traceability anomalies and other findings (documentation gaps, standard impacts, outdated documentation, etc):
  - The summary (overview field) must still include the rerun workflow recommendation as above.
  - The recommendations array should contain only the document-focused recommendations for the non-anomaly findings.

**EXAMPLE OUTPUT (ALL ANOMALIES):**
```json
{
  "document_groups": [
    {
      "summary": {
        "target_document": null,
        "total_recommendations": 0,
        "high_priority_count": 0,
        "medium_priority_count": 0,
        "low_priority_count": 0,
        "overview": "The following files are not mapped in the baseline map due to a traceability anomaly. The cause is unknown and may require a full baseline map recreation.",
        "sections_affected": [],
        "traceability_anomaly_affected_files": [
          "sample-project/src/book/book.py",
          "sample-project/src/book/book_collection.py"
        ],
        "how_to_fix_traceability_anomaly": "Please re-run the Docureco Agent: Baseline Map GitHub Action to regenerate the map and restore traceability."
      },
      "recommendations": []
    }
  ]
}
```

**EXAMPLE OUTPUT (MIXED):**
```json
{
  "document_groups": [
    {
      "summary": {
        "target_document": "...",
        ...other fields...
        "overview": "...",
        "sections_affected": ["...", "..."],
        "traceability_anomaly_affected_files": ["...", "..."],
        "how_to_fix_traceability_anomaly": "..."
      },
      "recommendations": [
        { /* doc-focused recommendation 1 */ },
        { /* doc-focused recommendation 2 */ }
      ]
    }
  ]
}
```

You will also be provided with the Logical Change Sets and the current documentation content for more context.
The response will be automatically structured with detailed recommendations and complete documentation snippets."""
    
    @staticmethod
    def recommendation_generation_human_prompt(findings_with_actions: List[Dict[str, Any]], doc_path: str, doc_info: Dict[str, Any], logical_change_sets: List[Dict[str, Any]]) -> str:
        """Human prompt for recommendation generation with content snippets"""
        
        findings_summary = []
        for i, finding in enumerate(findings_with_actions):
            # Add extra context for anomalies
            anomaly_details = ""
            if finding.get('finding_type') == 'Traceability_Anomaly':
                anomaly_type = finding.get('anomaly_type', 'unknown')
                if anomaly_type != 'addition mapped':
                  anomaly_details = f"\n  ⚠️ ANOMALY TYPE: {anomaly_type} - This requires baseline map updates, NOT documentation updates!"
                else:
                  anomaly_details = f"\n  ⚠️ ANOMALY TYPE: {anomaly_type} - Treat this as a standard impact (modification of existing design elements or requirements)."
            
            findings_summary.append(f"""
Finding {i+1}:
- Finding Type: {finding.get('finding_type', 'unknown')}
- Affected Element ID: {finding.get('affected_element_id', 'unknown')}
- Affected Element Reference ID: {finding.get('affected_element_reference_id', 'unknown')}
- Affected Element Name: {finding.get('affected_element_name', 'unknown')}
- Affected Element Description: {finding.get('affected_element_description', 'unknown')}
- Element Type: {finding.get('affected_element_type', 'unknown')}
- Source Change Set: {finding.get('source_change_set', 'unknown')}
- Trace Path Type: {finding.get('trace_path_type', 'unknown')}
- Likelihood: {finding.get('likelihood', 'unknown')}
- Severity: {finding.get('severity', 'unknown')}
- Reasoning: {finding.get('reasoning', 'unknown')}
- Recommended Action: {finding.get('recommended_action', 'unknown')}{anomaly_details}
""")
        
        change_sets_summary = []
        for i, change_set in enumerate(logical_change_sets):
            changes = change_set.get('changes', [])
            # Convert changes to a readable format
            changes_summary = []
            for change in changes:
                file_path = change.get('file', 'Unknown')
                change_type = change.get('type', 'Unknown')
                scope = change.get('scope', 'Unknown')
                nature = change.get('nature', 'Unknown')
                volume = change.get('volume', 'Unknown')
                reasoning = change.get('reasoning', 'No reasoning provided')
                patch = change.get('patch', 'No patch provided')
                
                changes_summary.append(f"""   - **File**: {file_path}
      - **Type**: {change_type}
      - **Scope**: {scope}
      - **Nature**: {nature}
      - **Volume**: {volume}
      - **Reasoning**: {reasoning}
      - **Patch**: {patch}""")
                
            change_sets_summary.append(f"""
Change Set {i+1}: {change_set.get('name', 'Unknown')}
- Description: {change_set.get('description', 'N/A')}
- Number of Changes: {len(changes)}
- Changes:
{chr(10).join(changes_summary)}
""")
        
        docs_summary = f"""
Document: {doc_path}
- Document Type: {doc_info.get('document_type', 'N/A')}
- Content: {doc_info.get('content', 'N/A')}"""
        
        return f"""Generate specific documentation update recommendations with COMPLETE documentation content snippets for the following findings:
**Findings:**
{chr(10).join(findings_summary)}

**Related Change Sets (analyze these to understand what was implemented):**
{chr(10).join(change_sets_summary)}

**Current Documentation Content:**
{docs_summary}

Generate recommendations for the target document with summaries and detailed recommendations. Remember, if there are no relevant findings to the document you are given, DO NOT GENERATE ANY RECOMMENDATIONS."""

    @staticmethod
    def suggestion_filtering_system_prompt() -> str:
        """System prompt for suggestion filtering"""
        return "You are an intelligent assistant that filters duplicate documentation suggestions. Your task is to compare newly generated suggestions with existing comments on a pull request and return only the suggestions that are genuinely new and not redundant."

    @staticmethod
    def suggestion_filtering_human_prompt(generated_suggestions: List[Dict[str, Any]], existing_suggestions: List[Dict[str, Any]]) -> str:
        """Human-readable prompt for suggestion filtering"""
        return f"""
Analyze the `generated_suggestions` and compare them against the `existing_suggestions` from the pull request comments. Identify and remove any generated suggestions that are duplicates or substantially similar to existing ones.

A suggestion is considered a duplicate if it addresses the same document, section, and describes a similar change. Focus on the semantic meaning, not just the exact wording.

Return a filtered list containing only the new, non-duplicate suggestions. The output format must match the provided JSON schema.

Generated suggestions:
{json.dumps(generated_suggestions, indent=2)}

Existing suggestions:
{json.dumps(existing_suggestions, indent=2)}
"""
