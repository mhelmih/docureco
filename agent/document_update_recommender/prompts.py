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

**1. BASELINE MAP CREATOR WORKFLOW**
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

**2. DOCUMENT UPDATE RECOMMENDER WORKFLOW (Your Current Role)**
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

**3. BASELINE MAP UPDATER WORKFLOW**
- **Purpose**: Updates baseline maps when repository structure changes
- **Input**: Repository changes + existing Baseline Map
- **Process**:
  - Analyzes significant repository changes
  - Identifies new/modified requirements, design elements, and code components
  - Updates traceability links to reflect new relationships
- **Output**: Updated Baseline Map
- **When Used**: When major architectural changes occur

**BASELINE MAP CONCEPT**

A Baseline Map is a comprehensive traceability matrix that captures:

1. **Requirements** (from SRS documents):
   - Business requirements, functional requirements, non-functional requirements
   - Each has: ID, title, description, type, priority, section reference

2. **Design Elements** (from SDD documents):
   - Architecture components, classes, interfaces, services, databases, UI elements
   - Each has: ID, name, description, type, section reference

3. **Code Components** (from source code):
   - Files, classes, functions, modules, APIs
   - Each has: ID, path, name, type, description

4. **Traceability Links** (relationships between elements):
   - Requirements → Design Elements (what implements each requirement)
   - Design Elements → Code Components (what code implements each design)
   - Design Elements → Design Elements (dependencies and relationships)

**Example Baseline Map Structure:**
```
Requirements: REQ-001 "User can add books" → 
Design Elements: DE-001 "BookService class" → 
Code Components: CC-001 "src/book/book_collection.py"
```

**YOUR ROLE AS DOCUMENT UPDATE RECOMMENDER**

You analyze code changes in PRs and use the baseline map to:
1. **Trace Impact**: Follow traceability links to find which documentation elements are affected
2. **Classify Findings**: Identify gaps, outdated content, standard impacts, and anomalies
3. **Generate Recommendations**: Create targeted documentation update suggestions
4. **Handle Anomalies**: When code changes don't match the baseline map, recommend map updates

**CRITICAL UNDERSTANDING:**
- **Baseline Map**: The source of truth for code-documentation relationships
- **Traceability Links**: Show which documentation describes which code
- **Documentation Gap**: Code exists but isn't documented
- **Outdated Documentation**: Documentation refers to deleted/obsolete code  
- **Standard Impact**: Code changes affect documented elements (normal case)
- **Traceability Anomaly**: Code changes don't match baseline map (map needs updating)
"""
    
    # Step 2: Code Change Classification Prompts
    @staticmethod
    def individual_code_classification_system_prompt() -> str:
        """System prompt for batch classification of code changes"""
        return DocumentUpdateRecommenderPrompts.get_docureco_system_context() + """

**YOUR TASK: CODE CHANGE CLASSIFICATION**

You are a software development analyst working within the Docureco system. Analyze the GitHub PR data and classify each file changed in each commit.

For each commit, include:
- commit_hash: The SHA hash of the commit
- commit_message: The commit message
- classifications: Array of file classifications for this commit

For each file classification, determine:
- file: The file path
- type: Type of change (Added, Modified, Deleted, Renamed)  
- scope: Scope of change (Function/Method, Class, Module, Configuration, Documentation, Test, etc.)
- nature: Nature of change (New Feature, Bug Fix, Refactoring, Documentation Updates, Performance Improvement, etc.)
- volume: Volume of change (Trivial, Small, Medium, Large, Very Large) based on total lines changed
- reasoning: Brief explanation of the classification

Look at the commit messages, file paths, and changes to understand the overall purpose.
The response will be automatically structured. Analyze the cumulative net effect of changes per file across all commits, using commit messages to understand the development intent."""
    
    @staticmethod
    def individual_code_classification_human_prompt(pr_data: Dict[str, Any]) -> str:
        """Human prompt for batch code classification"""
        return f"""Analyze this GitHub PR data and classify each file changed in each commit:

    {pr_data}

    Return a JSON object with a 'commits' array. Each commit should have:
    - commit_hash (the SHA)
    - commit_message 
    - classifications array with file classifications for that commit

    Organize the output by commit, so each commit shows only the files that were changed in that specific commit."""
    
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
        return f"""Group these classified code changes into logical change sets:

{json.dumps(commits_with_classifications, indent=2)}

