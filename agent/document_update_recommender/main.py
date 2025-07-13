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
    parser.add_argument("pr_url", help="GitHub PR URL to analyze (e.g., https://github.com/owner/repo/pull/123)")
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
        
        print(f"Analyzing documentation update needs for PR: {args.pr_url}")
        
        final_state = await workflow.execute(args.pr_url)
        
        # Get recommendations and stats
        recommendations = final_state['recommendations']
        stats = final_state['processing_stats']
        
        # Print summary
        print("\n" + "="*50)
        print("DOCUMENTATION UPDATE RECOMMENDATIONS")
        print("="*50)
        print(f"PR URL: {args.pr_url}")
        print(f"Repository: {final_state['repository']}")
        print(f"PR Number: {final_state['pr_number']}")
        print(f"Branch: {final_state['branch']}")
        print(f"Files Changed: {stats.get('pr_files_changed', 0)}")
        print(f"Logical Change Sets: {stats.get('logical_change_sets', 0)}")
        print(f"Potentially Impacted Elements: {stats.get('potentially_impacted_elements', 0)}")
        print(f"High Priority Findings: {stats.get('high_priority_findings', 0)}")
        print(f"Final Recommendations: {len(recommendations)}")
        
        if final_state['errors']:
            print(f"\nErrors encountered: {len(final_state['errors'])}")
            for error in final_state['errors'][:3]:  # Show first 3 errors
                print(f"  - {error}")
        
        print("="*50)
        
        # Count recommendations by priority
        priority_counts = {}
        for rec in recommendations:
            priority = getattr(rec, 'priority', 'unknown')
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
                    # Convert recommendations to dict for JSON serialization
                    recommendations_dict = []
                    for rec in recommendations:
                        rec_dict = {
                            "target_document": rec.target_document,
                            "section": rec.section,
                            "recommendation_type": rec.recommendation_type.value if hasattr(rec.recommendation_type, 'value') else str(rec.recommendation_type),
                            "priority": rec.priority,
                            "what_to_update": rec.what_to_update,
                            "where_to_update": rec.where_to_update,
                            "why_update_needed": rec.why_update_needed,
                            "how_to_update": rec.how_to_update,
                            "affected_element_id": rec.affected_element_id,
                            "affected_element_type": rec.affected_element_type,
                            "confidence_score": rec.confidence_score,
                            "status": rec.status.value if hasattr(rec.status, 'value') else str(rec.status)
                        }
                        recommendations_dict.append(rec_dict)
                    json.dump(recommendations_dict, f, indent=2)
                elif args.format == "markdown":
                    f.write("# Documentation Update Recommendations\n\n")
                    f.write(f"**PR URL:** {args.pr_url}\n\n")
                    f.write(f"**Repository:** {final_state['repository']}\n\n")
                    f.write(f"**PR Number:** {final_state['pr_number']}\n\n")
                    f.write(f"**Branch:** {final_state['branch']}\n\n")
                    f.write("## Recommendations\n\n")
                    for i, rec in enumerate(recommendations, 1):
                        f.write(f"### {i}. {rec.target_document}\n\n")
                        f.write(f"**Priority:** {rec.priority}\n\n")
                        f.write(f"**Section:** {rec.section}\n\n")
                        f.write(f"**Type:** {rec.recommendation_type}\n\n")
                        f.write(f"**What to Update:** {rec.what_to_update}\n\n")
                        f.write(f"**Where to Update:** {rec.where_to_update}\n\n")
                        f.write(f"**Why Update Needed:** {rec.why_update_needed}\n\n")
                        f.write(f"**How to Update:** {rec.how_to_update}\n\n")
                        f.write(f"**Confidence Score:** {rec.confidence_score}\n\n")
                        f.write("---\n\n")
                else:  # text format
                    f.write(f"Documentation Update Recommendations\n")
                    f.write(f"PR URL: {args.pr_url}\n")
                    f.write(f"Repository: {final_state['repository']}\n")
                    f.write(f"PR Number: {final_state['pr_number']}\n")
                    f.write(f"Branch: {final_state['branch']}\n\n")
                    f.write("Recommendations:\n\n")
                    for i, rec in enumerate(recommendations, 1):
                        f.write(f"{i}. {rec.target_document}\n")
                        f.write(f"   Priority: {rec.priority}\n")
                        f.write(f"   Section: {rec.section}\n")
                        f.write(f"   Type: {rec.recommendation_type}\n")
                        f.write(f"   What: {rec.what_to_update}\n")
                        f.write(f"   Where: {rec.where_to_update}\n")
                        f.write(f"   Why: {rec.why_update_needed}\n")
                        f.write(f"   How: {rec.how_to_update}\n")
                        f.write(f"   Confidence: {rec.confidence_score}\n")
                        f.write("\n")
            
            print(f"📄 Recommendations saved to: {args.output}")
        else:
            # Print to stdout
            if recommendations:
                print("\nTop 5 Recommendations:")
                for i, rec in enumerate(recommendations[:5], 1):
                    print(f"{i}. {rec.target_document}")
                    print(f"   Priority: {rec.priority}")
                    print(f"   What: {rec.what_to_update}")
                    print(f"   Why: {rec.why_update_needed}")
                    print(f"   Confidence: {rec.confidence_score}")
                    print()
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