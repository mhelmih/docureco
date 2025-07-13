"""
Prompts for Document Update Recommender workflow
"""

from typing import Dict, Any, List
import json


class DocumentUpdateRecommenderPrompts:
    """Collection of prompts for document update recommender workflow"""
    
    # Step 2: Code Change Classification Prompts
    @staticmethod
    def individual_code_classification_system_prompt() -> str:
        """System prompt for batch classification of code changes"""
        return """You are a software development analyst. Analyze the GitHub PR data and classify each file changed in each commit.
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
- reasoning: Brief explanation of your classification

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
        return """You are a software development analyst. Group related file changes into logical change sets that represent cohesive development tasks or features.

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
        return """You are a software documentation analyst. Assess the likelihood and severity of documentation updates needed based on code changes and their traced impact on documentation elements.

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
        """System prompt for generating specific documentation update recommendations"""
        return """You are an expert technical writer generating specific documentation update recommendations based on code changes and impact analysis.

Your task is to generate detailed, actionable documentation update recommendations that are:
- **Specific**: Clear about what needs to be updated
- **Actionable**: Provide concrete steps or content suggestions
- **Contextual**: Based on the actual code changes and their impact
- **Practical**: Can be implemented by development teams

For each high-priority finding, generate:
- **Target Document**: Which document needs updating (SRS, SDD, etc.)
- **Section**: Specific section or location in the document
- **Recommendation Type**: UPDATE, CREATE, DELETE, or REVIEW
- **Priority**: HIGH, MEDIUM, or LOW
- **What to Update**: Specific description of what needs to be changed
- **Where to Update**: Exact location or section reference
- **Why Update Needed**: Rationale based on code changes
- **How to Update**: Step-by-step guidance or content suggestions
- **Suggested Content**: Specific text or structure recommendations (when applicable)

The response will be automatically structured with detailed recommendations."""
    
    @staticmethod
    def recommendation_generation_human_prompt(findings_with_actions: List[Dict[str, Any]], current_docs: Dict[str, Any], logical_change_sets: List[Dict[str, Any]]) -> str:
        """Human prompt for recommendation generation"""
        
        findings_summary = []
        for i, finding in enumerate(findings_with_actions):
            findings_summary.append(f"""
Finding {i+1}:
- Type: {finding.get('finding_type', 'unknown')}
- Affected Element: {finding.get('affected_element_id', 'unknown')}
- Element Type: {finding.get('affected_element_type', 'unknown')}
- Likelihood: {finding.get('likelihood', 'unknown')}
- Severity: {finding.get('severity', 'unknown')}
- Source Change Set: {finding.get('source_change_set', 'unknown')}
- Recommended Action: {finding.get('recommended_action', 'unknown')}
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
        
        docs = []
        for file_path, value in current_docs.items():
            docs.append(f"""
Document: {file_path}
- Document Type: {value.get('document_type', 'N/A')}
- Content: {value.get('content', 'N/A')}
""")
        
        return f"""Generate specific documentation update recommendations for the following high-priority findings:

**High-Priority Findings:**
{chr(10).join(findings_summary)}

**Related Change Sets:**
{chr(10).join(change_sets_summary)}

**Current Documentation Context:**
{chr(10).join(docs)}

Generate detailed, actionable recommendations and return them as a structured JSON array."""

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