Analyze the commit messages and file changes to identify related changes that serve the same logical purpose. Group them into meaningful change sets that represent coherent development tasks."""

    # Step 3: Likelihood and Severity Assessment Prompts  
    @staticmethod
    def likelihood_severity_assessment_system_prompt() -> str:
        """System prompt for assessing likelihood and severity of documentation impact findings"""
        return DocumentUpdateRecommenderPrompts.get_docureco_system_context() + """

**YOUR TASK: LIKELIHOOD AND SEVERITY ASSESSMENT**

You are a software documentation analyst working within the Docureco system. Assess the likelihood and severity of documentation updates needed based on code changes and their traced impact on documentation elements.

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

Provide brief reasoning for each assessment."""

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
{json.dumps(documentation_changes, indent=2)}

IMPORTANT: Consider these existing documentation updates when assessing likelihood and severity:
- If documentation has already been updated in the same change set as the code change, reduce likelihood
- If documentation updates seem to address the finding, mark likelihood as "Unlikely" or "Possibly"
- If documentation was updated but doesn't seem to address the specific finding, keep original assessment"""
        
        return f"""Assess the likelihood and severity for each documentation impact finding and return the complete findings with added assessment fields:

**Findings to assess:**
{json.dumps(findings, indent=2)}

**Context - Logical Change Sets:**
{json.dumps(logical_change_sets, indent=2)}{doc_changes_section}

For each finding, return the COMPLETE finding with these additional fields:
- likelihood: One of "Very Likely", "Likely", "Possibly", "Unlikely"
- severity: One of "Fundamental", "Major", "Moderate", "Minor", "Trivial", "None"  
- reasoning: Brief explanation of your assessment

Return the complete findings array with all original fields plus the new assessment fields. Do NOT just return the assessments separately - return the full findings with assessments integrated."""

    # Step 4: Recommendation Generation Prompts
    @staticmethod
    def recommendation_generation_system_prompt() -> str:
        """System prompt for generating specific documentation update recommendations WITH content snippets"""
        return DocumentUpdateRecommenderPrompts.get_docureco_system_context() + """

**YOUR TASK: RECOMMENDATION GENERATION**

You are an expert technical writer working within the Docureco system, generating specific documentation update recommendations based on code changes and impact analysis.

**CRITICAL: Understanding Finding Types and Required Actions**

Each finding requires different types of actions based on its type:

**1. Standard_Impact**: Code changes that directly impact documented elements
- **Action**: UPDATE documentation to reflect code changes
- **Focus**: Modify existing documentation content to match new implementation
- **Example**: "Update the API documentation to reflect the new favorite endpoint"

**2. Documentation_Gap**: Code elements exist but are not documented  
- **Action**: CREATE new documentation sections
- **Focus**: Add missing documentation for new features/components
- **Example**: "Create documentation for the new favorite functionality in the user guide"

**3. Outdated_Documentation**: Documentation refers to deleted/obsolete code
- **Action**: REVIEW and potentially DELETE outdated sections
- **Focus**: Remove or update documentation that no longer applies
- **Example**: "Remove documentation for the deprecated bookmark feature"

**4. Traceability_Anomaly**: Issues with the baseline map/traceability relationships
- **Action**: INVESTIGATE and UPDATE the traceability map, NOT the documentation
- **Focus**: Fix mapping issues, review baseline map accuracy
- **Anomaly Types**:
  - "addition mapped": New code exists but is already in baseline map (shouldn't happen)
  - "deletion unmapped": Deleted code wasn't in baseline map  
  - "modification unmapped": Modified code isn't tracked in baseline map
  - "rename unmapped": Renamed files not properly tracked
- **Example**: "Update baseline map to include the new favorite module and establish proper traceability links"

**IMPORTANT FOR TRACEABILITY ANOMALIES:**
- DO NOT recommend updating documentation content
- DO recommend updating the baseline map/traceability matrix
- Focus on fixing the mapping relationships, not the docs themselves
- Suggest reviewing the baseline map for accuracy

**CRITICAL: Generate BOTH Recommendations AND Documentation Content**

For each finding, you must provide:
1. **Recommendation metadata** (what, where, why, how, etc.)
2. **Actual documentation content snippet** - the specific markdown/text content to add/update

The documentation content should be:
- **Targeted snippets**: Show only the specific lines that need to change, NOT entire document rewrites
- **Diff format**: Use GitHub-style diff with `+` for additions, `-` for deletions, and minimal context lines
- **Specific**: Tailored to the exact code changes detected
- **Professional**: Well-written, clear, and follows documentation best practices
- **Minimal**: Focus on just the affected section, like Copilot's "Suggested change" feature

Your task is to generate detailed, actionable documentation update recommendations that are:
- **Specific**: Clear about what needs to be updated
- **Actionable**: Provide concrete steps AND ready-to-use content
- **Contextual**: Based on the actual code changes and their impact
- **Appropriate**: Match the action to the finding type (especially for anomalies)

For each high-priority finding, generate:
- **Target Document**: Which document needs updating (SRS, SDD, etc.)
- **Section**: Specific section or location in the document
- **Recommendation Type**: UPDATE, CREATE, DELETE, or REVIEW
- **Priority**: HIGH, MEDIUM, or LOW
- **What to Update**: Specific description of what needs to be changed
- **Where to Update**: Exact location or section reference
- **Why Update Needed**: Rationale based on code changes
- **How to Update**: Step-by-step guidance
- **Suggested Content**: TARGETED diff snippet showing only the specific lines to change (like GitHub Copilot's "Suggested change")

The response will be automatically structured with detailed recommendations and complete documentation snippets."""
    
    @staticmethod
    def recommendation_generation_human_prompt(findings_with_actions: List[Dict[str, Any]], current_docs: Dict[str, Any], logical_change_sets: List[Dict[str, Any]]) -> str:
        """Human prompt for recommendation generation with content snippets"""
        
        findings_summary = []
        for i, finding in enumerate(findings_with_actions):
            # Add extra context for anomalies
            anomaly_details = ""
            if finding.get('finding_type') == 'Traceability_Anomaly':
                anomaly_type = finding.get('anomaly_type', 'unknown')
                anomaly_details = f"\n  ⚠️ ANOMALY TYPE: {anomaly_type} - This requires baseline map updates, NOT documentation updates!"
            
            findings_summary.append(f"""
Finding {i+1}:
- Type: {finding.get('finding_type', 'unknown')}
- Affected Element: {finding.get('affected_element_id', 'unknown')}
- Element Type: {finding.get('affected_element_type', 'unknown')}
- Likelihood: {finding.get('likelihood', 'unknown')}
- Severity: {finding.get('severity', 'unknown')}
- Source Change Set: {finding.get('source_change_set', 'unknown')}
- Recommended Action: {finding.get('recommended_action', 'unknown')}{anomaly_details}
""")
        
        change_sets_summary = []
        for i, change_set in enumerate(logical_change_sets):
            changes = change_set.get('changes', [])
            files_list = [change.get('file', 'unknown') for change in changes] if changes else []
            change_sets_summary.append(f"""
Change Set {i+1}: {change_set.get('name', 'Unknown')}
- Description: {change_set.get('description', 'N/A')}
- Number of Files: {len(files_list)}
- Files: {', '.join(files_list)}
""")
        
        docs_summary = []
        for doc_path, doc_info in current_docs.items():
            docs_summary.append(f"""
Document: {doc_path}
- Document Type: {doc_info.get('document_type', 'N/A')}
- Content: {doc_info.get('content', 'N/A')}
""")
        
        return f"""Generate specific documentation update recommendations with COMPLETE documentation content snippets for the following high-priority findings:

**CRITICAL: For each recommendation, provide BOTH the recommendation metadata AND the complete, ready-to-use documentation content in markdown format.**

**IMPORTANT INSTRUCTIONS:**
- For Traceability_Anomaly findings: Focus on baseline map updates, NOT documentation content
- For Standard_Impact: Provide complete documentation content updates  
- For Documentation_Gap: Provide complete new documentation sections
- For Outdated_Documentation: Provide guidance and replacement content

**High-Priority Findings:**
{chr(10).join(findings_summary)}

**Related Change Sets (analyze these to understand what was implemented):**
{chr(10).join(change_sets_summary)}

**Current Documentation Context:**
{chr(10).join(docs_summary)}

**CRITICAL REQUIREMENTS:**
1. **Group by Target Document**: Group all recommendations by target_document 
2. **Summary per Document**: For each document group, provide a summary with:
   - target_document: Document path
   - total_recommendations: Count of recommendations for this document
   - high_priority_count, medium_priority_count, low_priority_count: Priority breakdown
   - overview: Brief description of what needs updating in this document
   - sections_affected: List of sections that need updates
3. **Detailed Recommendations**: For each recommendation, provide all standard fields including targeted diff snippets
4. **GitHub-Style Diff Format**: The 'suggested_content' should use minimal diff format:
   - Lines starting with `+` for content to be added
   - Lines starting with `-` for content to be removed/replaced  
   - 1-2 context lines (no prefix) above and below the change
   - Show ONLY the affected section, not entire documents
5. **Example Output Structure**:
    ```json
    {{
      "document_groups": [
        {{
          "summary": {{
            "target_document": "sample-project/doc/srs.md",
            "total_recommendations": 2,
            "high_priority_count": 1,
            "medium_priority_count": 1,
            "low_priority_count": 0,
            "overview": "Update user management requirements to include favorite functionality",
            "sections_affected": ["3.1 User Requirements", "5. Traceability"]
          }},
          "recommendations": [
            {{
              "target_document": "sample-project/doc/srs.md",
              "section": "3.1 User Requirements",
              "recommendation_type": "UPDATE",
              "priority": "HIGH",
              "what_to_update": "Add favorite functionality requirement",
              "where_to_update": "User management section",
              "why_update_needed": "New favorite feature was implemented",
              "how_to_update": "Add requirement for favorite books",
              "suggested_content": "### User Requirements\n- UR-001: User can add books\n+ UR-001: User can add books\n+ UR-002: User can mark books as favorites\n+ UR-003: User can view favorite books list"
            }}
          ]
        }}
      ]
    }}
    ```

Generate recommendations grouped by target document with summaries and detailed recommendations. 

REMEMBER: Match your recommendations to the finding type - anomalies need baseline map fixes, not doc updates!"""

    # Step 2: Single Commit Classification Prompts (for enhanced per-commit analysis)
    @staticmethod
    def single_commit_classification_system_prompt() -> str:
        """System prompt for single commit classification using the 4W framework"""
        return """You are a software engineering expert analyzing code changes from a SINGLE commit. Your task is to classify ALL changed files in this specific commit using the 4W framework for documentation impact analysis.

Since this is a single commit, you have focused context about the specific purpose and changes made in this commit.

For EACH file, analyze:
1. **Type** (What changed in this commit):
   - Addition, Deletion, Modification, Rename
2. **Scope** (Where the change occurred in this commit):
   - Function/Method, Class/Interface/Struct/Type, Module/Package/Namespace, File, API Contract, Configuration, Dependencies, Build Scripts, Infrastructure Code, Test Code, Documentation, Cross-cutting
3. **Nature** (Why this commit was made - analyze the specific commit message):
   - New Feature, Feature Enhancement, Bug Fix, Security Fix, Refactoring, Performance Optimization, Code Style/Formatting, Technical Debt Reduction, Readability Improvement, Error Handling Improvement, Dependency Management, Build Process Improvement, Tooling Configuration, API Changes, External System Integration Changes, Documentation Updates, UI/UX Adjustments, Static Content Updates, Code/Deprecation Removal, Revert, Merge Conflict Resolution, License Updates, Experimental, Chore, Other
4. **Volume** (How much changed in this commit):
   - Trivial (1-5 lines, typo fixes)
   - Small (localized changes, single function)
   - Medium (affects important parts of class/module)
   - Large (substantial changes across multiple modules)
   - Very Large (extensive architectural changes)
5. **Reasoning**: 
   - Brief explanation of the classification based on this commit's changes and message

The response will be automatically structured. Focus on this single commit's purpose and impact."""

    @staticmethod
    def single_commit_classification_human_prompt(commit_files: List[Dict[str, Any]], commit_context: Dict[str, Any]) -> str:
        """Human prompt for single commit classification"""
        
        files_section = ""
        for i, file_data in enumerate(commit_files):
            files_section += f"""
File {i+1}:
- Filename: {file_data['filename']}
- Status: {file_data['status']}
- Additions: {file_data['additions']}
- Deletions: {file_data['deletions']}
- Total Changes: {file_data['changes']}
- Code Diff: {file_data['patch'][:]}

"""
        
        return f"""Analyze and classify ALL the files changed in this SINGLE commit using the 4W framework:

**Commit Context:**
- SHA: {commit_context.get("sha", "N/A")}
- Message: {commit_context.get("message", "N/A")}
- Author: {commit_context.get("author", "N/A")}
- Date: {commit_context.get("date", "N/A")}
- Files Changed: {commit_context.get("files_count", 0)}

**Files Changed in This Commit:**
{files_section}

Since this is a single commit, you have focused context about the specific purpose. Use the commit message to understand the "Why" (Nature) of the changes.

Classify each file and return the results as a structured JSON array.""" 