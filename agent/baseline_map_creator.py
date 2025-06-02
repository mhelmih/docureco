#!/usr/bin/env python3
"""
Main entry point for Docureco Baseline Map Creator
Creates initial baseline traceability maps for repositories
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
        logging.FileHandler('baseline_map_creator.log')
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main function for baseline map creator"""
    try:
        # Get repository and branch from environment variables
        repository = os.getenv("TARGET_REPOSITORY")
        branch = os.getenv("TARGET_BRANCH", "main")
        
        if not repository:
            logger.error("TARGET_REPOSITORY environment variable is required")
            sys.exit(1)
        
        logger.info(f"Starting baseline map creation for {repository}:{branch}")
        
        # Run the async workflow
        asyncio.run(create_baseline_map(repository, branch))
        
    except Exception as e:
        logger.error(f"Baseline map creation failed: {str(e)}")
        sys.exit(1)

async def create_baseline_map(repository: str, branch: str = "main"):
    """
    Create baseline map for repository
    
    Args:
        repository: Repository name (owner/repo)
        branch: Branch name
    """
    try:
        from .workflows.baseline_map_creator import create_baseline_map_creator
        
        # Create workflow
        creator = create_baseline_map_creator()
        
        # Execute workflow
        final_state = await creator.execute(repository, branch)
        
        if final_state.errors:
            logger.error(f"Baseline map creation completed with errors: {final_state.errors}")
            
            # Print statistics
            if final_state.processing_stats:
                logger.info("Processing Statistics:")
                for key, value in final_state.processing_stats.items():
                    logger.info(f"  {key}: {value}")
        else:
            logger.info("Baseline map creation completed successfully!")
            
            # Print statistics
            if final_state.processing_stats:
                logger.info("Processing Statistics:")
                for key, value in final_state.processing_stats.items():
                    logger.info(f"  {key}: {value}")
        
    except Exception as e:
        logger.error(f"Error in baseline map creation: {str(e)}")
        raise

if __name__ == "__main__":
    main() 