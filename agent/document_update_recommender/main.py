#!/usr/bin/env python3
"""
Main entry point for Document Update Recommender workflow
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

from .workflow import DocumentUpdateRecommenderWorkflow
from agent.config.llm_config import setup_logging

logger = logging.getLogger(__name__)


async def main():
    """Main function for document update recommender"""
    parser = argparse.ArgumentParser(description="Recommend documentation updates based on code changes and traceability analysis")
    parser.add_argument("repository", help="Repository name (owner/repo format) or local path")
    parser.add_argument("--branch", default="main", help="Branch name (default: main)")
    parser.add_argument("--since", help="Analyze changes since specific commit hash or date")
    parser.add_argument("--output", help="Output file for recommendations (default: stdout)")
    parser.add_argument("--format", choices=["json", "markdown", "text"], default="text", 
                        help="Output format (default: text)")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                        help="Logging level (default: INFO)")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(level=args.log_level)
    
    try:
        # Create and execute document update recommender workflow
        workflow = DocumentUpdateRecommenderWorkflow()
        
        print(f"Analyzing documentation update needs for {args.repository}:{args.branch}")
        if args.since:
            print(f"Analyzing changes since: {args.since}")
        
        final_state = await workflow.execute(args.repository, args.branch, since=args.since)
        
        # Get recommendations
        recommendations = final_state.get("recommendations", [])
        stats = final_state.get("analysis_stats", {})
        
        # Print summary
        print("\n" + "="*50)
        print("DOCUMENTATION UPDATE RECOMMENDATIONS")
        print("="*50)
        print(f"Repository: {args.repository}")
        print(f"Branch: {args.branch}")
        print(f"Code Changes Analyzed: {stats.get('code_changes_analyzed', 0)}")
        print(f"Documentation Files Affected: {stats.get('docs_affected', 0)}")
        print(f"Total Recommendations: {len(recommendations)}")
        
        # Count by priority
        priority_counts = {}
        for rec in recommendations:
            priority = rec.get('priority', 'unknown')
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        for priority, count in priority_counts.items():
            print(f"  - {priority.title()}: {count}")
        
        print("="*50)
        
        # Output recommendations
        if args.output:
            # Save to file
            with open(args.output, 'w') as f:
                if args.format == "json":
                    import json
                    json.dump(recommendations, f, indent=2)
                elif args.format == "markdown":
                    f.write("# Documentation Update Recommendations\n\n")
                    for i, rec in enumerate(recommendations, 1):
                        f.write(f"## {i}. {rec.get('document_path', 'Unknown Document')}\n")
                        f.write(f"**Priority:** {rec.get('priority', 'Unknown')}\n\n")
                        f.write(f"**Section:** {rec.get('section_reference', 'N/A')}\n\n")
                        f.write(f"**Update Type:** {rec.get('update_type', 'N/A')}\n\n")
                        f.write(f"**Rationale:** {rec.get('rationale', 'N/A')}\n\n")
                        if rec.get('suggested_content'):
                            f.write(f"**Suggested Content:**\n```\n{rec['suggested_content']}\n```\n\n")
                        f.write("---\n\n")
                else:  # text format
                    for i, rec in enumerate(recommendations, 1):
                        f.write(f"{i}. {rec.get('document_path', 'Unknown Document')}\n")
                        f.write(f"   Priority: {rec.get('priority', 'Unknown')}\n")
                        f.write(f"   Section: {rec.get('section_reference', 'N/A')}\n")
                        f.write(f"   Update Type: {rec.get('update_type', 'N/A')}\n")
                        f.write(f"   Rationale: {rec.get('rationale', 'N/A')}\n")
                        if rec.get('suggested_content'):
                            f.write(f"   Suggested Content: {rec['suggested_content'][:100]}...\n")
                        f.write("\n")
            
            print(f"📄 Recommendations saved to: {args.output}")
        else:
            # Print to stdout
            print("\nTop 5 Recommendations:")
            for i, rec in enumerate(recommendations[:5], 1):
                print(f"{i}. {rec.get('document_path', 'Unknown Document')}")
                print(f"   Priority: {rec.get('priority', 'Unknown')}")
                print(f"   Rationale: {rec.get('rationale', 'N/A')}")
                print()
        
        print("✅ Documentation update analysis completed successfully!")
        
    except Exception as e:
        logger.error(f"Failed to analyze documentation updates: {str(e)}")
        print(f"❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 