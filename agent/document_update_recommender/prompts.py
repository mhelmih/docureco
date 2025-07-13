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
    def individual_code_classification_human_prompt(pr_data: List[Dict[str, Any]]) -> str:
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
        return """You are a software engineering expert grouping related code changes into logical change sets for documentation impact analysis.

Your task is to use commit messages as the primary semantic keys to group file changes that serve the same logical purpose or feature development goal.

Group changes based on:
1. **Commit Message Semantics** - Changes mentioned in related commit messages
2. **Functional Similarity** - Changes that serve the same feature or purpose  
3. **Development Task Coherence** - Changes that together complete a logical development task

Each group should represent a cohesive development task (e.g., "Feature - User Profile Implementation", "Bug Fix - Authentication Issue", "Documentation Updates").

For each logical change set, provide:
- **name**: Descriptive name derived from commit messages (e.g., "Feature - User Profile Implementation")
- **description**: What this change set accomplishes
- **changes**: Array of file changes with their classifications that belong to this logical grouping

The response will be automatically structured as a JSON object with a 'logical_change_sets' array."""
    
    @staticmethod
    def change_grouping_human_prompt(commits_with_classifications: List[Dict[str, Any]]) -> str:
        """Human prompt for change grouping"""
        return f"""Analyze these commits with their file classifications and group related files into logical change sets:

{commits_with_classifications}

Group files that are semantically related across commits (e.g., files that implement the same feature, fix the same bug, etc.) into logical change sets. Each logical change set should have a descriptive name and contain the related file changes."""
    
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
    def recommendation_generation_human_prompt(filtered_findings: List[Dict[str, Any]], current_docs: Dict[str, Any], logical_change_sets: List[Dict[str, Any]]) -> str:
        """Human prompt for recommendation generation"""
        
        findings_summary = []
        for i, finding in enumerate(filtered_findings):
            findings_summary.append(f"""
Finding {i+1}:
- Type: {finding.get('finding_type', 'unknown')}
- Affected Element: {finding.get('affected_element_id', 'unknown')}
- Element Type: {finding.get('affected_element_type', 'unknown')}
- Likelihood: {finding.get('likelihood', 'unknown')}
- Severity: {finding.get('severity', 'unknown')}
- Source Change Set: {finding.get('source_change_set_id', 'unknown')}
""")
        
        change_sets_summary = []
        for i, change_set in enumerate(logical_change_sets):
            change_sets_summary.append(f"""
Change Set {i+1}: {change_set.get('name', 'Unknown')}
- Description: {change_set.get('description', 'N/A')}
- Primary Nature: {change_set.get('primary_nature', 'Other')}
- Estimated Impact: {change_set.get('estimated_impact', 'Medium')}
- Files Changed: {len(change_set.get('changes', []))}
""")
        
        docs_summary = []
        for doc_path, doc_info in current_docs.items():
            content_preview = str(doc_info.get('content', ''))[:200] + "..." if doc_info.get('content') else "No content available"
            docs_summary.append(f"""
Document: {doc_path}
- Content Preview: {content_preview}
""")
        
        return f"""Generate specific documentation update recommendations for the following high-priority findings:

**High-Priority Findings:**
{chr(10).join(findings_summary)}

**Related Change Sets:**
{chr(10).join(change_sets_summary)}

**Current Documentation Context:**
{chr(10).join(docs_summary)}

Generate detailed, actionable recommendations and return them as a structured JSON array."""
    
    # Quality Assessment Prompts
    @staticmethod
    def quality_assessment_system_prompt() -> str:
        """System prompt for assessing documentation quality after updates"""
        return """You are an expert technical writer assessing documentation quality and consistency. Your task is to evaluate the completeness and quality of documentation updates against the original recommendations.

For the quality assessment, provide:
- **Completeness Score**: Score from 1-10 for how well recommendations were addressed
- **Consistency Score**: Score from 1-10 for consistency across different documents
- **Quality Issues**: List of identified quality problems or gaps
- **Improvement Suggestions**: Specific suggestions for improvement
- **Overall Rating**: Overall quality rating (excellent, good, fair, poor)
- **Compliance Status**: Compliance with documentation standards

The response will be automatically structured with detailed quality metrics."""
    
    @staticmethod
    def quality_assessment_human_prompt(updated_documentation: Dict[str, str], recommendations: List[Dict[str, Any]]) -> str:
        """Human prompt for quality assessment"""
        
        updated_docs_summary = []
        for doc_path, content in updated_documentation.items():
            content_preview = content[:300] + "..." if len(content) > 300 else content
            updated_docs_summary.append(f"""
Document: {doc_path}
Updated Content: {content_preview}
""")
        
        recommendations_summary = []
        for i, rec in enumerate(recommendations):
            recommendations_summary.append(f"""
Recommendation {i+1}:
- Target: {rec.get('target_document', 'Unknown')}
- Type: {rec.get('recommendation_type', 'Unknown')}
- What: {rec.get('what_to_update', 'N/A')}
- Priority: {rec.get('priority', 'Unknown')}
""")
        
        return f"""Assess the quality of the following updated documentation against the original recommendations:

**Updated Documentation:**
{chr(10).join(updated_docs_summary)}

**Original Recommendations:**
{chr(10).join(recommendations_summary)}

Provide a comprehensive quality assessment as a structured JSON object.""" 

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
- Code Diff: {file_data['patch'][:800]}...

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