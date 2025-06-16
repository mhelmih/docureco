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
        repository = os.getenv("REPOSITORY")
        branch = os.getenv("BRANCH", "main")
        force_recreate = os.getenv("FORCE_RECREATE", "false").lower() == "true"
        
        if not repository:
            print("❌ REPOSITORY environment variable is required")
            sys.exit(1)
        
        print("🚀 Starting baseline map creation...")
        print(f"📊 Analyzing repository: {repository}:{branch}")
        
        # Override existing check if force recreate is enabled
        if force_recreate:
            print("⚠️  Force recreate enabled - will overwrite existing baseline map")
        
        # Run the async workflow
        asyncio.run(create_baseline_map(repository, branch))
        
    except Exception as e:
        print(f"❌ Baseline map creation failed: {str(e)}")
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
        
        # Print results
        print("\n📈 Baseline Map Creation Results:")
        print(f"Repository: {final_state.repository}:{final_state.branch}")
        
        if hasattr(final_state, 'requirements'):
            print(f"Requirements: {len(final_state.requirements)}")
        if hasattr(final_state, 'design_elements'):
            print(f"Design Elements: {len(final_state.design_elements)}")
        if hasattr(final_state, 'code_components'):
            print(f"Code Components: {len(final_state.code_components)}")
        if hasattr(final_state, 'traceability_links'):
            print(f"Traceability Links: {len(final_state.traceability_links)}")
        
        if final_state.errors:
            print("\n⚠️  Errors encountered:")
            for error in final_state.errors:
                print(f"  - {error}")
        
        print(f"\n✅ Baseline map creation completed: {final_state.current_step}")
        
        # Print statistics if available
        if final_state.processing_stats:
            print("\n📊 Processing Statistics:")
            for key, value in final_state.processing_stats.items():
                print(f"  {key}: {value}")
        
    except Exception as e:
        print(f"❌ Error in baseline map creation: {str(e)}")
        raise

if __name__ == "__main__":
    main() 