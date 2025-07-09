"""
LLM Client for Docureco Agent
Provides unified interface for Grok 3 and OpenAI models using LangChain
"""

import os
import logging
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

from ..config.llm_config import LLMConfig, LLMProvider, get_llm_config, get_task_config

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
        """
        Initialize LLM client
        
        Args:
            config: LLM configuration, defaults to environment-based config
        """
        self.config = config or get_llm_config()
        self.task_config = get_task_config()
        self.llm = self._initialize_llm()
        
        logger.info(f"Initialized LLM client with provider: {self.config.provider}, model: {self.config.llm_model}")
    
    def _initialize_llm(self) -> BaseLanguageModel:
        """
        Initialize the appropriate LLM based on configuration
        
        Returns:
            BaseLanguageModel: Configured LLM instance
        """
        if self.config.provider == LLMProvider.GROK:
            return self._initialize_grok()
        else:
            return self._initialize_openai()
    
    def _initialize_grok(self) -> ChatOpenAI:
        """
        Initialize Grok 3 using OpenAI-compatible interface
        
        Returns:
            ChatOpenAI: Configured Grok 3 model
        """
        if not self.config.api_key:
            raise ValueError("GROK_API_KEY environment variable is required for Grok 3")
        
        print(f"Initializing Grok with base_url: {self.config.base_url}")
        print(f"Grok API key starts with: {self.config.api_key[:10]}...")
        
        return ChatOpenAI(
            model=self.config.llm_model,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            max_retries=self.config.max_retries,
            request_timeout=self.config.request_timeout,
            top_p=self.config.top_p,
            frequency_penalty=self.config.frequency_penalty,
            presence_penalty=self.config.presence_penalty
        )
    
    def _initialize_openai(self) -> ChatOpenAI:
        """
        Initialize OpenAI model (fallback)
        
        Returns:
            ChatOpenAI: Configured OpenAI model
        """
        if not self.config.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI")
        
        print(f"Initializing OpenAI with base_url: {self.config.base_url}")
        print(f"OpenAI API key starts with: {self.config.api_key[:10]}...")
        
        return ChatOpenAI(
            model=self.config.llm_model,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            max_retries=self.config.max_retries,
            request_timeout=self.config.request_timeout
        )
    
    async def generate_response(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        task_type: Optional[str] = None,
        output_format: str = "text",
        **kwargs
    ) -> LLMResponse:
        """
        Generate response using LLM
        
        Args:
            prompt: User prompt/query
            system_message: System message for context
            task_type: Type of task (code_analysis, traceability_mapping, etc.)
            output_format: Response format ("text" or "json")
            **kwargs: Additional parameters for LLM
            
        Returns:
            LLMResponse: Standardized response object
        """
        try:
            # Apply task-specific configuration if provided
            llm = self._configure_for_task(task_type, **kwargs)
            
            # Prepare messages
            messages = []
            if system_message:
                messages.append(SystemMessage(content=system_message))
            messages.append(HumanMessage(content=prompt))
            
            # Generate response
            response = await llm.ainvoke(messages)
            
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
    
    def _configure_for_task(self, task_type: Optional[str], **kwargs) -> BaseLanguageModel:
        """
        Configure LLM for specific task
        
        Args:
            task_type: Type of task to configure for
            **kwargs: Override parameters
            
        Returns:
            BaseLanguageModel: Configured LLM
        """
        if not task_type:
            return self.llm
        
        task_config = getattr(self.task_config, task_type, {})
        
        # Override configuration for specific task
        if self.config.provider == LLMProvider.GROK:
            print(f"Configuring Grok for task '{task_type}' with base_url: {self.config.base_url}")
            return ChatOpenAI(
                model=self.config.llm_model,
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                temperature=kwargs.get('temperature', task_config.get('temperature', self.config.temperature)),
                max_tokens=kwargs.get('max_tokens', task_config.get('max_tokens', self.config.max_tokens)),
                max_retries=self.config.max_retries,
                request_timeout=self.config.request_timeout,
                top_p=self.config.top_p,
                frequency_penalty=self.config.frequency_penalty,
                presence_penalty=self.config.presence_penalty
            )
        else:
            print(f"Configuring OpenAI for task '{task_type}' with base_url: {self.config.base_url}")
            return ChatOpenAI(
                model=self.config.llm_model,
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                temperature=kwargs.get('temperature', task_config.get('temperature', self.config.temperature)),
                max_tokens=kwargs.get('max_tokens', task_config.get('max_tokens', self.config.max_tokens)),
                max_retries=self.config.max_retries,
                request_timeout=self.config.request_timeout
            )
    
    def create_prompt_template(self, template_name: str) -> ChatPromptTemplate:
        """
        Create prompt template for specific use case
        
        Args:
            template_name: Name of the template to create
            
        Returns:
            ChatPromptTemplate: Configured prompt template
        """
        templates = {
            "code_change_classifier": self._get_code_classification_template(),
            "traceability_mapper": self._get_traceability_mapping_template(),
            "impact_assessor": self._get_impact_assessment_template(),
            "recommendation_generator": self._get_recommendation_generation_template(),
        }
        
        if template_name not in templates:
            raise ValueError(f"Unknown template: {template_name}")
        
        return templates[template_name]
    
    def _get_code_classification_template(self) -> ChatPromptTemplate:
        """Code change classification prompt template"""
        system_template = """You are an expert software analyst for the Docureco system. Your task is to classify code changes according to the 4W framework:

1. What (Type): Addition, Deletion, Modification, Rename
2. Where (Scope): Function/Method, Class/Interface/Struct/Type, Module/Package/Namespace, File, API Contract, Configuration, Dependencies, Test Code, etc.
3. Why (Nature): New Feature, Bug Fix, Refactoring, Performance Optimization, Security Fix, etc.
4. How (Volume): Trivial, Small, Medium, Large, Very Large

Always respond in JSON format with: type, scope, nature, volume, and reasoning fields."""

        human_template = """Analyze this code change:

File: {filename}
Commit Message: {commit_message}
Code Diff:
{code_diff}

Classify according to the 4W framework."""

        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_template),
            HumanMessagePromptTemplate.from_template(human_template)
        ])
    
    def _get_traceability_mapping_template(self) -> ChatPromptTemplate:
        """Traceability mapping prompt template"""
        system_template = """You are an expert software architect for the Docureco system. Your task is to establish traceability mappings between code components, design elements, and requirements.

You will analyze software artifacts and create mappings following these relationships:
- Requirements (SRS) ↔ Design Elements (SDD)
- Design Elements (SDD) ↔ Design Elements (SDD)
- Design Elements (SDD) ↔ Code Components
- Code Components ↔ Code Components

Always respond in JSON format with clear mapping relationships."""

        human_template = """Create traceability mappings for:

{artifact_type}: {artifact_content}

Context:
{context}

Generate mappings according to the traceability framework."""

        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_template),
            HumanMessagePromptTemplate.from_template(human_template)
        ])
    
    def _get_impact_assessment_template(self) -> ChatPromptTemplate:
        """Impact assessment prompt template"""
        system_template = """You are an expert software analyst for the Docureco system. Your task is to assess the impact of code changes on documentation (SRS and SDD).

For each finding, provide:
- likelihood: Very Likely, Likely, Possibly, Unlikely
- severity: None, Trivial, Minor, Moderate, Major, Fundamental

Consider the nature and volume of changes when making assessments."""

        human_template = """Assess the impact of these findings:

Change Set: {change_set}
Traceability Information: {traceability_info}
Affected Elements: {affected_elements}

Provide likelihood and severity assessments for each element."""

        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_template),
            HumanMessagePromptTemplate.from_template(human_template)
        ])
    
    def _get_recommendation_generation_template(self) -> ChatPromptTemplate:
        """Recommendation generation prompt template"""
        system_template = """You are an expert technical writer for the Docureco system. Your task is to generate specific, actionable recommendations for updating SRS and SDD documentation.

Generate recommendations that are:
- Specific and clear
- Actionable by developers
- Contextually relevant to the code changes
- Properly formatted for documentation updates

Provide recommendations in clear, professional language."""

        human_template = """Generate documentation update recommendations for:

Finding Type: {finding_type}
Affected Element: {affected_element}
Code Changes: {code_changes}
Current Documentation: {current_docs}
Impact Assessment: {impact_assessment}

Provide specific, actionable recommendations."""

        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_template),
            HumanMessagePromptTemplate.from_template(human_template)
        ])

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
__all__ = ["DocurecoLLMClient", "LLMResponse", "create_llm_client"] 