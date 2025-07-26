#!/usr/bin/env python3
"""
Main entry point for Baseline Map Updater workflow
"""

import os
import argparse
import asyncio
import subprocess
import sys
import logging

current_dir = os.path.dirname(os.path.abspath(__file__))
agent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(agent_dir)
sys.path.insert(0, agent_dir)
sys.path.insert(0, root_dir)

from .workflow import BaselineMapUpdaterWorkflow
from agent.config.llm_config import setup_logging

logger = logging.getLogger(__name__)

async def main():
    """
    Initializes and runs the baseline map updater workflow.
    It now relies on the latest git commit to fetch file changes.
    """
    parser = argparse.ArgumentParser(description="Baseline Map Updater")
    parser.add_argument("--repository", type=str, required=True, help="Repository name (e.g., 'owner/repo')")
    parser.add_argument("--branch", type=str, default="main", help="Branch name")
    parser.add_argument("--commit_sha", type=str, required=True, help="The SHA of the commit to analyze")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                        help="Logging level (default: INFO)")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(level=args.log_level)
    
    workflow = BaselineMapUpdaterWorkflow()
    
    final_state = await workflow.execute(
        repository=args.repository,
        branch=args.branch,
        commit_sha=args.commit_sha
    )
    print("\n--- Workflow Final State ---")
    if final_state.get("baseline_map"):
        # Avoid printing the whole map object for brevity
        map_summary = {
            "repository": final_state["baseline_map"].repository,
            "branch": final_state["baseline_map"].branch,
            "requirements": len(final_state["baseline_map"].requirements),
            "design_elements": len(final_state["baseline_map"].design_elements),
            "code_components": len(final_state["baseline_map"].code_components),
            "traceability_links": len(final_state["baseline_map"].traceability_links),
        }
        final_state["baseline_map"] = map_summary
    
    # Print summary
    stats = final_state.get("processing_stats", {})
    print("\n" + "="*50)
    print("BASELINE MAP UPDATER SUMMARY")
    print("="*50)
    print(f"Repository: {args.repository}")
    print(f"Branch: {args.branch}")
    print(f"Requirements: {stats.get('requirements_count', 0)}")
    print(f"Design Elements: {stats.get('total_design_elements_count', 0)}")
    print(f"Code Components: {stats.get('code_components_count', 0)}")
    print(f"Traceability Links: {stats.get('total_traceability_links_count', 0)}")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main()) 