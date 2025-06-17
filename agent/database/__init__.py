"""
Database package for Docureco Agent
"""

import logging
from typing import Optional

from .supabase_client import SupabaseClient, create_supabase_client
from .baseline_map_repository import BaselineMapRepository

logger = logging.getLogger(__name__)

def create_baseline_map_repository() -> BaselineMapRepository:
    """Create baseline map repository with auto-configured database client"""
    try:
        db_client = create_supabase_client()
        return BaselineMapRepository(db_client)
    except Exception as e:
        logger.warning(f"Failed to create baseline map repository: {e}")
        # Return repository with no client - will fail gracefully
        return BaselineMapRepository(None)

# Export all public classes and functions
__all__ = [
    # Core repositories
    "BaselineMapRepository",
    
    # Database clients
    "SupabaseClient",
    
    # Factory functions
    "create_supabase_client",
    "create_baseline_map_repository"
] 