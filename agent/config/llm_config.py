"""
LLM Configuration for Docureco Agent
Supports Grok 3 Mini Reasoning (High) as specified in Q10 analysis
"""

import os
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum

class LLMProvider(str, Enum):
    """Supported LLM providers"""
    GROK = "grok"
    OPENAI = "openai"  # Fallback for development/testing

class LLMConfig(BaseModel):
    """LLM Configuration model"""
    model_config = {"protected_namespaces": ()}
    
    provider: LLMProvider = Field(default=LLMProvider.GROK)
    llm_model: str = Field(default="grok-3-mini")
    api_key: Optional[str] = Field(default=None)
    base_url: Optional[str] = Field(default=None)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=10000, gt=0)
    max_retries: int = Field(default=3, ge=0)
    request_timeout: int = Field(default=120, gt=0)
    
    # Grok 3 specific settings based on benchmark analysis
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)

class TaskSpecificConfig(BaseModel):
    """Task-specific LLM configurations for different Docureco processes"""
    
    # For Code Change Classification (FR-B1)
    code_analysis: Dict[str, Any] = Field(default_factory=lambda: {
        "temperature": 0.1,  # Low temperature for consistent classification
        "max_tokens": 2000,
        "system_prompt_template": "code_change_classifier"
    })
    
    # For Traceability Mapping (FR-C1, FR-C2)
    traceability_mapping: Dict[str, Any] = Field(default_factory=lambda: {
        "temperature": 0.2,
        "max_tokens": 3000,
        "system_prompt_template": "traceability_mapper"
    })
    
    # For Impact Analysis (FR-C4)
    impact_assessment: Dict[str, Any] = Field(default_factory=lambda: {
        "temperature": 0.15,
        "max_tokens": 2500,
        "system_prompt_template": "impact_assessor"
    })
    
    # For Recommendation Generation (FR-D1)
    recommendation_generation: Dict[str, Any] = Field(default_factory=lambda: {
        "temperature": 0.3,  # Slightly higher for creative recommendation text
        "max_tokens": 4000,
        "system_prompt_template": "recommendation_generator"
    })

def get_llm_config() -> LLMConfig:
    """
    Get LLM configuration from environment variables
    Auto-detects provider based on API key format if not explicitly set
    
    Returns:
        LLMConfig: Configured LLM settings
    """
    # Check for API keys to auto-detect provider
    grok_api_key = os.getenv("GROK_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    
    # Auto-detect provider based on available keys and key format
    provider_env = os.getenv("DOCURECO_LLM_PROVIDER", "").lower()
    
    if provider_env == "openai":
        provider = LLMProvider.OPENAI
    elif provider_env == "grok":
        provider = LLMProvider.GROK
    elif grok_api_key and grok_api_key.startswith("xai-"):
        # Auto-detect Grok/xAI based on key format
        provider = LLMProvider.GROK
        print(f"Auto-detected Grok provider based on xAI API key format")
    elif openai_api_key and openai_api_key.startswith("sk-"):
        # Auto-detect OpenAI based on key format
        provider = LLMProvider.OPENAI
        print(f"Auto-detected OpenAI provider based on key format")
    else:
        # Default to Grok as specified in requirements
        provider = LLMProvider.GROK
        print(f"Using default Grok provider")
    
    if provider == LLMProvider.GROK:
        # Grok 3 configuration
        # Ensure base_url is never empty - ignore empty env vars
        grok_base_url = os.getenv("GROK_BASE_URL") or "https://api.x.ai/v1"
        
        config = LLMConfig(
            provider=provider,
            llm_model=os.getenv("DOCURECO_LLM_MODEL", "grok-3-mini"),
            api_key=grok_api_key,
            base_url=grok_base_url,
            temperature=float(os.getenv("DOCURECO_LLM_TEMPERATURE", "0.1")),
            max_tokens=int(os.getenv("DOCURECO_LLM_MAX_TOKENS", "10000")),
            max_retries=int(os.getenv("DOCURECO_LLM_MAX_RETRIES", "3")),
            request_timeout=int(os.getenv("DOCURECO_LLM_TIMEOUT", "120"))
        )
        print(f"Configured Grok provider with base_url: {config.base_url}")
    else:
        # OpenAI fallback configuration
        # For OpenAI, base_url can be None (uses default)
        openai_base_url = os.getenv("OPENAI_BASE_URL") or None
        
        config = LLMConfig(
            provider=provider,
            llm_model=os.getenv("DOCURECO_LLM_MODEL", "gpt-4o-mini"),
            api_key=openai_api_key,
            base_url=openai_base_url,
            temperature=float(os.getenv("DOCURECO_LLM_TEMPERATURE", "0.1")),
            max_tokens=int(os.getenv("DOCURECO_LLM_MAX_TOKENS", "4000")),
            max_retries=int(os.getenv("DOCURECO_LLM_MAX_RETRIES", "3")),
            request_timeout=int(os.getenv("DOCURECO_LLM_TIMEOUT", "120"))
        )
        print(f"Configured OpenAI provider with base_url: {config.base_url}")
    
    return config

def get_task_config() -> TaskSpecificConfig:
    """
    Get task-specific LLM configurations
    
    Returns:
        TaskSpecificConfig: Task-specific settings
    """
    return TaskSpecificConfig()

# Export configurations
__all__ = ["LLMProvider", "LLMConfig", "TaskSpecificConfig", "get_llm_config", "get_task_config"] 