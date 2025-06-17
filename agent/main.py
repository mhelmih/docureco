import os
import json
import sys
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List

import requests
from dotenv import load_dotenv

# Add path for absolute imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Import Docureco components
from agent.llm import create_llm_client
from agent.workflows import create_document_update_recommendator
from agent.models import (
    PREventModel, FileChangeModel, RecommendationResponseModel,
    WorkflowStatusModel
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Main entry point for Docureco Agent"""
    logger.info("Starting Docureco Agent...")
    
    load_dotenv()

    # Get GitHub event information
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        logger.error("GITHUB_EVENT_PATH is not set or file does not exist.")
        sys.exit(1)

    with open(event_path) as f:
        event = json.load(f)
        logger.info("--- FULL GITHUB EVENT PAYLOAD ---")
        logger.info("%s", json.dumps(event, indent=2))
        logger.info("--- END GITHUB EVENT PAYLOAD ---")

    # Extract PR and repository information
    pr_info = extract_pr_info(event)
    if not pr_info:
        logger.error("Failed to extract PR information from event")
        sys.exit(1)

    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        logger.error("GITHUB_TOKEN environment variable not set. Cannot proceed.")
        sys.exit(1)

    try:
        # Fetch PR details and changed files
        pr_details = await fetch_pr_details(pr_info, github_token)
        changed_files = await fetch_changed_files(pr_info, github_token)
        
        if not changed_files:
            logger.warning("No changed files found in PR")
            return
        
        # Initialize LLM client and workflow
        llm_client = create_llm_client()
        workflow = create_document_update_recommendator(llm_client)
        
        # Execute Document Update Recommendator workflow 
        logger.info(f"Executing Document Update Recommendator workflow for PR #{pr_info['pr_number']}")
        
        # Construct PR URL for the workflow
        pr_url = f"https://github.com/{pr_info['repository']}/pull/{pr_info['pr_number']}"
        final_state = await workflow.execute(pr_url)
        
        # Process results
        if final_state.errors:
            logger.error(f"Workflow completed with errors: {final_state.errors}")
        
        # Post recommendations to PR
        if final_state.recommendations:
            await post_recommendations_to_pr(
                pr_info, 
                final_state.recommendations, 
                github_token
            )
        
        # Update CI/CD check status
        await update_check_status(pr_info, final_state, github_token)
        
        logger.info(f"Document Update Recommendator processing completed for PR #{pr_info['pr_number']}")
        
    except Exception as e:
        logger.error(f"Error during Document Update Recommendator processing: {str(e)}")
        # Update check status to failure
        await update_check_status(
            pr_info, 
            {"errors": [str(e)], "recommendations": []}, 
            github_token,
            status="failure"
        )
        sys.exit(1)

def extract_pr_info(event: Dict[str, Any]) -> Dict[str, Any]:
    """Extract PR information from GitHub event"""
    try:
        pr = event.get("pull_request", {})
        repository_info = event.get("repository", {})
        
        return {
            "pr_number": pr.get("number"),
            "repository": repository_info.get("full_name"),
            "repo_owner": repository_info.get("owner", {}).get("login"),
            "repo_name": repository_info.get("name"),
            "base_sha": pr.get("base", {}).get("sha"),
            "head_sha": pr.get("head", {}).get("sha"),
            "base_ref": pr.get("base", {}).get("ref"),
            "head_ref": pr.get("head", {}).get("ref"),
            "title": pr.get("title", ""),
            "body": pr.get("body", ""),
            "author": pr.get("user", {}).get("login", ""),
        }
    except Exception as e:
        logger.error(f"Error extracting PR info: {str(e)}")
        return {}

async def fetch_pr_details(pr_info: Dict[str, Any], github_token: str) -> Dict[str, Any]:
    """Fetch detailed PR information"""
    repository = pr_info["repository"]
    pr_number = pr_info["pr_number"]
    
    pr_url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}"
    logger.info(f"Fetching PR details from: {pr_url}")
    
    try:
        response = requests.get(
                pr_url,
            headers={
                "Authorization": f"Bearer {github_token}", 
                "Accept": "application/vnd.github.v3+json"
            }
            )
        response.raise_for_status()
        pr_data = response.json()
        
        # Fetch commit messages
        commits_url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}/commits"
        commits_response = requests.get(
            commits_url,
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        commits_response.raise_for_status()
        commits_data = commits_response.json()
        
        commit_messages = [commit["commit"]["message"] for commit in commits_data]
        
        return {
            "title": pr_data.get("title", ""),
            "body": pr_data.get("body", ""),
            "commit_messages": commit_messages,
            "commits_count": len(commits_data)
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch PR details: {e}")
    return {}

async def fetch_changed_files(pr_info: Dict[str, Any], github_token: str) -> List[FileChangeModel]:
    """Fetch list of changed files in the PR"""
    repository = pr_info["repository"]
    pr_number = pr_info["pr_number"]
    
    files_url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}/files"
    logger.info(f"Fetching changed files list from: {files_url}")
    
    try:
        response = requests.get(
                files_url,
                headers={
                "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
        response.raise_for_status()
        files_data = response.json()
        
        changed_files = []
        for file_info in files_data:
            file_change = FileChangeModel(
                filename=file_info.get("filename", ""),
                status=file_info.get("status", ""),
                additions=file_info.get("additions", 0),
                deletions=file_info.get("deletions", 0),
                patch=file_info.get("patch", ""),
                previous_filename=file_info.get("previous_filename")
            )
            changed_files.append(file_change)
        
        logger.info(f"Found {len(changed_files)} changed files")
        return changed_files
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch changed files: {e}")
        return []

async def load_baseline_map(repository: str) -> Dict[str, Any]:
    """Load baseline traceability map for repository"""
    # For now, return empty map. In full implementation, this would:
    # 1. Connect to Supabase database
    # 2. Query for existing baseline map for this repository
    # 3. Return the traceability graph data
    
    logger.info(f"Loading baseline map for repository: {repository}")
    logger.warning("Baseline map loading not implemented - returning empty map")
    
    return {
        "requirements": [],
        "design_elements": [],
        "code_components": [],
        "traceability_links": []
    }

async def post_recommendations_to_pr(
    pr_info: Dict[str, Any], 
    recommendations: List[Any], 
    github_token: str
) -> None:
    """Post recommendations as comments to the PR"""
    repository = pr_info["repository"]
    pr_number = pr_info["pr_number"]
    
    # Format recommendations into a comment
    comment_body = format_recommendations_comment(recommendations)
    
    comments_url = f"https://api.github.com/repos/{repository}/issues/{pr_number}/comments"
    
    try:
        response = requests.post(
            comments_url,
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            json={"body": comment_body}
        )
        response.raise_for_status()
        
        logger.info(f"Posted {len(recommendations)} recommendations to PR #{pr_number}")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to post recommendations: {e}")

def format_recommendations_comment(recommendations: List[Any]) -> str:
    """Format recommendations into a GitHub comment"""
    if not recommendations:
        return "## 📋 Document Update Recommendator Analysis\n\nNo documentation updates required for this PR."
    
    comment_lines = [
        "## 📋 Document Update Recommendator Recommendations",
        "",
        f"Found **{len(recommendations)}** documentation update recommendations:",
        ""
    ]
    
    for i, rec in enumerate(recommendations, 1):
        # Handle both dataclass and dict formats
        priority = getattr(rec, 'priority', rec.get('priority', 'Medium'))
        target_document = getattr(rec, 'target_document', rec.get('target_document', 'Documentation'))
        section = getattr(rec, 'section', rec.get('section', 'N/A'))
        recommendation_type = getattr(rec, 'recommendation_type', rec.get('recommendation_type', 'UPDATE'))
        what_to_update = getattr(rec, 'what_to_update', rec.get('what_to_update', 'Content needs updating'))
        why_update_needed = getattr(rec, 'why_update_needed', rec.get('why_update_needed', 'Changes detected'))
        how_to_update = getattr(rec, 'how_to_update', rec.get('how_to_update', 'Review and update content'))
        
        priority_emoji = {
            "High": "🔴",
            "Medium": "🟡", 
            "Low": "🔵",
            "Major": "🟠",
            "Fundamental": "🔴",
            "Moderate": "🟡",
            "Minor": "🔵",
            "Trivial": "⚪"
        }.get(priority, "⚪")
        
        comment_lines.extend([
            f"### {priority_emoji} Recommendation {i}: {target_document}",
            f"**Section:** {section}",
            f"**Priority:** {priority}",
            f"**Action:** {recommendation_type}",
            "",
            f"**What to update:** {what_to_update}",
            "",
            f"**Why update needed:** {why_update_needed}",
            "",
            f"**How to update:** {how_to_update}",
            "",
            "---",
            ""
        ])
    
    comment_lines.extend([
        "",
        "_Generated by Document Update Recommendator 🤖_"
    ])
    
    return "\n".join(comment_lines)

async def update_check_status(
    pr_info: Dict[str, Any], 
    workflow_state, # Can be DocumentUpdateRecommendatorState or dict for fallback
    github_token: str,
    status: str = None
) -> None:
    """Update GitHub check status"""
    repository = pr_info["repository"]
    head_sha = pr_info["head_sha"]
    
    # Determine status based on workflow results
    if status is None:
        # Handle both dataclass and dict formats
        errors = getattr(workflow_state, 'errors', None) or workflow_state.get("errors", [])
        recommendations = getattr(workflow_state, 'recommendations', None) or workflow_state.get("recommendations", [])
        
        if errors:
            status = "failure"
        elif recommendations:
            # Has recommendations - might require action
            high_priority = [
                r for r in recommendations 
                if getattr(r, 'priority', r.get('priority', '')) in ["High", "Major", "Fundamental"]
            ]
            status = "action_required" if high_priority else "success"
    else:
            status = "success"
    
    # Map internal status to GitHub status
    github_status_map = {
        "success": "success",
        "failure": "failure", 
        "action_required": "failure",  # GitHub doesn't have action_required
        "neutral": "success"
    }
    
    github_status = github_status_map.get(status, "failure")
    
    checks_url = f"https://api.github.com/repos/{repository}/check-runs"
    
    check_data = {
        "name": "Docureco Documentation Analysis",
        "head_sha": head_sha,
        "status": "completed",
        "conclusion": github_status,
        "output": {
            "title": "Document Update Recommendator Analysis Results",
            "summary": create_check_summary(workflow_state)
        }
    }
    
    try:
        response = requests.post(
            checks_url,
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.checks-preview"
            },
            json=check_data
        )
        response.raise_for_status()
        
        logger.info(f"Updated check status to: {github_status}")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to update check status: {e}")

def create_check_summary(workflow_state) -> str:
    """Create summary for GitHub check"""
    # Handle both dataclass and dict formats
    errors = getattr(workflow_state, 'errors', None) or workflow_state.get("errors", [])
    recommendations = getattr(workflow_state, 'recommendations', None) or workflow_state.get("recommendations", [])
    
    if errors:
        return f"❌ Analysis failed with {len(errors)} errors"
    
    if not recommendations:
        return "✅ No documentation updates required"
    
    high_priority = [
        r for r in recommendations 
        if getattr(r, 'priority', r.get('priority', '')) in ["High", "Major", "Fundamental"]
    ]
    
    if high_priority:
        return f"⚠️ {len(recommendations)} recommendations found ({len(high_priority)} high priority)"
    else:
        return f"📝 {len(recommendations)} minor recommendations found"

def run_async_main():
    """Wrapper to run async main function"""
    asyncio.run(main())

if __name__ == "__main__":
    run_async_main()
