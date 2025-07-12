"""
Prompts for Document Update Recommender workflow
"""

from typing import Dict, Any, List
import json


class DocumentUpdateRecommenderPrompts:
    """Collection of prompts for document update recommender workflow"""
    
    # Step 1: Scan PR Prompts
    @staticmethod
    def pr_analysis_system_prompt() -> str:
        """System prompt for analyzing PR event data and repository context"""
        return """You are an expert software development analyst specializing in PR (Pull Request) analysis. Your task is to:

1. Analyze PR event data to understand the nature and scope of changes
2. Extract relevant commit information and change patterns
3. Identify key files and components affected
4. Categorize the type of changes (feature, bug fix, refactoring, etc.)

For each PR analysis, provide:
- change_summary: Brief description of what changed
- change_type: Type of change (feature, bugfix, refactoring, documentation, etc.)
- scope: Scope of impact (component, module, system-wide)
- risk_level: Risk assessment (low, medium, high)
- affected_areas: List of affected functional areas

Return a JSON object with the PR analysis results."""
    
    @staticmethod
    def pr_analysis_human_prompt(pr_event_data: Dict[str, Any], repo_content: Dict[str, Any]) -> str:
        """Human prompt for PR analysis"""
        return f"""Analyze the following PR event data and repository context:

PR Event Data:
{json.dumps(pr_event_data, indent=2)}

Repository Content Context:
{json.dumps(repo_content, indent=2)}

Provide a comprehensive analysis of this PR as a JSON object."""
    
    # Step 2: Analyze Code Changes Prompts
    @staticmethod
    def code_change_classification_system_prompt() -> str:
        """System prompt for classifying individual code changes"""
        return """You are an expert software architect analyzing code changes to classify them into logical groups. Your task is to:

1. Classify individual code changes based on their purpose and impact
2. Group related changes into logical change sets
3. Identify dependencies between changes
4. Determine the semantic meaning of changes

For each change classification, provide:
- change_id: Unique identifier for the change
- file_path: Path to the changed file
- change_type: Type of change (addition, modification, deletion, rename)
- semantic_category: Semantic category (api_change, business_logic, configuration, etc.)
- impact_scope: Scope of impact (local, module, system)
- related_changes: List of related change IDs

Return a JSON object with classified changes."""
    
    @staticmethod
    def code_change_classification_human_prompt(changed_files: List[str], pr_data: Dict[str, Any], repo_content: Dict[str, Any]) -> str:
        """Human prompt for code change classification"""
        return f"""Classify the following code changes into logical groups:

Changed Files:
{json.dumps(changed_files, indent=2)}

PR Data:
{json.dumps(pr_data, indent=2)}

Repository Context:
{json.dumps(repo_content, indent=2)}

Classify these changes and return the results as a JSON object."""
    
    @staticmethod
    def logical_grouping_system_prompt() -> str:
        """System prompt for grouping classified changes into logical change sets"""
        return """You are an expert software architect grouping related code changes into logical change sets. Your task is to:

1. Group related changes that serve the same purpose
2. Identify change dependencies and ordering
3. Create logical change sets that represent cohesive modifications
4. Determine the overall impact of each change set

For each logical change set, provide:
- changeset_id: Unique identifier for the change set
- changes: List of individual change IDs in this set
- purpose: Purpose of this change set
- dependencies: List of dependent change set IDs
- impact_level: Overall impact level (low, medium, high)
- affected_components: List of affected system components

Return a JSON object with logical change sets."""
    
    @staticmethod
    def logical_grouping_human_prompt(classified_changes: List[Dict[str, Any]], commit_info: Dict[str, Any]) -> str:
        """Human prompt for logical grouping"""
        return f"""Group the following classified changes into logical change sets:

Classified Changes:
{json.dumps(classified_changes, indent=2)}

Commit Information:
{json.dumps(commit_info, indent=2)}

Group these changes into logical sets and return the results as a JSON object."""
    
    # Step 3: Assess Documentation Impact Prompts
    @staticmethod
    def traceability_analysis_system_prompt() -> str:
        """System prompt for traceability analysis and impact assessment"""
        return """You are an expert software architect specializing in traceability analysis and documentation impact assessment. Your task is to:

1. Analyze traceability relationships between code changes and documentation
2. Determine which documentation elements are potentially impacted
3. Assess the likelihood and severity of documentation impacts
4. Prioritize findings based on business impact

For each impacted documentation element, provide:
- element_id: Unique identifier for the documentation element
- element_type: Type of element (requirement, design, specification, etc.)
- impact_reason: Reason why this element is impacted
- likelihood: Probability of impact (0.0 to 1.0)
- severity: Impact severity (low, medium, high, critical)
- affected_sections: List of affected document sections
- business_impact: Business impact assessment

Return a JSON object with impact analysis results."""
    
    @staticmethod
    def traceability_analysis_human_prompt(logical_change_sets: List[Dict[str, Any]], traceability_map: Dict[str, Any]) -> str:
        """Human prompt for traceability analysis"""
        return f"""Analyze the traceability impact of the following logical change sets:

Logical Change Sets:
{json.dumps(logical_change_sets, indent=2)}

Traceability Map:
{json.dumps(traceability_map, indent=2)}

Assess the documentation impact and return the results as a JSON object."""
    
    @staticmethod
    def impact_prioritization_system_prompt() -> str:
        """System prompt for prioritizing documentation impact findings"""
        return """You are an expert technical writer prioritizing documentation impact findings. Your task is to:

1. Prioritize findings based on business impact, likelihood, and severity
2. Consider documentation quality and consistency requirements
3. Assess the urgency of documentation updates
4. Filter findings to focus on high-priority impacts

For each prioritized finding, provide:
- finding_id: Unique identifier for the finding
- priority_level: Priority level (urgent, high, medium, low)
- business_justification: Business justification for the priority
- update_urgency: How urgent the update is
- quality_impact: Impact on documentation quality
- consistency_impact: Impact on documentation consistency

Return a JSON object with prioritized findings."""
    
    @staticmethod
    def impact_prioritization_human_prompt(combined_findings: List[Dict[str, Any]], logical_change_sets: List[Dict[str, Any]]) -> str:
        """Human prompt for impact prioritization"""
        return f"""Prioritize the following documentation impact findings:

Combined Findings:
{json.dumps(combined_findings, indent=2)}

Logical Change Sets Context:
{json.dumps(logical_change_sets, indent=2)}

Prioritize these findings and return the results as a JSON object."""
    
    # Step 4: Generate and Post Recommendations Prompts
    @staticmethod
    def recommendation_generation_system_prompt() -> str:
        """System prompt for generating specific documentation update recommendations"""
        return """You are an expert technical writer generating specific documentation update recommendations. Your task is to:

1. Generate detailed, actionable documentation update recommendations
2. Provide specific content suggestions and implementation guidance
3. Consider documentation standards and best practices
4. Ensure recommendations are practical and implementable

For each recommendation, provide:
- recommendation_id: Unique identifier for the recommendation
- target_document: Path to the document that needs updating
- section_reference: Specific section or line numbers
- recommendation_type: Type of update (content_change, structure_change, addition, removal)
- priority: Priority level (urgent, high, medium, low)
- what_to_update: Specific description of what needs to be updated
- where_to_update: Exact location in the document
- why_update_needed: Rationale for why this update is necessary
- how_to_update: Step-by-step guidance on how to implement the update
- suggested_content: Specific content suggestions or templates
- validation_criteria: Criteria to validate the update was successful

Return a JSON object with detailed recommendations."""
    
    @staticmethod
    def recommendation_generation_human_prompt(filtered_findings: List[Dict[str, Any]], current_docs: Dict[str, Any], logical_change_sets: List[Dict[str, Any]]) -> str:
        """Human prompt for recommendation generation"""
        return f"""Generate specific documentation update recommendations based on the following:

High-Priority Findings:
{json.dumps(filtered_findings, indent=2)}

Current Documentation Context:
{json.dumps(current_docs, indent=2)}

Logical Change Sets:
{json.dumps(logical_change_sets, indent=2)}

Generate detailed, actionable recommendations and return them as a JSON object."""
    
    @staticmethod
    def recommendation_filtering_system_prompt() -> str:
        """System prompt for filtering recommendations against existing suggestions"""
        return """You are an expert technical writer filtering and managing documentation recommendations. Your task is to:

1. Compare new recommendations with existing suggestions
2. Identify duplicates and conflicts
3. Merge or consolidate similar recommendations
4. Ensure recommendation quality and consistency

For each filtered recommendation, provide:
- recommendation_id: Unique identifier for the recommendation
- action: Action to take (keep, merge, discard, modify)
- merge_target: Target recommendation ID if merging
- modification_reason: Reason for modification if applicable
- quality_score: Quality score (1-10)
- implementation_priority: Implementation priority
- resource_requirements: Estimated resource requirements

Return a JSON object with filtered recommendations."""
    
    @staticmethod
    def recommendation_filtering_human_prompt(generated_suggestions: List[Dict[str, Any]], existing_suggestions: List[Dict[str, Any]]) -> str:
        """Human prompt for recommendation filtering"""
        return f"""Filter the following generated recommendations against existing suggestions:

Generated Suggestions:
{json.dumps(generated_suggestions, indent=2)}

Existing Suggestions:
{json.dumps(existing_suggestions, indent=2)}

Filter and manage these recommendations, returning the results as a JSON object."""
    
    # Quality Assessment Prompts
    @staticmethod
    def quality_assessment_system_prompt() -> str:
        """System prompt for assessing documentation quality after updates"""
        return """You are an expert technical writer assessing documentation quality and consistency. Your task is to:

1. Evaluate the completeness of documentation updates
2. Check for consistency across different documents
3. Identify potential gaps or redundancies
4. Assess overall documentation quality

For the quality assessment, provide:
- completeness_score: Score from 1-10 for completeness
- consistency_score: Score from 1-10 for consistency
- quality_issues: List of identified quality issues
- improvement_suggestions: Specific suggestions for improvement
- overall_rating: Overall quality rating (excellent, good, fair, poor)
- compliance_status: Compliance with documentation standards

Return a JSON object with the quality assessment."""
    
    @staticmethod
    def quality_assessment_human_prompt(updated_documentation: Dict[str, str], recommendations: List[Dict[str, Any]]) -> str:
        """Human prompt for quality assessment"""
        return f"""Assess the quality of the following updated documentation against the original recommendations:

Updated Documentation:
{json.dumps(updated_documentation, indent=2)}

Original Recommendations:
{json.dumps(recommendations, indent=2)}

Provide a comprehensive quality assessment as a JSON object.""" 