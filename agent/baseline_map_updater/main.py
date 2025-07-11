#!/usr/bin/env python3
"""
Main entry point for Baseline Map Updater workflow
"""

import asyncio
import os
import sys
import argparse
import logging
from pathlib import Path

# Add parent directories to path for absolute imports
current_dir = os.path.dirname(os.path.abspath(__file__))
agent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(agent_dir)
sys.path.insert(0, agent_dir)
sys.path.insert(0, root_dir)

from .workflow import BaselineMapUpdaterWorkflow
from agent.config.llm_config import setup_logging

logger = logging.getLogger(__name__)


async def main():
    """Main function for baseline map updater"""
    parser = argparse.ArgumentParser(description="Update baseline traceability maps when repository changes occur")
    parser.add_argument("repository", help="Repository name (owner/repo format) or local path")
    parser.add_argument("--branch", default="main", help="Branch name (default: main)")
    parser.add_argument("--since", help="Update since specific commit hash or date")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                        help="Logging level (default: INFO)")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(level=args.log_level)
    
    try:
        # Create and execute baseline map updater workflow
        workflow = BaselineMapUpdaterWorkflow()
        
        print(f"Updating baseline map for {args.repository}:{args.branch}")
        if args.since:
            print(f"Analyzing changes since: {args.since}")
        
        final_state = await workflow.execute(args.repository, args.branch, since=args.since)
        
        # Print summary
        stats = final_state.get("update_stats", {})
        print("\n" + "="*50)
        print("BASELINE MAP UPDATE SUMMARY")
        print("="*50)
        print(f"Repository: {args.repository}")
        print(f"Branch: {args.branch}")
        print(f"Changes Analyzed: {stats.get('changes_analyzed', 0)}")
        print(f"Links Updated: {stats.get('links_updated', 0)}")
        print(f"Links Added: {stats.get('links_added', 0)}")
        print(f"Links Removed: {stats.get('links_removed', 0)}")
        print(f"Update Strategy: {stats.get('update_strategy', 'N/A')}")
        print("="*50)
        
        print("✅ Baseline map update completed successfully!")
        
    except Exception as e:
        logger.error(f"Failed to update baseline map: {str(e)}")
        print(f"❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 