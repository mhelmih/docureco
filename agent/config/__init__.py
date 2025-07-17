"""
Configuration package for Docureco Agent
"""

from .llm_config import (
    LLMProvider,
    LLMConfig,
    get_llm_config,
    setup_logging
)

__all__ = [
    "LLMProvider",
    "LLMConfig",
    "get_llm_config",
    "setup_logging"
] 