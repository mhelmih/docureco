#!/usr/bin/env python3
"""
Main entry point for Baseline Map Creator workflow
"""

import asyncio
import os
import sys
import argparse
import logging

# Add parent directories to path for absolute imports
current_dir = os.path.dirname(os.path.abspath(__file__))
agent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(agent_dir)
sys.path.insert(0, agent_dir)
sys.path.insert(0, root_dir)

from .workflow import create_baseline_map_creator
from agent.config.llm_config import setup_logging

logger = logging.getLogger(__name__)


async def main():
    """Main function for baseline map creator"""
    parser = argparse.ArgumentParser(description="Create baseline traceability maps from repository documentation and code")
    parser.add_argument("repository", help="Repository name (owner/repo format) or local path")
    parser.add_argument("--branch", default="main", help="Branch name (default: main)")
    parser.add_argument("--force", action="store_true", help="Force recreate existing baseline map")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                        help="Logging level (default: INFO)")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(level=args.log_level)
    
    # Set force recreate environment variable if specified
    if args.force:
        os.environ["FORCE_RECREATE"] = "true"
    
    try:
        # Create and execute baseline map creator workflow
        workflow = create_baseline_map_creator()
        
        print(f"Creating baseline map for {args.repository}:{args.branch}")
        final_state = await workflow.execute(args.repository, args.branch)
        
        # Print summary
        stats = final_state.get("processing_stats", {})
        print("\n" + "="*50)
        print("BASELINE MAP CREATION SUMMARY")
        print("="*50)
        print(f"Repository: {args.repository}")
        print(f"Branch: {args.branch}")
        print(f"Requirements: {stats.get('requirements_count', 0)}")
        print(f"Design Elements: {stats.get('total_design_elements_count', 0)}")
        print(f"Code Components: {stats.get('code_components_count', 0)}")
        print(f"Traceability Links: {stats.get('total_traceability_links_count', 0)}")
        print(f"  - Design-to-Design: {stats.get('design_to_design_links_count', 0)}")
        print(f"  - Design-to-Code: {stats.get('design_to_code_links_count', 0)}")
        print(f"  - Requirements-to-Design: {stats.get('requirements_to_design_links_count', 0)}")
        print("="*50)
        
        print("✅ Baseline map creation completed successfully!")
        
    except Exception as e:
        logger.error(f"Failed to create baseline map: {str(e)}")
        print(f"❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 