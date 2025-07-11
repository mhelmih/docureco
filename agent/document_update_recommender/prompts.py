"""
Prompts for Document Update Recommender workflow
"""

from typing import Dict, Any, List
import json


class DocumentUpdateRecommenderPrompts:
    """Collection of prompts for document update recommender workflow"""
    
    @staticmethod
    def impact_analysis_system_prompt() -> str:
        """System prompt for analyzing code changes impact on documentation"""
        return """You are an expert software architect analyzing code changes to determine their impact on documentation. Your task is to:

1. Analyze code changes and their semantic meaning
2. Identify which documentation sections may be affected
3. Determine the severity and scope of required documentation updates
4. Recommend specific documentation changes needed

For each impacted documentation section, provide:
- document_type: Type of document (SRS, SDD, API, etc.)
- section_name: Specific section or component affected
- impact_level: Severity (critical, high, medium, low)
- change_type: Type of change needed (update, add, remove, restructure)
- recommendation: Specific recommendation for the documentation update

Return a JSON object with impact analysis results."""
    
    @staticmethod
    def impact_analysis_human_prompt(code_changes: List[Dict[str, Any]], traceability_map: Dict[str, Any]) -> str:
        """Human prompt for impact analysis"""
        return f"""Analyze the following code changes and determine their impact on documentation using the traceability map:

Code Changes:
{json.dumps(code_changes, indent=2)}

Traceability Map:
{json.dumps(traceability_map, indent=2)}

Analyze the impact and return recommendations as a JSON object."""
    
    @staticmethod
    def recommendation_generation_system_prompt() -> str:
        """System prompt for generating specific documentation update recommendations"""
        return """You are an expert technical writer generating specific documentation update recommendations based on code changes and traceability analysis. Your task is to:

1. Generate detailed, actionable documentation update recommendations
2. Prioritize recommendations based on impact and urgency
3. Provide specific content suggestions where possible
4. Consider documentation consistency and quality

For each recommendation, provide:
- priority: Urgency level (urgent, high, medium, low)
- document_path: Path to the document that needs updating
- section_reference: Specific section or line numbers
- update_type: Type of update (content_change, structure_change, addition, removal)
- suggested_content: Specific content suggestions or templates
- rationale: Explanation of why this update is needed

Return a JSON object with prioritized recommendations."""
    
    @staticmethod
    def recommendation_generation_human_prompt(impact_analysis: Dict[str, Any], documentation_content: Dict[str, str]) -> str:
        """Human prompt for recommendation generation"""
        return f"""Based on the following impact analysis and current documentation content, generate specific, actionable documentation update recommendations:

Impact Analysis:
{json.dumps(impact_analysis, indent=2)}

Current Documentation Content:
{json.dumps(documentation_content, indent=2)}

Generate prioritized recommendations and return them as a JSON object."""
    
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