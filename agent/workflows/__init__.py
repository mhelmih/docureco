"""
Docureco Workflows Package
Contains all LangGraph workflows for the Docureco agent
"""

from .document_update_recommendator import (
    DocumentUpdateRecommendatorWorkflow,
    DocumentUpdateRecommendatorState,
    create_document_update_recommendator
)

from .baseline_map_creator import (
    BaselineMapCreatorWorkflow,
    BaselineMapCreatorState,
    create_baseline_map_creator
)

from .baseline_map_updater import (
    BaselineMapUpdaterWorkflow,
    BaselineMapUpdaterState,
    create_baseline_map_updater
)

__all__ = [
    # Document Update Recommendator (main PR analysis)
    "DocumentUpdateRecommendatorWorkflow",
    "DocumentUpdateRecommendatorState", 
    "create_document_update_recommendator",
    
    # Initial Baseline Map Creator
    "BaselineMapCreatorWorkflow",
    "BaselineMapCreatorState",
    "create_baseline_map_creator",
    
    # Baseline Map Updater
    "BaselineMapUpdaterWorkflow", 
    "BaselineMapUpdaterState",
    "create_baseline_map_updater"
] 