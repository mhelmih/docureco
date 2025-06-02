"""
Configuration package for Docureco Agent
"""

from .llm_config import (
    LLMProvider,
    LLMConfig,
    TaskSpecificConfig,
    get_llm_config,
    get_task_config
)

__all__ = [
    "LLMProvider",
    "LLMConfig", 
    "TaskSpecificConfig",
    "get_llm_config",
    "get_task_config"
] 