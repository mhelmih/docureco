"""
Prompts for Baseline Map Updater workflow
"""

from typing import Dict, Any, List
import json


class BaselineMapUpdaterPrompts:
    """Collection of prompts for baseline map updater workflow"""
    
    @staticmethod
    def change_analysis_system_prompt() -> str:
        """System prompt for analyzing repository changes"""
        return """You are an expert software architect analyzing repository changes to determine their impact on traceability relationships. Your task is to:

1. Analyze the changes in documentation and code files
2. Identify which existing traceability links may be affected
3. Determine what new traceability links need to be created
4. Assess the severity and scope of changes

For each change, provide:
- change_type: Type of change (added, modified, deleted, renamed)
- file_path: Path to the changed file
- change_description: Brief description of what changed
- impact_level: Severity (high, medium, low)
- affected_artifacts: List of artifact IDs that may be impacted

Return a JSON object with analysis results."""
    
    @staticmethod
    def change_analysis_human_prompt(changes: List[Dict[str, Any]], baseline_map: Dict[str, Any]) -> str:
        """Human prompt for change analysis"""
        return f"""Analyze the following repository changes and determine their impact on the existing baseline traceability map:

Repository Changes:
{json.dumps(changes, indent=2)}

Existing Baseline Map:
{json.dumps(baseline_map, indent=2)}

Analyze the changes and return impact assessment as a JSON object."""
    
    @staticmethod
    def update_strategy_system_prompt() -> str:
        """System prompt for determining update strategy"""
        return """You are an expert software architect determining the optimal strategy for updating traceability maps based on repository changes. Your task is to:

1. Analyze the impact assessment of changes
2. Determine the most efficient update strategy
3. Prioritize updates based on impact and dependencies
4. Recommend whether to do incremental updates or full recreation

For the update strategy, provide:
- strategy_type: "incremental" or "full_recreation"
- update_order: Prioritized list of updates to perform
- estimated_effort: Effort level (low, medium, high)
- risk_level: Risk of update strategy (low, medium, high)

Return a JSON object with the recommended update strategy."""
    
    @staticmethod
    def update_strategy_human_prompt(impact_assessment: Dict[str, Any]) -> str:
        """Human prompt for update strategy determination"""
        return f"""Based on the following impact assessment, determine the optimal strategy for updating the baseline traceability map:

Impact Assessment:
{json.dumps(impact_assessment, indent=2)}

Recommend an update strategy and return it as a JSON object.""" 