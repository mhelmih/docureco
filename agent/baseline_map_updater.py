#!/usr/bin/env python3
"""
Main entry point for Docureco Baseline Map Updater
Updates baseline traceability maps when PRs are merged
"""

import asyncio
import logging
import os
import sys
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('baseline_map_updater.log')
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main function for baseline map updater"""
    try:
        # Get repository, branch, and PR number from environment variables
        repository = os.getenv("TARGET_REPOSITORY")
        branch = os.getenv("TARGET_BRANCH", "main")
        merged_pr_number = os.getenv("MERGED_PR_NUMBER")
        
        if not repository:
            logger.error("TARGET_REPOSITORY environment variable is required")
            sys.exit(1)
        
        pr_number = None
        if merged_pr_number:
            try:
                pr_number = int(merged_pr_number)
            except ValueError:
                logger.warning(f"Invalid MERGED_PR_NUMBER: {merged_pr_number}")
        
        logger.info(f"Starting baseline map update for {repository}:{branch}")
        if pr_number:
            logger.info(f"Processing merged PR #{pr_number}")
        
        # Run the async workflow
        asyncio.run(update_baseline_map(repository, branch, pr_number))
        
    except Exception as e:
        logger.error(f"Baseline map update failed: {str(e)}")
        sys.exit(1)

async def update_baseline_map(repository: str, branch: str = "main", merged_pr_number: Optional[int] = None):
    """
    Update baseline map for repository after PR merge
    
    Args:
        repository: Repository name (owner/repo)
        branch: Branch name
        merged_pr_number: Merged PR number (if applicable)
    """
    try:
        from .workflows.baseline_map_updater import create_baseline_map_updater
        
        # Create workflow
        updater = create_baseline_map_updater()
        
        # Execute workflow
        final_state = await updater.execute(repository, branch, merged_pr_number)
        
        if final_state.errors:
            logger.error(f"Baseline map update completed with errors: {final_state.errors}")
            
            # Print update statistics
            if final_state.update_stats:
                logger.info("Update Statistics:")
                for key, value in final_state.update_stats.items():
                    logger.info(f"  {key}: {value}")
        else:
            logger.info("Baseline map update completed successfully!")
            
            # Print update statistics
            if final_state.update_stats:
                logger.info("Update Statistics:")
                for key, value in final_state.update_stats.items():
                    logger.info(f"  {key}: {value}")
                    
                # Log summary
                new_elements = (
                    final_state.update_stats.get("new_requirements", 0) +
                    final_state.update_stats.get("new_design_elements", 0) +
                    final_state.update_stats.get("new_code_components", 0)
                )
                
                if new_elements > 0:
                    logger.info(f"Added {new_elements} new elements and {final_state.update_stats.get('new_traceability_links', 0)} traceability links")
                else:
                    logger.info("No new elements detected in this update")
        
    except Exception as e:
        logger.error(f"Error in baseline map update: {str(e)}")
        raise

if __name__ == "__main__":
    main() 