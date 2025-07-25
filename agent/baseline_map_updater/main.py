#!/usr/bin/env python3
"""
Main entry point for Baseline Map Updater workflow
"""

import os
import argparse
import asyncio
import subprocess
from .workflow import BaselineMapUpdaterWorkflow

def main():
    """
    Initializes and runs the baseline map updater workflow.
    It now relies on the latest git commit to fetch file changes.
    """
    parser = argparse.ArgumentParser(description="Baseline Map Updater")
    parser.add_argument("--repository", type=str, required=True, help="Repository name (e.g., 'owner/repo')")
    parser.add_argument("--branch", type=str, default="main", help="Branch name")
    parser.add_argument("--commit_sha", type=str, required=True, help="The SHA of the commit to analyze")
    args = parser.parse_args()
    
    workflow = BaselineMapUpdaterWorkflow()
    
    async def run_workflow():
        # The 'file_changes' argument is now unused as the workflow fetches them directly
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
        print(final_state)
        print("--------------------------")

    asyncio.run(run_workflow())

if __name__ == "__main__":
    main() 