#!/usr/bin/env python3
"""
Main entry point for Docureco Agent
Dispatches to specific workflow packages
"""

import sys
import argparse
import asyncio

from .baseline_map_creator.main import main as baseline_map_creator_main
from .baseline_map_updater.main import main as baseline_map_updater_main
from .document_update_recommender.main import main as document_update_recommender_main

def main():
    """Main dispatcher function"""
    parser = argparse.ArgumentParser(
        description="Docureco Agent - Document-Code Traceability Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available workflows:
  baseline-map-creator      Create baseline traceability maps from repository documentation and code
  baseline-map-updater      Update existing baseline traceability maps when repository changes occur
  document-update-recommender  Recommend documentation updates based on code changes and traceability analysis

Examples:
  python -m agent baseline-map-creator owner/repo --branch main
  python -m agent baseline-map-updater owner/repo --since 2024-01-01
  python -m agent document-update-recommender owner/repo --output recommendations.md
        """
    )
    
    parser.add_argument(
        "workflow",
        choices=["baseline-map-creator", "baseline-map-updater", "document-update-recommender"],
        help="Workflow to execute"
    )
    
    # Parse only the workflow argument, pass the rest to the specific workflow
    args, remaining_args = parser.parse_known_args()
    
    # Replace sys.argv with the remaining args for the specific workflow
    sys.argv = [f"agent.{args.workflow.replace('-', '_')}"] + remaining_args
    
    # Dispatch to the appropriate workflow
    if args.workflow == "baseline-map-creator":
        asyncio.run(baseline_map_creator_main())
    elif args.workflow == "baseline-map-updater":
        asyncio.run(baseline_map_updater_main())
    elif args.workflow == "document-update-recommender":
        asyncio.run(document_update_recommender_main())
    else:
        parser.error(f"Unknown workflow: {args.workflow}")
        
if __name__ == "__main__":
    main()
