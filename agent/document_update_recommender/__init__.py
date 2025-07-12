"""
Document Update Recommender Workflow Package
Recommends documentation updates based on code changes and traceability analysis
"""

from .workflow import DocumentUpdateRecommenderWorkflow
from .main import main as document_update_recommender_main

__all__ = ["DocumentUpdateRecommenderWorkflow", "document_update_recommender_main"] 