"""
Document Update Recommender Workflow for Docureco Agent
Main LangGraph workflow that analyzes GitHub PR code changes and recommends documentation updates
Implements the Document Update Recommender component from the system architecture
"""

import asyncio
import logging
import re
import sys
import os
import httpx
import subprocess
import tempfile
import fnmatch
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser

# Add parent directories to path for absolute imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.extend([current_dir, parent_dir, root_dir])

# LangGraph imports
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Agent imports
from agent.llm.llm_client import LLMClient
from agent.models.docureco_models import (
    BaselineMapModel,
    DocumentationRecommendationModel,
    RecommendationType,
    RecommendationStatus
)
from agent.database import create_baseline_map_repository
from agent.document_update_recommender.prompts import DocumentUpdateRecommenderPrompts as prompts

logger = logging.getLogger(__name__)

# Structured output models
class CodeChangeClassification(BaseModel):
    """Structured output for individual code change classification"""
    filename: str = Field(description="Path to the changed file")
    type: str = Field(description="Type of change (Addition, Deletion, Modification, Rename)")
    scope: str = Field(description="Scope of change (Function/Method, Class, Module, etc.)")
    nature: str = Field(description="Nature of change (New Feature, Bug Fix, Refactoring, etc.)")
    volume: str = Field(description="Volume of change (Trivial, Small, Medium, Large, Very Large)")
    reasoning: str = Field(description="Brief explanation of the classification")

class BatchClassificationOutput(BaseModel):
    """Structured output for batch classification of all changed files"""
    classifications: List[CodeChangeClassification] = Field(description="List of classified code changes")

class LogicalChangeSet(BaseModel):
    """Structured output for logical change sets"""
    name: str = Field(description="Descriptive name for the change set")
    description: str = Field(description="Brief description of what this change set accomplishes")
    change_indices: List[int] = Field(description="Indices of changes in this set (1-based)")
    primary_nature: str = Field(description="Primary nature of changes in this set")
    estimated_impact: str = Field(description="Estimated impact level (Low/Medium/High)")

class ChangeGroupingOutput(BaseModel):
    """Structured output for grouping changes into logical change sets"""
    change_sets: List[LogicalChangeSet] = Field(description="List of logical change sets")

class DocumentationRecommendation(BaseModel):
    """Structured output for documentation recommendations"""
    target_document: str = Field(description="Document that needs updating")
    section: str = Field(description="Specific section or location")
    recommendation_type: str = Field(description="Type of update (UPDATE, CREATE, DELETE, REVIEW)")
    priority: str = Field(description="Priority level (HIGH, MEDIUM, LOW)")
    what_to_update: str = Field(description="What needs to be changed")
    where_to_update: str = Field(description="Exact location or section reference")
    why_update_needed: str = Field(description="Rationale based on code changes")
    how_to_update: str = Field(description="Step-by-step guidance")
    suggested_content: str = Field(default="", description="Specific content suggestions")

class RecommendationGenerationOutput(BaseModel):
    """Structured output for recommendation generation"""
    recommendations: List[DocumentationRecommendation] = Field(description="List of generated recommendations")

@dataclass
class DocumentUpdateRecommenderState:
    """State for the Document Update Recommender workflow"""
    repository: str
    pr_number: int
    branch: str
    
    # Step 1: Scan PR - PR Event Data and Context
    pr_event_data: Dict[str, Any] = field(default_factory=dict)
    requested_repo_content: Dict[str, Any] = field(default_factory=dict)
    commit_info: Dict[str, Any] = field(default_factory=dict)
    changed_files_list: List[str] = field(default_factory=list)
    
    # Step 2: Analyze Code Changes - Classification and Grouping
    classified_changes: List[Dict[str, Any]] = field(default_factory=list)
    logical_change_sets: List[Dict[str, Any]] = field(default_factory=list)
    
    # Step 3: Assess Documentation Impact - Traceability and Impact Analysis
    baseline_map: Optional[BaselineMapModel] = None
    traceability_map: Dict[str, Any] = field(default_factory=dict)
    potentially_impacted_elements: List[Dict[str, Any]] = field(default_factory=list)
    prioritized_finding_list: List[Dict[str, Any]] = field(default_factory=list)
    
    # Step 4: Generate and Post Recommendations - Suggestion Generation
    filtered_high_priority_findings: List[Dict[str, Any]] = field(default_factory=list)
    existing_suggestions: List[Dict[str, Any]] = field(default_factory=list)
    generated_suggestions: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[DocumentationRecommendationModel] = field(default_factory=list)
    
    # Workflow metadata
    errors: List[str] = field(default_factory=list)
    processing_stats: Dict[str, int] = field(default_factory=dict)

