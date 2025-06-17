#!/usr/bin/env python3
"""
Main entry point for Docureco Baseline Map Creator
Creates initial baseline traceability maps for repositories
"""

import asyncio
import os
import sys

# Add current directory and parent directory to Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, current_dir)
sys.path.insert(0, parent_dir)

def main():
    """Main function for baseline map creator"""
    try:
        # Get repository and branch from environment variables
        repository = os.getenv("REPOSITORY")
        branch = os.getenv("BRANCH")
        force_recreate = os.getenv("FORCE_RECREATE").lower() == "true"
        
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
        from agent.workflows.baseline_map_creator import create_baseline_map_creator
        
        # Create workflow
        creator = create_baseline_map_creator()
        
        # Execute workflow
        final_state = await creator.execute(repository, branch)
        
        # Print results
        print("\n📈 Baseline Map Creation Results:")
        print(f"Repository: {final_state['repository']}:{final_state['branch']}")
        
        if 'requirements' in final_state:
            print(f"Requirements: {len(final_state['requirements'])}")
        if 'design_elements' in final_state:
            print(f"Design Elements: {len(final_state['design_elements'])}")
        if 'code_components' in final_state:
            print(f"Code Components: {len(final_state['code_components'])}")
        if 'traceability_links' in final_state:
            print(f"Traceability Links: {len(final_state['traceability_links'])}")
        
        if final_state.get('errors'):
            print("\n⚠️  Errors encountered:")
            for error in final_state['errors']:
                print(f"  - {error}")
        
        print(f"\n✅ Baseline map creation completed: {final_state['current_step']}")
        
        # Print statistics if available
        if final_state.get('processing_stats'):
            print("\n📊 Processing Statistics:")
            for key, value in final_state['processing_stats'].items():
                print(f"  {key}: {value}")
        
    except Exception as e:
        print(f"❌ Error in baseline map creation: {str(e)}")
        raise

if __name__ == "__main__":
    main() 