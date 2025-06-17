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

# Add current directory and parent directory to Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, current_dir)
sys.path.insert(0, parent_dir)

def main():
    """Main function for baseline map updater"""
    try:
        # Get parameters from environment variables
        repository = os.getenv("REPOSITORY")
        branch = os.getenv("BRANCH", "main")
        
        if not repository:
            print("❌ REPOSITORY environment variable is required")
            sys.exit(1)
        
        print("🔄 Starting baseline map update...")
        print(f"📊 Updating repository: {repository}:{branch}")
        
        # Run the async workflow
        asyncio.run(update_baseline_map(repository, branch))
        
    except Exception as e:
        print(f"❌ Baseline map update failed: {str(e)}")
        sys.exit(1)

async def update_baseline_map(repository: str, branch: str = "main"):
    """
    Update baseline map for repository
    
    Args:
        repository: Repository name (owner/repo)
        branch: Branch name
    """
    try:
        from agent.workflows.baseline_map_updater import create_baseline_map_updater
        
        # Create workflow
        updater = create_baseline_map_updater()
        
        # Execute workflow
        final_state = await updater.execute(repository, branch)
        
        # Print results
        print("\n📈 Baseline Map Update Results:")
        print(f"Repository: {final_state.repository}:{final_state.branch}")
        print(f"Current Step: {final_state.current_step}")
        
        if hasattr(final_state, 'processing_stats') and final_state.processing_stats:
            print(f"New Requirements: {final_state.processing_stats.get('new_requirements', 0)}")
            print(f"New Design Elements: {final_state.processing_stats.get('new_design_elements', 0)}")
            print(f"New Code Components: {final_state.processing_stats.get('new_code_components', 0)}")
            print(f"New Traceability Links: {final_state.processing_stats.get('new_traceability_links', 0)}")
        
        if hasattr(final_state, 'errors') and final_state.errors:
            print("\n⚠️  Errors encountered:")
            for error in final_state.errors:
                print(f"  - {error}")
        
        print(f"\n✅ Baseline map update completed!")
        
    except Exception as e:
        print(f"❌ Error in baseline map update: {str(e)}")
        raise

if __name__ == "__main__":
    main() 