class DocumentUpdateRecommenderWorkflow:
    """
    Main LangGraph workflow for analyzing GitHub PR code changes and recommending documentation updates.
    
    This workflow implements the Document Update Recommender component following the 5-step process:
    1. Scan PR - Scan PR event data and repo context
    2. Analyze Code Changes - Code change classification, grouping, and contextualization
    3. Assess Documentation Impact - Determine traceability status, impact tracing, and prioritization
    4. Generate and Post Recommendations - Filter findings, generate suggestions, and manage status
    5. End - Complete workflow
    """
    
    def __init__(self, 
                 llm_client: Optional[LLMClient] = None,
                 baseline_map_repo = None):
        """
        Initialize Document Update Recommender workflow
        
        Args:
            llm_client: Optional LLM client for analysis and recommendations
            baseline_map_repo: Optional repository for baseline map operations
        """
        self.llm_client = llm_client or LLMClient()
        self.baseline_map_repo = baseline_map_repo or create_baseline_map_repository()
        
        self.workflow = self._build_workflow()
        self.memory = MemorySaver()
        
        logger.info("Initialized DocumentUpdateRecommenderWorkflow")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow with conditional logic"""
        workflow = StateGraph(DocumentUpdateRecommenderState)
        
        # Add nodes for each step of the 5-step process
        workflow.add_node("scan_pr", self._scan_pr)
        # workflow.add_node("analyze_code_changes", self._analyze_code_changes)
        # workflow.add_node("assess_documentation_impact", self._assess_documentation_impact)
        # workflow.add_node("generate_and_post_recommendations", self._generate_and_post_recommendations)
        
        # Define workflow edges following the exact sequence
        workflow.set_entry_point("scan_pr")
        workflow.add_edge("scan_pr", END)
        # workflow.add_edge("scan_pr", "analyze_code_changes")
        # workflow.add_edge("analyze_code_changes", "assess_documentation_impact")
        # workflow.add_edge("assess_documentation_impact", "generate_and_post_recommendations")
        # workflow.add_edge("generate_and_post_recommendations", END)
        
        return workflow
    
    async def execute(self, pr_url: str) -> DocumentUpdateRecommenderState:
        """
        Execute the Document Update Recommender workflow for PR analysis
        
        Args:
            pr_url: GitHub PR URL to analyze
            
        Returns:
            DocumentUpdateRecommenderState: Final state with recommendations
        """
        # Initialize state with PR information
        pr_info = await self._parse_pr_url(pr_url)
        initial_state = DocumentUpdateRecommenderState(
            repository=pr_info["repository"],
            pr_number=pr_info["pr_number"],
            branch=pr_info["branch"]
        )
        
        try:
            # Compile and run workflow
            app = self.workflow.compile(checkpointer=self.memory)
            config = {"configurable": {"thread_id": f"pr_{pr_info['repository'].replace('/', '_')}_{pr_info['pr_number']}"}}
            
            final_state = await app.ainvoke(initial_state, config=config)
            
            logger.info(f"Document Update Recommender completed for PR {pr_info['repository']}#{pr_info['pr_number']}")
            return final_state
            
        except Exception as e:
            logger.error(f"Document Update Recommender failed: {str(e)}")
            initial_state.errors.append(str(e))
            raise
    
    async def _scan_pr(self, state: DocumentUpdateRecommenderState) -> DocumentUpdateRecommenderState:
        """
        Step 1: Scan PR and Repository Context
        
        Implements:
        - PR Event Data scanning
        - Requested Repository Content retrieval
        - Commit Information gathering
        - Changed Files List compilation
        """
        logger.info(f"Step 1: Scanning PR #{state.pr_number} and repository context")
        
        try:
            # Scan PR event data
            pr_event_data = await self._fetch_pr_event_data(state.repository, state.pr_number)
            state.pr_event_data = pr_event_data
            
            # Get requested repository content
            repo_content = await self._fetch_repo_content(state.repository, state.branch)
            state.requested_repo_content = repo_content
            
            commits_len = len(state.pr_event_data["commits"])
            files_changed = sum(len(commit.get("files", [])) for commit in state.pr_event_data["commits"])
            additions = sum(commit.get("additions", 0) for commit in state.pr_event_data["commits"])
            deletions = sum(commit.get("deletions", 0) for commit in state.pr_event_data["commits"])
            
            # Update processing statistics
            state.processing_stats.update({
                "pr_commits": commits_len,
                "pr_files_changed": files_changed,
                "pr_additions": additions,
                "pr_deletions": deletions
            })
            
            print("PR EVENT DATA", state.pr_event_data)
            print("REPO CONTENT", state.requested_repo_content)
            
            logger.info(f"Scanned PR with {commits_len} commits, {files_changed} files changed, {additions} additions, {deletions} deletions")
                
        except Exception as e:
            error_msg = f"Error scanning PR: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _analyze_code_changes(self, state: DocumentUpdateRecommenderState) -> DocumentUpdateRecommenderState:
        """
        Analyze code changes from PR event data and classify them.
        
        This workflow step:
        1. Classifies individual code changes using enhanced per-commit analysis
        2. Groups classified changes into logical change sets using commit semantics
        3. Handles multi-purpose files correctly by analyzing each commit separately
        
        Args:
            state: Current workflow state containing PR event data
            
        Returns:
            Updated state with classified changes and logical change sets
        """
        try:
            if not state.pr_event_data:
                logger.warning("No PR event data available for code change analysis")
                state.classified_changes = []
                state.logical_change_sets = []
                return state
                
            logger.info("Starting enhanced per-commit code change analysis")
            
            # Step 1: Classify individual changes using enhanced per-commit analysis
            classified_changes = await self._llm_classify_individual_changes(state.pr_event_data)
            
            # Step 2: Group classified changes into logical change sets
            logical_change_sets = await self._llm_group_classified_changes(
                classified_changes,
                state.pr_event_data.get("commit_info", {})
            )
            
            # Update state
            state.classified_changes = classified_changes
            state.logical_change_sets = logical_change_sets
            
            logger.info(f"Successfully analyzed {len(classified_changes)} classified changes into {len(logical_change_sets)} logical change sets")
                
        except Exception as e:
            logger.error(f"Error in code change analysis: {str(e)}")
            # Set fallback empty data
            state.classified_changes = []
            state.logical_change_sets = []
        
        return state
    
    async def _assess_documentation_impact(self, state: DocumentUpdateRecommenderState) -> DocumentUpdateRecommenderState:
        """
        Step 3: Assess Documentation Impact
        
        Implements:
        - Determine Traceability Status
        - Impact Tracing through Map
        - Combine Findings
        - Assess Likelihood and Severity
        """
        logger.info("Step 3: Assessing documentation impact using traceability analysis")
        
        try:
            # 3.1 Determine Traceability Status
            baseline_map_data = await self.baseline_map_repo.get_baseline_map(state.repository, state.branch)
            if not baseline_map_data:
                return state    # Terminate workflow if no baseline map is found
                
            traceability_status = await self._determine_traceability_status(
                state.logical_change_sets,
                state.repository,
                state.branch,
                baseline_map_data
            )
            
            # 3.2 Trace Impact Through Map
            # Get changes with traceability status modification, outdated, rename
            changes_modification_outdated_rename = []
            changes_gap_anomaly = []
            for change in state.logical_change_sets:
                status = change.get("traceability_status")
                if status == "modification" or status == "outdated" or status == "rename":
                    changes_modification_outdated_rename.append(change)
                elif status == "gap" or status == "anomaly":
                    changes_gap_anomaly.append(change)
                    
            # Get potentially impacted elements
            potentially_impacted_elements = await self._trace_impact_through_map(
                changes_modification_outdated_rename,
                state.traceability_map
            )
            state.potentially_impacted_elements = potentially_impacted_elements
            
            # 3.3 Combine Findings
            findings = potentially_impacted_elements + changes_gap_anomaly
            
            # 3.4 Assess Likelihood and Severity
            prioritized_findings = await self._llm_assess_likelihood_and_severity(
                findings,
                state.logical_change_sets
            )
            state.prioritized_finding_list = prioritized_findings
            
            # Update processing statistics
            state.processing_stats.update({
                "potentially_impacted_elements": len(potentially_impacted_elements),
                "prioritized_findings": len(prioritized_findings)
            })
            
            logger.info(f"Identified {len(potentially_impacted_elements)} potentially impacted elements")
            
        except Exception as e:
            error_msg = f"Error assessing documentation impact: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _generate_and_post_recommendations(self, state: DocumentUpdateRecommenderState) -> DocumentUpdateRecommenderState:
        """
        Step 4: Generate and Post Recommendations
        
        Implements:
        - Filter High-Priority Findings
        - Query Existing Suggestions
        - Findings Iteration & Suggestion Generation
        - Filter Against Existing & Post Details
        - Manage Check Status
        """
        logger.info("Step 4: Generating and posting documentation recommendations")
        
        try:
            # 4.1 Filter High-Priority Findings
            filtered_findings = await self._filter_high_priority_findings(
                state.prioritized_finding_list
            )
            state.filtered_high_priority_findings = filtered_findings
            
            # 4.2 Query Existing Suggestions
            existing_suggestions = await self._query_existing_suggestions(
                state.repository,
                state.pr_number
            )
            state.existing_suggestions = existing_suggestions
            
            # 4.3 Fetch Current Documentation Context
            current_docs = await self._fetch_current_documentation(
                state.requested_repo_content,
                filtered_findings
            )
            
            # 4.4 Findings Iteration & Suggestion Generation
            generated_suggestions = await self._llm_generate_suggestions(
                filtered_findings,
                current_docs,
                state.logical_change_sets
            )
            state.generated_suggestions = generated_suggestions
            
            # 4.5 Filter Against Existing & Post Details
            final_recommendations = await self._llm_filter_and_post_suggestions(
                generated_suggestions,
                existing_suggestions,
                state.repository,
                state.pr_number
            )
            state.recommendations = final_recommendations
            
            # Update processing statistics
            state.processing_stats.update({
                "high_priority_findings": len(filtered_findings),
                "existing_suggestions": len(existing_suggestions),
                "generated_suggestions": len(generated_suggestions),
                "final_recommendations": len(final_recommendations)
            })
            
            logger.info(f"Generated {len(final_recommendations)} final recommendations")
            
        except Exception as e:
            error_msg = f"Error generating recommendations: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    async def _parse_pr_url(self, pr_url: str) -> Dict[str, Any]:
        """Parse GitHub PR URL to extract repository and PR details"""
        
        # Parse the PR URL using regex
        # Supports formats like:
        # https://github.com/owner/repo/pull/123
        # https://github.com/owner/repo/pull/123#issuecomment-123456
        # https://github.com/owner/repo/pull/123/files
        pattern = r'https://github\.com/([^/]+)/([^/]+)/pull/(\d+)'
        match = re.match(pattern, pr_url)
        
        if not match:
            raise ValueError(f"Invalid GitHub PR URL format: {pr_url}")
        
        owner, repo, pr_number = match.groups()
        repository = f"{owner}/{repo}"
        pr_number = int(pr_number)
        
        # Get branch information from GitHub API
        github_token = os.getenv("GITHUB_TOKEN")
        if not github_token:
            logger.warning("GITHUB_TOKEN not found, using default branch 'main'")
            return {
                "repository": repository,
                "pr_number": pr_number,
                "branch": "main"
            }
        
        try:
            # Make API call to get PR details
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"token {github_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
                
                response = await client.get(
                    f"https://api.github.com/repos/{repository}/pulls/{pr_number}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    pr_data = response.json()
                    branch = pr_data.get("base", {}).get("ref", "main")
                    
                    return {
                        "repository": repository,
                        "pr_number": pr_number,
                        "branch": branch
                    }
                else:
                    logger.warning(f"Failed to fetch PR details from GitHub API: {response.status_code}")
                    return {
                        "repository": repository,
                        "pr_number": pr_number,
                        "branch": "main"
                    }
            
        except Exception as e:
            logger.warning(f"Error fetching PR details: {str(e)}, using default branch 'main'")
        return {
                "repository": repository,
                "pr_number": pr_number,
            "branch": "main"
        }
    
    async def _fetch_pr_event_data(self, repository: str, pr_number: int) -> Dict[str, Any]:
        """Fetch PR event data from GitHub REST API with per-commit file changes"""
        github_token = os.getenv("GITHUB_TOKEN")
        if not github_token:
            logger.warning("GITHUB_TOKEN not found, using placeholder data")
            return self._get_placeholder_pr_data()
        
        try:
            # Parse repository owner and name
            owner, repo_name = repository.split("/")
            
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
                
            # Step 1: Get PR details and commits
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Get PR details
                pr_response = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{pr_number}",
                    headers=headers
                )
                pr_response.raise_for_status()
                pr_data = pr_response.json()
                
                # Get commits for this PR
                commits_response = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{pr_number}/commits",
                    headers=headers
                )
                commits_response.raise_for_status()
                commits_data = commits_response.json()
                
                # Step 2: Get file changes for each commit (N+1 approach)
                enhanced_commits = []
                logger.info(f"Fetching file changes for {len(commits_data)} commits")
                
                # Process commits with controlled concurrency
                semaphore = asyncio.Semaphore(5)  # Limit concurrent requests
                
                async def fetch_commit_files(commit_data):
                    async with semaphore:
                        try:
                            commit_sha = commit_data["sha"]
                            commit_response = await client.get(
                                f"https://api.github.com/repos/{owner}/{repo_name}/commits/{commit_sha}",
                                headers=headers
                            )
                            commit_response.raise_for_status()
                            commit_details = commit_response.json()
                            
                            # Extract file changes
                            files = commit_details.get("files", [])
                            
                            # Structure commit data with files
                            enhanced_commit = {
                                "sha": commit_data["sha"],
                                "message": commit_data["commit"]["message"],
                                "author": {
                                    "name": commit_data["commit"]["author"]["name"],
                                    "date": commit_data["commit"]["author"]["date"]
                                },
                                "additions": commit_details.get("stats", {}).get("additions", 0),
                                "deletions": commit_details.get("stats", {}).get("deletions", 0),
                                "total_changes": commit_details.get("stats", {}).get("total", 0),
                                "files": []
                            }
                            
                            # Process each file
                            for file_data in files:
                                file_info = {
                                    "filename": file_data.get("filename", ""),
                                    "status": file_data.get("status", ""),
                                    "additions": file_data.get("additions", 0),
                                    "deletions": file_data.get("deletions", 0),
                                    "changes": file_data.get("changes", 0),
                                    "patch": file_data.get("patch", ""),
                                    "blob_url": file_data.get("blob_url", ""),
                                    "raw_url": file_data.get("raw_url", "")
                                }
                                enhanced_commit["files"].append(file_info)
                
                            return enhanced_commit
                            
                        except Exception as e:
                            logger.error(f"Error fetching commit {commit_data['sha']}: {str(e)}")
                            # Return minimal commit data if file fetch fails
                            return {
                                    "sha": commit_data["sha"],
                                    "message": commit_data["commit"]["message"],
                                    "author": {
                                        "name": commit_data["commit"]["author"]["name"],
                                        "date": commit_data["commit"]["author"]["date"]
                                    },
                                    "additions": 0,
                                    "deletions": 0,
                                    "total_changes": 0,
                                    "files": []
                                }
                
                # Fetch all commit files concurrently
                enhanced_commits = await asyncio.gather(
                    *[fetch_commit_files(commit) for commit in commits_data]
                )
                
                # Structure the data according to expected format
                structured_data = {
                    "action": "opened",
                    "number": pr_number,
                    "pull_request": {
                        "title": pr_data.get("title", ""),
                        "body": pr_data.get("body", ""),
                        "user": {
                            "login": pr_data.get("user", {}).get("login", "")
                        },
                        "base": {
                            "ref": pr_data.get("base", {}).get("ref", "")
                        },
                        "head": {
                            "ref": pr_data.get("head", {}).get("ref", "")
                        }
                    },
                    "repository": {
                        "name": repo_name,
                        "full_name": repository
                    },
                    # Enhanced commit info with per-commit file details
                    "commit_info": {
                        "commits": enhanced_commits,
                        "count": len(enhanced_commits)
                    }
                }
                
                logger.info(f"Successfully fetched PR data with {len(enhanced_commits)} commits and detailed file changes")
                return structured_data
                
        except Exception as e:
            logger.error(f"Error fetching PR event data: {str(e)}")
            return self._get_placeholder_pr_data()

    def _get_placeholder_pr_data(self) -> Dict[str, Any]:
        """Get placeholder PR data for development/testing"""
        return {
            "commit_info": {
            "commits": [
                {
                    "sha": "abc123",
                    "message": "Fix auth timeout bug",
                    "author": "Developer",
                    "date": "2024-01-01T00:00:00Z",
                    "additions": 5,
                    "deletions": 2,
                    "changed_files_count": 1,
                    "files": [
                        {
                            "path": "src/auth/service.py",
                            "status": "modified",
                            "additions": 5,
                            "deletions": 2,
                            "changes": 7,
                            "patch": "- setTimeout(5000)\n+ setTimeout(30000)"
                        }
                    ]
                },
                {
                    "sha": "def456",
                    "message": "Add OAuth 2.0 support",
                    "author": "Developer",
                    "date": "2024-01-02T00:00:00Z",
                    "additions": 45,
                    "deletions": 0,
                    "changed_files_count": 2,
                    "files": [
                        {
                            "path": "src/auth/service.py",
                            "status": "modified",
                            "additions": 40,
                            "deletions": 0,
                            "changes": 40,
                            "patch": "+ class OAuthHandler:\n+   def __init__(self):"
                        },
                        {
                            "path": "src/auth/oauth.py",
                            "status": "added",
                            "additions": 5,
                            "deletions": 0,
                            "changes": 5,
                            "patch": "+ def oauth_login():\n+   pass"
                        }
                    ]
                }
                ],
                "additions": 50,
                "deletions": 2,
                "total_commits": 2,
                "total_files_changed": 2
            },
            "pr_details": {
                "title": "Add OAuth 2.0 support and fix auth timeout",
                "body": "This PR adds OAuth 2.0 support and fixes the auth timeout bug.",
                "state": "open",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "head": {"ref": "feature/oauth", "sha": "def456"},
                "base": {"ref": "main", "sha": "xyz789"}
            },
            "fetch_method": "placeholder"
        }
    
    async def _fetch_repo_content(self, repository: str, branch: str) -> Dict[str, Any]:
        """Fetch repository content using Repomix for comprehensive analysis"""
        
        logger.info(f"Fetching repository content using Repomix for {repository}:{branch}")
        
        try:
            # Check if Repomix is available
            try:
                subprocess.run(["repomix", "--version"], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.warning("Repomix not available, falling back to placeholder content")
                logger.info("To install Repomix: npm install -g repomix")
                logger.info("Repomix provides faster and more comprehensive repository scanning")
                return {"repo_name": repository, "branch": branch, "content": {"README.md": "Project Overview", "docs/": "Documentation"}}
            
            # Use Repomix to scan the repository
            repo_data = await self._scan_repository_with_repomix(repository, branch)
            
            # Categorize files by type
            documentation_files = []
            source_files = []
            config_files = []
            other_files = []
            documentation_content = {}
            
            doc_extensions = {'.md', '.rst', '.txt', '.doc', '.docx', '.pdf'}
            source_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.cs', '.go', '.rs', '.php', '.rb', '.scala', '.kt', '.swift'}
            config_extensions = {'.json', '.yaml', '.yml', '.xml', '.ini', '.cfg', '.conf', '.toml', '.properties'}
            
            for file_info in repo_data.get("files", []):
                file_path = file_info.get("path", "")
                file_content = file_info.get("content", "")
                file_name = os.path.basename(file_path)
                file_ext = os.path.splitext(file_name)[1].lower()
                
                file_metadata = {
                    "path": file_path,
                    "name": file_name,
                    "size": len(file_content),
                    "has_content": bool(file_content.strip())
                }
                
                # Categorize documentation files
                if (file_ext in doc_extensions or 
                    'readme' in file_name.lower() or 
                    'doc' in file_path.lower() or
                    'documentation' in file_path.lower() or
                    file_path.startswith('docs/')):
                    documentation_files.append(file_metadata)
                    
                    # Store content for key documentation files
                    if ('readme' in file_name.lower() or 
                        file_path.startswith('docs/') or
                        'srs' in file_name.lower() or
                        'sdd' in file_name.lower() or
                        'requirements' in file_name.lower() or
                        'design' in file_name.lower()):
                        documentation_content[file_path] = file_content[:]
                
                # Categorize source files
                elif file_ext in source_extensions:
                    source_files.append(file_metadata)
                
                # Categorize configuration files
                elif file_ext in config_extensions or file_name.lower() in ['dockerfile', 'makefile', 'rakefile', 'gemfile']:
                    config_files.append(file_metadata)
                
                else:
                    other_files.append(file_metadata)
            
            # Structure the repository content
            repo_content = {
                "repo_name": repository,
                "branch": branch,
                "file_structure": {
                    "documentation_files": documentation_files,
                    "source_files": source_files,
                    "config_files": config_files,
                    "other_files": other_files,
                    "total_files": len(documentation_files) + len(source_files) + len(config_files) + len(other_files)
                },
                "documentation_content": documentation_content,
                "statistics": {
                    "documentation_files_count": len(documentation_files),
                    "source_files_count": len(source_files),
                    "config_files_count": len(config_files),
                    "other_files_count": len(other_files),
                    "documentation_with_content_count": len(documentation_content)
                },
                "scan_method": "repomix"
            }
            
            logger.info(f"Successfully scanned repository with Repomix:")
            logger.info(f"  - Documentation files: {len(documentation_files)} ({len(documentation_content)} with content)")
            logger.info(f"  - Source files: {len(source_files)}")
            logger.info(f"  - Config files: {len(config_files)}")
            logger.info(f"  - Other files: {len(other_files)}")
            
            return repo_content
            
        except Exception as e:
            logger.error(f"Error fetching repository content with Repomix: {str(e)}")
            # Return fallback content on error
            return {
                "repo_name": repository,
                "branch": branch,
                "error": str(e),
                "content": {"error": f"Failed to fetch repository content: {str(e)}"},
                "scan_method": "fallback"
            }
    
    async def _scan_repository_with_repomix(self, repository: str, branch: str) -> Dict[str, Any]:
        """
        Scan repository using Repomix (borrowed from Baseline Map Creator)
        
        Args:
            repository: Repository URL or path (owner/repo format)
            branch: Branch name
            
        Returns:
            Dict containing repository structure and file contents
        """
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, "repo_scan.xml")
            
            # Convert repository format to URL if needed
            if "/" in repository and not repository.startswith("http"):
                repo_url = f"https://github.com/{repository}.git"
            else:
                repo_url = repository
            
            try:
                # Run Repomix to scan the repository
                cmd = [
                    "repomix",
                    "--remote", repo_url,
                    "--remote-branch", branch,
                    "--output", output_file,
                    "--style", "xml",
                    "--ignore", "node_modules,__pycache__,.git,.venv,venv,env,target,build,dist,.next,coverage,.github,.vscode,.env,.env.local,.env.development.local,.env.test.local,.env.production.local"
                ]
                
                logger.debug(f"Running Repomix: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode != 0:
                    raise RuntimeError(f"Repomix failed: {result.stderr}")
                
                # Read and parse the XML output file
                with open(output_file, 'r', encoding='utf-8') as f:
                    xml_content = f.read()
                
                repo_data = self._parse_repomix_xml(xml_content)
                
                logger.debug(f"Repomix scan completed successfully for {repository}:{branch}")
                return repo_data
                
            except subprocess.TimeoutExpired:
                raise RuntimeError("Repomix scan timed out after 5 minutes")
            except Exception as e:
                raise RuntimeError(f"Failed to scan repository with Repomix: {str(e)}")
    
    def _parse_repomix_xml(self, xml_content: str) -> Dict[str, Any]:
        """
        Parse Repomix XML-like output into structured data (borrowed from Baseline Map Creator)
        
        Args:
            xml_content: Raw content from Repomix (not valid XML, but uses XML-like tags)
            
        Returns:
            Dict with files structure compatible with existing code
        """
        files = []
        
        try:
            # Repomix uses <file path="..."> tags but it's not valid XML
            # We need to parse it manually using regex/string parsing
            
            # Find all <file path="..."> sections
            
            # Pattern to match <file path="..."> and capture path and content
            file_pattern = r'<file path="([^"]*)">\s*(.*?)\s*</file>'
            
            matches = re.findall(file_pattern, xml_content, re.DOTALL)
            
            for file_path, file_content in matches:
                if file_path and file_content.strip():
                    files.append({
                        "path": file_path,
                        "content": file_content.strip()
                    })
            
            if not matches:
                # Try alternative approach: split by <file path=" and parse manually
                sections = xml_content.split('<file path="')
                
                for i, section in enumerate(sections):
                    if i == 0:  # Skip the first section (header/metadata)
                        continue
                        
                    # Extract file path from the opening tag
                    if '">' not in section:
                        continue
                        
                    path_end = section.find('">')
                    if path_end == -1:
                        continue
                        
                    file_path = section[:path_end]
                    
                    # Extract content until the closing </file> tag
                    content_start = path_end + 2  # Skip ">
                    
                    # Find the closing tag
                    closing_tag = '</file>'
                    content_end = section.find(closing_tag)
                    
                    if content_end == -1:
                        # If no closing tag, take everything until next <file or end
                        next_file = section.find('<file path="', content_start)
                        if next_file != -1:
                            file_content = section[content_start:next_file].strip()
                        else:
                            file_content = section[content_start:].strip()
                    else:
                        file_content = section[content_start:content_end].strip()
                    
                    if file_path and file_content:
                        files.append({
                            "path": file_path,
                            "content": file_content
                        })

            return {"files": files}
                
        except Exception as e:
            logger.warning(f"Repomix XML parsing failed ({e}), attempting fallback parsing")
            return self._parse_repomix_fallback(xml_content)
    
    def _parse_repomix_fallback(self, content: str) -> Dict[str, Any]:
        """
        Fallback parser for Repomix Markdown-style output (borrowed from Baseline Map Creator)
        
        Args:
            content: Raw content from Repomix
            
        Returns:
            Dict with files structure
        """
        files = []
        lines = content.split('\n')
        current_file = None
        current_content = []
        in_code_block = False
        
        for i, line in enumerate(lines):
            # Look for file headers: ## path/to/file (must contain a file extension or be in recognizable directory)
            if line.startswith('## '):
                if '/' in line or '.' in line:
                    # Save previous file if exists
                    if current_file and current_content:
                        file_content = '\n'.join(current_content).strip()
                        if file_content:  # Only add if there's actual content
                            files.append({
                                "path": current_file,
                                "content": file_content
                            })
                    
                    # Extract file path (remove ## prefix and clean up)
                    potential_file = line[3:].strip()
                    
                    # Filter out non-file headers - files should have extensions or be in directories
                    if ('.' in potential_file or '/' in potential_file) and not potential_file.endswith(':'):
                        current_file = potential_file
                        current_content = []
                        in_code_block = False
                
            elif current_file:
                # Handle code blocks
                if line.startswith('```'):
                    if not in_code_block:
                        # Starting code block
                        in_code_block = True
                    else:
                        # Ending code block
                        in_code_block = False
                    continue
                elif in_code_block:
                    current_content.append(line)
        
        # Save last file
        if current_file and current_content:
            file_content = '\n'.join(current_content).strip()
            if file_content:
                files.append({
                    "path": current_file,
                    "content": file_content
                })
            
        return {"files": files}
    
    async def _llm_classify_individual_changes(self, pr_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Classify individual code changes using enhanced per-commit file analysis with structured output.
        
        This method leverages the enhanced per-commit data structure to analyze each commit's file changes
        separately, then intelligently aggregates them to handle multi-purpose files correctly.
        
        Args:
            pr_data: Enhanced PR event data containing per-commit file changes
            
        Returns:
            List of classified changes with proper multi-purpose handling
        """
        try:
            # Get enhanced commit data with per-commit file changes
            commits = pr_data.get("commit_info", {}).get("commits", [])
            
            if not commits:
                logger.warning("No commits found in PR data")
                return []
            
            logger.info(f"Processing {len(commits)} commits for classification")
            
            # Strategy: Classify each commit's changes separately, then aggregate
            all_classifications = []
            
            for commit in commits:
                commit_sha = commit.get("sha", "")
                commit_message = commit.get("message", "")
                commit_files = commit.get("files", [])
                
                if not commit_files:
                    logger.warning(f"No files found for commit {commit_sha}")
                    continue
                
                # Classify changes for this specific commit
                try:
                    # Build single commit classification prompt
                    system_prompt = prompts.single_commit_classification_system_prompt()
                    human_prompt = prompts.single_commit_classification_human_prompt(
                        commit_sha, commit_message, commit_files
                    )
                    
                    # Use structured output parsing
                    parser = JsonOutputParser(pydantic_object=prompts.SingleCommitClassificationOutput)
                    
                    # Get LLM classification
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "human", "content": human_prompt}
                    ]
                    
                    classification_response = await self.llm_client.generate_response(
                        messages=messages,
                        temperature=0.1,
                        response_format={"type": "json_object"}
                    )
                    
                    # Parse the structured response
                    parsed_response = parser.parse(classification_response.content)
                    
                    # Add commit context to each classification
                    for classification in parsed_response.get("classifications", []):
                        classification["commit_sha"] = commit_sha
                        classification["commit_message"] = commit_message
                        classification["commit_author"] = commit.get("author", {}).get("name", "")
                        classification["commit_date"] = commit.get("author", {}).get("date", "")
                        all_classifications.append(classification)
                    
                    logger.info(f"Successfully classified {len(parsed_response.get('classifications', []))} files for commit {commit_sha}")
                        
                except Exception as e:
                    logger.error(f"Error classifying commit {commit_sha}: {str(e)}")
                    # Create fallback classifications for this commit
                    fallback_classifications = self._create_fallback_commit_classifications(
                        commit_files, commit_message
                    )
                    for classification in fallback_classifications:
                        classification["commit_sha"] = commit_sha
                        classification["commit_message"] = commit_message
                        classification["commit_author"] = commit.get("author", {}).get("name", "")
                        classification["commit_date"] = commit.get("author", {}).get("date", "")
                        all_classifications.append(classification)
                    
                    logger.info(f"Used fallback classification for commit {commit_sha}")
            
            # Aggregate classifications for files that appear in multiple commits
            aggregated_classifications = self._aggregate_multi_commit_classifications(all_classifications)
            
            logger.info(f"Successfully classified {len(aggregated_classifications)} unique files across {len(commits)} commits")
            return aggregated_classifications
            
        except Exception as e:
            logger.error(f"Error in per-commit classification: {str(e)}")
            # Create simple fallback for all commits
            fallback_classifications = []
            commits = pr_data.get("commit_info", {}).get("commits", [])
            
            for commit in commits:
                commit_files = commit.get("files", [])
                commit_message = commit.get("message", "")
                
                for file_data in commit_files:
                    classification = self._create_fallback_classification(
                        file_data.get("filename", ""),
                        file_data.get("status", "modified"),
                        file_data.get("additions", 0),
                        file_data.get("deletions", 0),
                        file_data.get("changes", 0),
                        commit_message
                    )
                    classification["commit_sha"] = commit.get("sha", "")
                    classification["commit_message"] = commit_message
                    fallback_classifications.append(classification)
            
            return fallback_classifications
    
    async def _classify_commit_changes(self, commit_files: List[Dict[str, Any]], 
                                     commit_message: str, commit_sha: str, 
                                     commit_author: str, commit_date: str) -> Dict[str, Any]:
        """
        Classify file changes for a single commit using LLM with focused context.
        
        Args:
            commit_files: List of files changed in this commit
            commit_message: Commit message for context
            commit_sha: Commit SHA
            commit_author: Commit author
            commit_date: Commit date
            
        Returns:
            Dict containing commit metadata and classified file changes
        """
        try:
            if not commit_files:
                return {
                    "commit_sha": commit_sha,
                    "commit_message": commit_message,
                    "commit_author": commit_author,
                    "commit_date": commit_date,
                    "classified_files": []
                }
            
            # Prepare commit-specific context
            commit_context = {
                "message": commit_message,
                "sha": commit_sha,
                "author": commit_author,
                "date": commit_date,
                "files_count": len(commit_files)
            }
            
            # Format files for LLM prompt
            formatted_files = []
            for file_data in commit_files:
                formatted_files.append({
                    "filename": file_data.get("path", ""),
                    "status": file_data.get("status", "modified"),
                    "additions": file_data.get("additions", 0),
                    "deletions": file_data.get("deletions", 0),
                    "changes": file_data.get("changes", 0),
                    "patch": file_data.get("patch", "")[:500]  # Truncate for efficiency
                })
            
            # Use enhanced prompts for single-commit classification
            system_message = prompts.single_commit_classification_system_prompt()
            human_prompt = prompts.single_commit_classification_human_prompt(formatted_files, commit_context)
            
            # Create output parser for JSON format
            output_parser = JsonOutputParser(pydantic_object=BatchClassificationOutput)
            
            # Generate JSON response
            response = await self.llm_client.generate_response(
                prompt=human_prompt,
                system_message=system_message + "\n" + output_parser.get_format_instructions(),
                task_type="code_analysis",
                output_format="json",
                    temperature=0.1
                )
                
            classification_result = response.content
            
            # Structure the response
            classified_files = []
            for classification in classification_result.get('classifications', []):
                classified_files.append({
                    "filename": classification.get('filename', ''),
                    "type": classification.get('type', ''),
                    "scope": classification.get('scope', ''),
                    "nature": classification.get('nature', ''),
                    "volume": classification.get('volume', ''),
                    "reasoning": classification.get('reasoning', ''),
                    "additions": next((f['additions'] for f in formatted_files if f['filename'] == classification.get('filename', '')), 0),
                    "deletions": next((f['deletions'] for f in formatted_files if f['filename'] == classification.get('filename', '')), 0),
                    "changes": next((f['changes'] for f in formatted_files if f['filename'] == classification.get('filename', '')), 0)
                })
            
            return {
                "commit_sha": commit_sha,
                "commit_message": commit_message,
                "commit_author": commit_author,
                "commit_date": commit_date,
                "classified_files": classified_files
            }
                
        except Exception as e:
            logger.error(f"Error classifying commit {commit_sha}: {str(e)}")
            # Return fallback classification for this commit
            return {
                "commit_sha": commit_sha,
                "commit_message": commit_message,
                "commit_author": commit_author,
                "commit_date": commit_date,
                "classified_files": self._create_fallback_commit_classifications(commit_files, commit_message)
            }

    def _aggregate_file_classifications(self, commit_classifications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Aggregate per-commit file classifications into final per-file classifications.
        
        This method intelligently combines classifications from multiple commits for the same file,
        detecting multi-purpose files and preserving the granular commit-level context.
        
        Args:
            commit_classifications: List of commit-level classifications
            
        Returns:
            List of aggregated per-file classifications with multi-purpose detection
        """
        file_aggregations = {}
        
        # Group classifications by filename
        for commit_data in commit_classifications:
            commit_sha = commit_data.get("commit_sha", "")
            commit_message = commit_data.get("commit_message", "")
            
            for file_classification in commit_data.get("classified_files", []):
                filename = file_classification.get("filename", "")
                
                if filename not in file_aggregations:
                    file_aggregations[filename] = {
                        "filename": filename,
                        "commit_changes": [],
                        "total_additions": 0,
                        "total_deletions": 0,
                        "total_changes": 0
                    }
                
                # Add this commit's classification for this file
                file_aggregations[filename]["commit_changes"].append({
                    "commit_sha": commit_sha,
                    "commit_message": commit_message,
                    "type": file_classification.get("type", ""),
                    "scope": file_classification.get("scope", ""),
                    "nature": file_classification.get("nature", ""),
                    "volume": file_classification.get("volume", ""),
                    "reasoning": file_classification.get("reasoning", ""),
                    "additions": file_classification.get("additions", 0),
                    "deletions": file_classification.get("deletions", 0),
                    "changes": file_classification.get("changes", 0)
                })
                
                # Update totals
                file_aggregations[filename]["total_additions"] += file_classification.get("additions", 0)
                file_aggregations[filename]["total_deletions"] += file_classification.get("deletions", 0)
                file_aggregations[filename]["total_changes"] += file_classification.get("changes", 0)
        
        # Create final aggregated classifications
        final_classifications = []
        for filename, file_data in file_aggregations.items():
            commit_changes = file_data["commit_changes"]
            
            # Detect if this is a multi-purpose file
            unique_natures = set(change["nature"] for change in commit_changes)
            unique_types = set(change["type"] for change in commit_changes)
            unique_scopes = set(change["scope"] for change in commit_changes)
            
            is_multi_purpose = len(unique_natures) > 1
            
            # Determine primary characteristics
            primary_nature = self._get_primary_characteristic([change["nature"] for change in commit_changes])
            primary_type = self._get_primary_characteristic([change["type"] for change in commit_changes])
            primary_scope = self._get_primary_characteristic([change["scope"] for change in commit_changes])
            
            # Determine overall volume
            total_changes = file_data["total_changes"]
            if total_changes <= 5:
                overall_volume = "Trivial"
            elif total_changes <= 25:
                overall_volume = "Small"
            elif total_changes <= 100:
                overall_volume = "Medium"
            elif total_changes <= 500:
                overall_volume = "Large"
            else:
                overall_volume = "Very Large"
            
            # Create comprehensive reasoning
            if is_multi_purpose:
                reasoning = f"Multi-purpose file changed across {len(commit_changes)} commits: {', '.join(unique_natures)}"
            else:
                reasoning = f"Single-purpose file with {primary_nature} changes"
            
            final_classifications.append({
                "filename": filename,
                "type": primary_type if not is_multi_purpose else "Mixed",
                "scope": primary_scope if not is_multi_purpose else "Multiple",
                "nature": primary_nature,
                "volume": overall_volume,
                "reasoning": reasoning,
                "additions": file_data["total_additions"],
                "deletions": file_data["total_deletions"],
                "changes": file_data["total_changes"],
                # Enhanced multi-purpose detection
                "is_multi_purpose": is_multi_purpose,
                "unique_natures": list(unique_natures),
                "unique_types": list(unique_types),
                "unique_scopes": list(unique_scopes),
                "commit_breakdown": commit_changes,
                "commits_count": len(commit_changes)
            })
        
        return final_classifications

    def _get_primary_characteristic(self, characteristics: List[str]) -> str:
        """Get the most common characteristic from a list"""
        if not characteristics:
            return "Unknown"
        
        # Count occurrences
        char_counts = {}
        for char in characteristics:
            char_counts[char] = char_counts.get(char, 0) + 1
        
        # Return most common
        return max(char_counts, key=char_counts.get)

    def _create_fallback_classification(self, filename: str, status: str, additions: int, deletions: int, changes: int, commit_context: str) -> Dict[str, Any]:
        """Create fallback classification when LLM fails"""
        
        # Simple heuristic-based classification
        file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
        
        # Determine scope based on file extension and path
        scope = "File"
        if file_ext in ['py', 'js', 'ts', 'java', 'cpp', 'c', 'cs', 'go', 'rs']:
            scope = "Module/Package/Namespace"
        elif 'test' in filename.lower():
            scope = "Test Code"
        elif file_ext in ['md', 'rst', 'txt']:
            scope = "Documentation"
        elif file_ext in ['json', 'yaml', 'yml', 'xml', 'ini', 'cfg', 'toml']:
            scope = "Configuration"
        
        # Determine nature based on commit message
        nature = "Other"
        if commit_context:
            msg_lower = commit_context.lower()
            if any(word in msg_lower for word in ['feat', 'feature', 'add']):
                nature = "New Feature"
            elif any(word in msg_lower for word in ['fix', 'bug']):
                nature = "Bug Fix"
            elif any(word in msg_lower for word in ['refactor', 'refactoring']):
                nature = "Refactoring"
            elif any(word in msg_lower for word in ['style', 'format']):
                nature = "Code Style/Formatting"
            elif any(word in msg_lower for word in ['doc', 'documentation']):
                nature = "Documentation Updates"
        
        # Determine volume based on total changes
        if changes <= 5:
            volume = "Trivial"
        elif changes <= 25:
            volume = "Small"
        elif changes <= 100:
            volume = "Medium"
        elif changes <= 500:
            volume = "Large"
        else:
            volume = "Very Large"
                
        return {
            "filename": filename,
            "type": status,
            "scope": scope,
            "nature": nature,
            "volume": volume,
            "reasoning": "Fallback heuristic classification",
            "commit_hash": "N/A", # Commit hash is not directly available in this method's signature
            "additions": additions,
            "deletions": deletions,
            "changes": changes # Include total changes for volume
        }
    
    def _create_fallback_commit_classifications(self, commit_files: List[Dict[str, Any]], commit_message: str) -> List[Dict[str, Any]]:
        """Create fallback classifications for a single commit when LLM fails"""
        fallback_classifications = []
        
        for file_data in commit_files:
            filename = file_data.get("filename", "")
            status = file_data.get("status", "modified")
            additions = file_data.get("additions", 0)
            deletions = file_data.get("deletions", 0)
            changes = file_data.get("changes", additions + deletions)
            
            classification = self._create_fallback_classification(
                filename, status, additions, deletions, changes, commit_message
            )
            fallback_classifications.append(classification)
        
        return fallback_classifications
    
    def _create_fallback_classifications(self, pr_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create fallback classifications using cumulative data when enhanced classification fails"""
        classifications = []
        
        # Use cumulative files data as fallback
        files_data = pr_data.get("files", [])
        commits = pr_data.get("commit_info", {}).get("commits", [])
        
        # Create combined commit context
        commit_messages = [commit.get("message", "") for commit in commits]
        combined_commit_context = " | ".join(commit_messages)
        
        for file_data in files_data:
            filename = file_data.get("filename", "")
            status = file_data.get("status", "modified")
            additions = file_data.get("additions", 0)
            deletions = file_data.get("deletions", 0)
            changes = file_data.get("changes", additions + deletions)
            
            classification = self._create_fallback_classification(
                filename, status, additions, deletions, changes, combined_commit_context
            )
            
            # Add fallback multi-purpose detection
            classification.update({
                "is_multi_purpose": False,
                "unique_natures": [classification["nature"]],
                "unique_types": [classification["type"]],
                "unique_scopes": [classification["scope"]],
                "commit_breakdown": [],
                "commits_count": len(commits)
            })
            
            classifications.append(classification)
        
        return classifications
    
    async def _llm_batch_classify_changes(self, relevant_files: List[Dict[str, Any]], commit_context: Dict[str, Any]) -> BatchClassificationOutput:
        """
        Batch classify all changed files using LLM with structured JSON output.
        Returns a Pydantic model with validated structure.
        """
        # Get prompts from the prompts module
        system_message = prompts.batch_code_classification_system_prompt()
        human_prompt = prompts.batch_code_classification_human_prompt(relevant_files, commit_context)

        # Create output parser for JSON format
        output_parser = JsonOutputParser(pydantic_object=BatchClassificationOutput)

        # Generate JSON response
        response = await self.llm_client.generate_response(
            prompt=human_prompt,
            system_message=system_message + "\n" + output_parser.get_format_instructions(),
            task_type="code_analysis",
            output_format="text",  # Use text so we can parse into Pydantic model
            temperature=0.1  # Low temperature for consistent extraction
        )

        # Parse the JSON response into Pydantic model
        classification_result = output_parser.parse(response.content)

        logger.info(f"Batch classified {len(classification_result.classifications)} files using structured LLM analysis")
        return classification_result
    
    async def _llm_group_classified_changes(self, classified_changes: List[Dict[str, Any]], commit_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Group classified changes into logical change sets using commit messages as semantic keys with structured output.
        
        This method uses commit messages to understand the development intent and groups
        file changes that serve the same logical purpose or feature development goal.
        
        Args:
            classified_changes: List of classified individual file changes
            commit_info: Commit information containing messages and metadata
            
        Returns:
            List of logical change sets with grouped changes
        """
        try:
            if not classified_changes:
                return []
            
            # Extract commit messages as primary semantic drivers
            commits = commit_info.get("commits", [])
            commit_messages = [commit.get("message", "") for commit in commits]
            
            # Prepare comprehensive context for LLM grouping
            grouping_context = {
                "commit_messages": commit_messages,
                "pr_metadata": {
                    "total_commits": len(commits),
                    "total_files_changed": len(classified_changes),
                    "total_additions": sum(change.get("additions", 0) for change in classified_changes),
                    "total_deletions": sum(change.get("deletions", 0) for change in classified_changes)
                }
            }
            
            # Use structured output with Pydantic model
            grouping_result = await self._llm_group_changes_structured(classified_changes, grouping_context)
            
            # Convert Pydantic model output to our internal format
            logical_change_sets = []
            for change_set in grouping_result.change_sets:
                # Get the actual changes for these indices
                changes_in_set = []
                for idx in change_set.change_indices:
                    if 1 <= idx <= len(classified_changes):
                        changes_in_set.append(classified_changes[idx - 1])  # Convert to 0-based indexing
                    
                    if changes_in_set:
                        logical_change_sets.append({
                        "name": change_set.name,
                        "description": change_set.description,
                            "changes": changes_in_set,
                        "primary_nature": change_set.primary_nature,
                        "estimated_impact": change_set.estimated_impact
                    })
            
            # Fallback if no valid change sets were created
            if not logical_change_sets:
                return self._create_semantic_fallback_grouping(classified_changes, commit_messages)
            
            logger.info(f"Grouped {len(classified_changes)} changes into {len(logical_change_sets)} logical change sets using structured commit semantics")
            return logical_change_sets
                
        except Exception as e:
            logger.error(f"Error in structured LLM grouping: {str(e)}")
            # Fallback to semantic grouping by commit patterns
            return self._create_semantic_fallback_grouping(classified_changes, commit_messages)
    
    async def _llm_group_changes_structured(self, classified_changes: List[Dict[str, Any]], grouping_context: Dict[str, Any]) -> ChangeGroupingOutput:
        """
        Group classified changes using LLM with structured JSON output.
        Returns a Pydantic model with validated structure.
        """
        # Get prompts from the prompts module
        system_message = prompts.change_grouping_system_prompt()
        human_prompt = prompts.change_grouping_human_prompt(classified_changes, grouping_context)

        # Create output parser for JSON format
        output_parser = JsonOutputParser(pydantic_object=ChangeGroupingOutput)

        # Generate JSON response
        response = await self.llm_client.generate_response(
            prompt=human_prompt,
            system_message=system_message + "\n" + output_parser.get_format_instructions(),
            task_type="code_analysis",
            output_format="text",  # Use text so we can parse into Pydantic model
            temperature=0.1  # Low temperature for consistent grouping
        )

        # Parse the JSON response into Pydantic model
        grouping_result = output_parser.parse(response.content)

        logger.info(f"Structured grouping created {len(grouping_result.change_sets)} logical change sets")
        return grouping_result
    
    def _create_fallback_classification(self, filename: str, status: str, additions: int, deletions: int, changes: int, commit_context: str) -> Dict[str, Any]:
        """Create fallback classification when LLM fails"""
        
        # Simple heuristic-based classification
        file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
        
        # Determine scope based on file extension and path
        scope = "File"
        if file_ext in ['py', 'js', 'ts', 'java', 'cpp', 'c', 'cs', 'go', 'rs']:
            scope = "Module/Package/Namespace"
        elif 'test' in filename.lower():
            scope = "Test Code"
        elif file_ext in ['md', 'rst', 'txt']:
            scope = "Documentation"
        elif file_ext in ['json', 'yaml', 'yml', 'xml', 'ini', 'cfg', 'toml']:
            scope = "Configuration"
        
        # Determine nature based on commit message
        nature = "Other"
        if commit_context:
            msg_lower = commit_context.lower()
            if any(word in msg_lower for word in ['feat', 'feature', 'add']):
                nature = "New Feature"
            elif any(word in msg_lower for word in ['fix', 'bug']):
                nature = "Bug Fix"
            elif any(word in msg_lower for word in ['refactor', 'refactoring']):
                nature = "Refactoring"
            elif any(word in msg_lower for word in ['style', 'format']):
                nature = "Code Style/Formatting"
            elif any(word in msg_lower for word in ['doc', 'documentation']):
                nature = "Documentation Updates"
        
        # Determine volume based on total changes
        if changes <= 5:
            volume = "Trivial"
        elif changes <= 25:
            volume = "Small"
        elif changes <= 100:
            volume = "Medium"
        elif changes <= 500:
            volume = "Large"
        else:
            volume = "Very Large"
        
        return {
            "filename": filename,
            "type": status,
            "scope": scope,
            "nature": nature,
            "volume": volume,
            "reasoning": "Fallback heuristic classification",
            "commit_hash": "N/A", # Commit hash is not directly available in this method's signature
            "additions": additions,
            "deletions": deletions,
            "changes": changes # Include total changes for volume
        }
    
    def _create_semantic_fallback_grouping(self, classified_changes: List[Dict[str, Any]], commit_messages: List[str]) -> List[Dict[str, Any]]:
        """Create fallback grouping when LLM fails to use commit semantics"""
        if not classified_changes:
            return []
        
        # Simple grouping by commit hash (fallback)
        commit_groups = {}
        for i, change in enumerate(classified_changes):
            commit_hash = change.get("commit_hash", "unknown")
            if commit_hash not in commit_groups:
                commit_groups[commit_hash] = []
            commit_groups[commit_hash].append(change)
        
        # Convert to logical change sets
        logical_change_sets = []
        for i, (commit_hash, changes) in enumerate(commit_groups.items()):
            # Determine primary nature
            natures = [change.get("nature", "Other") for change in changes]
            primary_nature = max(set(natures), key=natures.count)
            
            # Estimate impact based on the changes in the set
            total_changes = sum(change.get("changes", 0) for change in changes)
            if total_changes <= 5:
                estimated_impact = "Low"
            elif total_changes <= 25:
                estimated_impact = "Medium"
            else:
                estimated_impact = "High"
            
            logical_change_sets.append({
                "name": f"Change Set {i+1} - {commit_hash[:8]}",
                "description": f"Changes from commit {commit_hash[:8]}",
                "changes": changes,
                "primary_nature": primary_nature,
                "estimated_impact": estimated_impact
            })
        
        return logical_change_sets
    
    def _create_simple_fallback_grouping(self, classified_changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create simple fallback grouping when LLM fails"""
        if not classified_changes:
            return []
        
        # Group all changes into a single logical change set as last resort
        natures = [change.get("nature", "Other") for change in classified_changes]
        primary_nature = max(set(natures), key=natures.count) if natures else "Other"
        
        # Estimate impact based on total changes
        total_changes = sum(change.get("changes", 0) for change in classified_changes)
        if total_changes <= 10:
            estimated_impact = "Low"
        elif total_changes <= 50:
            estimated_impact = "Medium"
        else:
            estimated_impact = "High"
        
        return [{
            "name": "All Changes",
            "description": "All file changes grouped together (fallback)",
            "changes": classified_changes,
            "primary_nature": primary_nature,
            "estimated_impact": estimated_impact
        }]
    
    async def _determine_traceability_status(self, logical_change_sets: List[Dict[str, Any]], repository: str, branch: str, baseline_map_data: Optional[BaselineMapModel]) -> Dict[str, Any]:
        """Determine if traceability status is available and if it's sufficient"""
        # Placeholder implementation
        return {"traceability_status": "sufficient", "details": "Traceability map available"}
    
    async def _trace_impact_through_map(self, changes_modification_outdated_rename: List[Dict[str, Any]], traceability_map: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Trace impact through the traceability map"""
        # Placeholder implementation
        return [{"element_id": "req1", "element_type": "Requirement", "impact_reason": "Code changes in src/auth/service.py", "likelihood": 0.9, "severity": "High", "change_details": {"file": "src/auth/service.py", "additions": 15, "deletions": 3}}]
    
    async def _llm_assess_likelihood_and_severity(self, combined_findings: List[Dict[str, Any]], logical_change_sets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Assess likelihood and severity for each combined finding"""
        # Placeholder implementation
        return [{"element_id": "req1", "element_type": "Requirement", "impact_reason": "Code changes in src/auth/service.py", "likelihood": 0.9, "severity": "High", "change_details": {"file": "src/auth/service.py", "additions": 15, "deletions": 3}}]
    
    async def _filter_high_priority_findings(self, prioritized_findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter findings to include only high-priority ones"""
        # Placeholder implementation
        return [{"element_id": "req1", "element_type": "Requirement", "impact_reason": "Code changes in src/auth/service.py", "likelihood": 0.9, "severity": "High", "change_details": {"file": "src/auth/service.py", "additions": 15, "deletions": 3}}]
    
    async def _query_existing_suggestions(self, repository: str, pr_number: int) -> List[Dict[str, Any]]:
        """Query existing documentation suggestions for the PR"""
        # Placeholder implementation
        return [{"target_document": "SRS.md", "section": "3.1 Authentication", "type": "UPDATE", "priority": "High", "what": "Update authentication requirements", "where": "Section 3.1.2", "why": "New authentication method added", "how": "Add specification for new auth method"}]
    
    async def _fetch_current_documentation(self, repo_content: Dict[str, Any], filtered_findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fetch current documentation context for suggestions"""
        # Placeholder implementation
        return {"SRS.md": {"content": "Authentication requirements are defined in Section 3.1.2."}}
    
    async def _llm_generate_suggestions(self, filtered_findings: List[Dict[str, Any]], current_docs: Dict[str, Any], logical_change_sets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate specific documentation update recommendations using LLM"""
        # Placeholder implementation
        return [{"target_document": "SRS.md", "section": "3.1 Authentication", "type": "UPDATE", "priority": "High", "what": "Update authentication requirements", "where": "Section 3.1.2", "why": "New authentication method added", "how": "Add specification for new auth method"}]
    
    async def _llm_filter_and_post_suggestions(self, generated_suggestions: List[Dict[str, Any]], existing_suggestions: List[Dict[str, Any]], repository: str, pr_number: int) -> List[DocumentationRecommendationModel]:
        """Filter generated suggestions against existing ones and post details"""
        # Placeholder implementation
        return [DocumentationRecommendationModel(
            target_document="SRS.md",
            section="3.1 Authentication",
            recommendation_type=RecommendationType.UPDATE,
            priority=RecommendationStatus.HIGH,
            what_to_update="Update authentication requirements",
            where_to_update="Section 3.1.2",
            why_update_needed="New authentication method added",
            how_to_update="Add specification for new auth method",
            affected_element_id="req1",
            affected_element_type="Requirement",
            confidence_score=0.9,
            status=RecommendationStatus.PENDING
        )]

    def _aggregate_multi_commit_classifications(self, all_classifications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Aggregate classifications for files that appear in multiple commits.
        
        This method handles the multi-purpose file problem by creating composite classifications
        that capture all the different reasons a file was changed across multiple commits.
        
        Args:
            all_classifications: List of all classifications from all commits
            
        Returns:
            List of aggregated classifications with multi-purpose detection
        """
        # Group by filename
        file_groups = {}
        for classification in all_classifications:
            filename = classification.get("filename", "")
            if filename not in file_groups:
                file_groups[filename] = []
            file_groups[filename].append(classification)
        
        aggregated_classifications = []
        
        for filename, classifications in file_groups.items():
            if len(classifications) == 1:
                # Single commit - use as-is
                aggregated_classifications.append(classifications[0])
            else:
                # Multiple commits - create composite classification
                composite = self._create_composite_classification(filename, classifications)
                aggregated_classifications.append(composite)
        
        return aggregated_classifications
    
    def _create_composite_classification(self, filename: str, classifications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a composite classification for a file changed across multiple commits.
        
        Args:
            filename: Name of the file
            classifications: List of individual commit classifications for this file
            
        Returns:
            Composite classification that captures all purposes
        """
        # Aggregate basic stats
        total_additions = sum(c.get("additions", 0) for c in classifications)
        total_deletions = sum(c.get("deletions", 0) for c in classifications)
        total_changes = sum(c.get("changes", 0) for c in classifications)
        
        # Collect all unique types, scopes, and natures
        types = list(set(c.get("type", "") for c in classifications))
        scopes = list(set(c.get("scope", "") for c in classifications))
        natures = list(set(c.get("nature", "") for c in classifications))
        
        # Get all commit info
        commit_info = []
        for c in classifications:
            commit_info.append({
                "sha": c.get("commit_sha", ""),
                "message": c.get("commit_message", ""),
                "author": c.get("commit_author", ""),
                "date": c.get("commit_date", ""),
                "purpose": c.get("nature", "")
            })
        
        # Determine primary purpose (most frequent)
        nature_counts = {}
        for nature in natures:
            nature_counts[nature] = nature_counts.get(nature, 0) + 1
        primary_nature = max(nature_counts, key=nature_counts.get) if nature_counts else "Other"
        
        # Create composite classification
        composite = {
            "filename": filename,
            "type": " + ".join(types) if len(types) > 1 else types[0] if types else "Modified",
            "scope": " + ".join(scopes) if len(scopes) > 1 else scopes[0] if scopes else "File",
            "nature": primary_nature,
            "is_multi_purpose": True,
            "all_purposes": natures,
            "purpose_breakdown": nature_counts,
            "additions": total_additions,
            "deletions": total_deletions,
            "changes": total_changes,
            "commit_count": len(classifications),
            "commits": commit_info,
            "reasoning": f"Multi-purpose file changed across {len(classifications)} commits for: {', '.join(natures)}"
        }
        
        return composite
    
    def _create_fallback_commit_classifications(self, commit_files: List[Dict[str, Any]], commit_message: str) -> List[Dict[str, Any]]:
        """Create fallback classifications for a single commit when LLM fails"""
        fallback_classifications = []
        
        for file_data in commit_files:
            filename = file_data.get("filename", "")
            status = file_data.get("status", "modified")
            additions = file_data.get("additions", 0)
            deletions = file_data.get("deletions", 0)
            changes = file_data.get("changes", additions + deletions)
            
            classification = self._create_fallback_classification(
                filename, status, additions, deletions, changes, commit_message
            )
            fallback_classifications.append(classification)
        
        return fallback_classifications

def create_document_update_recommender(llm_client: Optional[LLMClient] = None) -> DocumentUpdateRecommenderWorkflow:
    """
    Factory function to create Document Update Recommender workflow
    
    Args:
        llm_client: Optional LLM client
        
    Returns:
        DocumentUpdateRecommenderWorkflow: Configured workflow
    """
    return DocumentUpdateRecommenderWorkflow(llm_client)

# Export main classes
__all__ = ["DocumentUpdateRecommenderWorkflow", "DocumentUpdateRecommenderState", "create_document_update_recommender"] 