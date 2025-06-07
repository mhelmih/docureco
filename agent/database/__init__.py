"""
Database package for Docureco Agent
Supports both Supabase and direct PostgreSQL connections
"""

import os
import logging
from typing import Optional

from .supabase_client import (
    SupabaseClient,
    create_supabase_client
)

from .baseline_map_repository import (
    BaselineMapRepository
)

from .vector_search_repository import (
    VectorSearchRepository,
    create_vector_search_repository
)

logger = logging.getLogger(__name__)

def create_database_client() -> Optional[SupabaseClient]:
    """
    Create database client based on available environment variables
    
    Priority:
    1. Supabase (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY)
    2. Direct PostgreSQL (DATABASE_URL) - Future implementation
    
    Returns:
        Optional[SupabaseClient]: Database client or None if no valid config
    """
    # Try Supabase first (recommended)
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if supabase_url and supabase_key:
        try:
            logger.info("Using Supabase database connection")
            return create_supabase_client(supabase_url, supabase_key)
        except Exception as e:
            logger.error(f"Failed to create Supabase client: {e}")
    
    # Fallback to direct PostgreSQL (future implementation)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        logger.warning("DATABASE_URL detected but direct PostgreSQL support not implemented yet")
        logger.warning("Please use Supabase connection (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY)")
        return None
    
    logger.warning("No database configuration found")
    logger.warning("Available options:")
    logger.warning("1. Supabase: Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
    logger.warning("2. PostgreSQL: Set DATABASE_URL (future support)")
    
    return None

def create_baseline_map_repository() -> BaselineMapRepository:
    """Create baseline map repository with auto-configured database client"""
    try:
        db_client = create_database_client()
        return BaselineMapRepository(db_client)
    except Exception as e:
        logger.warning(f"Failed to create baseline map repository: {e}")
        # Return repository without client (will fail gracefully)
        return BaselineMapRepository(None)

def create_vector_search_repository() -> VectorSearchRepository:
    """Create vector search repository with auto-configured database client"""
    try:
        db_client = create_database_client()
        return VectorSearchRepository(db_client)
    except Exception as e:
        logger.warning(f"Failed to create vector search repository: {e}")
        # Return repository without client (will fail gracefully)
        return VectorSearchRepository(None)

# Export main classes and factory functions
__all__ = [
    # Core clients
    "SupabaseClient",
    "create_supabase_client",
    
    # Repositories
    "BaselineMapRepository", 
    "VectorSearchRepository",
    
    # Factory functions
    "create_database_client",
    "create_baseline_map_repository",
    "create_vector_search_repository"
] 