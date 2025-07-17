"""
LLM Client for Docureco Agent
Provides unified interface for Grok 3 and OpenAI models using LangChain
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI

from ..config.llm_config import LLMConfig, LLMProvider, get_llm_config

logger = logging.getLogger(__name__)

@dataclass
class LLMResponse:
    """Standardized LLM response"""
    content: str
    metadata: Dict[str, Any]
    model_used: str
    tokens_used: Optional[int] = None
    cost: Optional[float] = None

class DocurecoLLMClient:
    """
    Unified LLM client for Docureco Agent
    Supports Grok 3 Mini Reasoning (High) as primary model with OpenAI fallback
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        """Initialize LLM client with LangSmith integration"""
        # Set up LangSmith tracing
        from ..config.llm_config import setup_langsmith
        setup_langsmith()
        
        self.config = config or get_llm_config()
        self.llm = self._initialize_llm(temperature=self.config.temperature)
        
        logger.info(f"Initialized LLM client with provider: {self.config.provider}, model: {self.config.llm_model}")
    
    def _initialize_llm(self, temperature: float = 0.1) -> BaseLanguageModel:
        """
        Initialize the appropriate LLM based on configuration
        
        Returns:
            BaseLanguageModel: Configured LLM instance
        """
        if self.config.provider == LLMProvider.GROK:
            return self._initialize_grok(temperature)
        else:
            return self._initialize_openai(temperature)
    
    def _initialize_grok(self, temperature: float = 0.1) -> ChatOpenAI:
        """
        Initialize Grok 3 using OpenAI-compatible interface
        
        Returns:
            ChatOpenAI: Configured Grok 3 model
        """
        if not self.config.api_key:
            raise ValueError("GROK_API_KEY environment variable is required for Grok 3")
        
        # Ensure base_url is always set for Grok
        base_url = self.config.base_url or "https://api.x.ai/v1"
        
        model_kwargs = {
            "reasoning_effort": self.config.reasoning_effort
        }
        
        return ChatOpenAI(
            model=self.config.llm_model,
            api_key=self.config.api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=self.config.max_tokens,
            max_retries=self.config.max_retries,
            request_timeout=self.config.request_timeout,
            model_kwargs=model_kwargs
            # Note: top_p, frequency_penalty, presence_penalty are NOT supported by Grok
        )
    
    def _initialize_openai(self, temperature: float = 0.1) -> ChatOpenAI:
        """
        Initialize OpenAI model (fallback)
        
        Returns:
            ChatOpenAI: Configured OpenAI model
        """
        if not self.config.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI")
        
        return ChatOpenAI(
            model=self.config.llm_model,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            temperature=temperature,
            max_tokens=self.config.max_tokens,
            max_retries=self.config.max_retries,
            request_timeout=self.config.request_timeout
        )
    
    async def generate_response(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        output_format: str = "text",
        temperature: float = 0.1
    ) -> LLMResponse:
        """
        Generate response using LLM
        
        Args:
            prompt: User prompt/query
            system_message: System message for context
            output_format: Response format ("text" or "json")
            
        Returns:
            LLMResponse: Standardized response object
        """
        try:            
            # Prepare messages
            messages = []
            if system_message:
                messages.append(SystemMessage(content=system_message))
            messages.append(HumanMessage(content=prompt))

            # Reinitialize LLM with temperature if provided
            if temperature:
                self.llm = self._initialize_llm(temperature)
            
            # Generate response
            response = await self.llm.ainvoke(messages)
            
            # Parse response based on format
            if output_format == "json":
                parser = JsonOutputParser()
                parsed_content = parser.parse(response.content)
            else:
                parsed_content = response.content
            
            return LLMResponse(
                content=parsed_content,
                metadata=response.response_metadata if hasattr(response, 'response_metadata') else {},
                model_used=self.config.llm_model,
                tokens_used=response.response_metadata.get('token_usage', {}).get('total_tokens') 
                           if hasattr(response, 'response_metadata') else None
            )
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {str(e)}")
            raise

# Factory function for easy instantiation
def create_llm_client(config: Optional[LLMConfig] = None) -> DocurecoLLMClient:
    """
    Factory function to create LLM client
    
    Args:
        config: Optional LLM configuration
        
    Returns:
        DocurecoLLMClient: Configured LLM client
    """
    return DocurecoLLMClient(config)

# Export main classes and functions
__all__ = ["LLMProvider", "LLMConfig", "get_llm_config", "setup_langsmith"] 