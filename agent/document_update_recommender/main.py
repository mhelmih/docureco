#!/usr/bin/env python3
"""
Main entry point for Document Update Recommender workflow
Updated for the 5-step process: Scan PR, Analyze Code Changes, Assess Documentation Impact, Generate and Post Recommendations
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

from .workflow import DocumentUpdateRecommenderWorkflow
from agent.config.llm_config import setup_logging

logger = logging.getLogger(__name__)

async def main():
    """Main function for document update recommender"""
    parser = argparse.ArgumentParser(description="Recommend documentation updates based on code changes and traceability analysis")
    parser.add_argument("pr_url", help="GitHub PR URL to analyze (e.g., https://github.com/owner/repo/pull/123)")
    parser.add_argument("--output", help="Output file for recommendations (default: stdout)")
    parser.add_argument("--format", choices=["json", "markdown", "text"], default="text", 
                        help="Output format (default: json)")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                        help="Logging level (default: INFO)")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(level=args.log_level)
    
    try:
        # Create and execute document update recommender workflow
        workflow = DocumentUpdateRecommenderWorkflow()
        
        print(f"Analyzing documentation update needs for PR: {args.pr_url}")
        
        final_state = await workflow.execute(args.pr_url)
        
        # Get recommendations and stats
        recommendations = final_state['recommendations']
        
        print("="*50)
        
        # Count recommendations by priority
        priority_counts = {}
        for group in recommendations:
            for rec in group.get('recommendations', []):
                priority = rec.get('priority', 'unknown')
                priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        if priority_counts:
            print("\nRecommendations by Priority:")
            for priority, count in priority_counts.items():
                print(f"  - {priority}: {count}")
        
        # Output recommendations
        if args.output:
            # Save to file
            with open(args.output, 'w') as f:
                if args.format == "json":
                    import json
                    json.dump(recommendations, f, indent=2)
                elif args.format == "markdown":
                    f.write("# Documentation Update Recommendations\n\n")
                    f.write(f"**PR URL:** {args.pr_url}\n\n")
                    
                    rec_counter = 1
                    for group in recommendations:
                        summary = group.get('summary', {})
                        target_document = summary.get('target_document', 'Unknown Document')
                        f.write(f"## Document: {target_document}\n\n")
                        for rec in group.get('recommendations', []):
                            f.write(f"### Recommendation {rec_counter}\n\n")
                            f.write(f"**Priority:** {rec.get('priority', 'N/A')}\n\n")
                            f.write(f"**Section:** {rec.get('section', 'N/A')}\n\n")
                            f.write(f"**Type:** {rec.get('recommendation_type', 'N/A')}\n\n")
                            f.write(f"**What to Update:** {rec.get('what_to_update', 'N/A')}\n\n")
                            f.write(f"**Why Update Needed:** {rec.get('why_update_needed', 'N/A')}\n\n")
                            f.write(f"**Suggested Content:**\n```diff\n{rec.get('suggested_content', 'N/A')}\n```\n\n")
                            f.write("---\n\n")
                            rec_counter += 1
                else:  # text format
                    f.write(f"Documentation Update Recommendations\n")
                    f.write(f"PR URL: {args.pr_url}\n\n")
                    rec_counter = 1
                    for group in recommendations:
                        summary = group.get('summary', {})
                        target_document = summary.get('target_document', 'Unknown Document')
                        f.write(f"\n--- Document: {target_document} ---\n")
                        for rec in group.get('recommendations', []):
                            f.write(f"\n{rec_counter}. Recommendation\n")
                            f.write(f"   Priority: {rec.get('priority', 'N/A')}\n")
                            f.write(f"   Section: {rec.get('section', 'N/A')}\n")
                            f.write(f"   Type: {rec.get('recommendation_type', 'N/A')}\n")
                            f.write(f"   What: {rec.get('what_to_update', 'N/A')}\n")
                            f.write(f"   Why: {rec.get('why_update_needed', 'N/A')}\n")
                            f.write(f"   Suggested Content:\n---\n{rec.get('suggested_content', 'N/A')}\n---\n")
                            rec_counter += 1
            
            print(f"📄 Recommendations saved to: {args.output}")
        else:
            # Print to stdout
            if recommendations:
                print("\nTop 5 Recommendations:")
                all_recs = []
                for group in recommendations:
                    target_doc = group.get('summary', {}).get('target_document', 'Unknown')
                    for rec in group.get('recommendations', []):
                        rec['target_document'] = target_doc
                        all_recs.append(rec)

                for i, rec in enumerate(all_recs[:5], 1):
                    print(f"\n{i}. Document: {rec.get('target_document', 'N/A')}")
                    print(f"   Section: {rec.get('section', 'N/A')}")
                    print(f"   Priority: {rec.get('priority', 'N/A')}")
                    print(f"   What: {rec.get('what_to_update', 'N/A')}")
                    print(f"   Why: {rec.get('why_update_needed', 'N/A')}")
                    print(f"   Suggested Content:\n---\n{rec.get('suggested_content', 'N/A')}\n---")
            else:
                print("\nNo recommendations generated.")
        
        print("✅ Documentation update analysis completed successfully!")
        
    except Exception as e:
        logger.error(f"Failed to analyze documentation updates: {str(e)}")
        print(f"❌ Error: {str(e)}")
        if args.log_level == "DEBUG":
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 