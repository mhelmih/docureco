"""
Prompts for Baseline Map Creator workflow
"""

from typing import Dict, Any, List
import json


class BaselineMapCreatorPrompts:
    """Collection of prompts for baseline map creation workflow"""
    
    @staticmethod
    def design_elements_with_matrix_system_prompt() -> str:
        """System prompt for extracting design elements and traceability matrix from SDD"""
        return """You are an expert software architect analyzing Software Design Documents (SDD). Your task is to:

1. Extract all design elements (components, classes, use cases, modules, tables, user interfaces, queries, diagrams, etc.) from the SDD.
2. Identify and extract the traceability matrix from the SDD, which maps requirements to design elements.

For each design element found, provide:
- id: Design element identifier reference from the document (e.g., 'C01', 'UC01', 'M01', etc.). May be empty if not available.
- name: Clear, descriptive name of the design element with its type (e.g., AddBook Class)
- description: Brief description of purpose/functionality
- type: Category (Service, Class, Interface, Component, Database, UI, etc.)
- section: Section reference from the document (if available). If available, please choose more specific section name.

For the traceability matrix, provide relationships between ANY artifacts (requirements, design elements, etc.) found:
- source_id: ID of the source artifact (e.g., 'REQ-001', 'DE-001', etc.)
- target_id: ID of the target artifact (e.g., 'DE-002', 'UC01', etc.)
- relationship_type: Leave this field as "unclassified" (will be classified later)
- source_file: File path where this relationship was found

The response will be automatically structured. If no traceability matrix is found, return an empty array for traceability_matrix."""
    
    @staticmethod
    def design_elements_with_matrix_human_prompt(content: str, file_path: str) -> str:
        """Human prompt for design elements and matrix extraction"""
        return f"""Analyze the following Software Design Document content and extract both design elements and their traceability matrix:

File: {file_path}

Content:
{content}

Extract design elements and their traceability matrix and return them as a JSON object."""
    
    @staticmethod
    def requirements_with_design_elements_system_prompt() -> str:
        """System prompt for extracting requirements and design elements from SRS"""
        return """You are an expert software architect analyzing Software Requirements Specification (SRS) documents. Your task is to:

1. Extract functional and non-functional requirements from the SRS.
2. Identify and extract design elements from the SRS, which are typically components, classes, or interfaces that are directly referenced or implied by the SRS.
3. Use the provided traceability matrix from SDD to help identify design elements that are already mapped and should be included.

For each requirement found, provide:
- title: Clear, concise title of the requirement
- description: Detailed description of what is required
- type: Category (Functional, Non-Functional, Business, User, System, etc.)
- priority: Importance level (High, Medium, Low)
- section: Section reference from the document (if available)

For each design element found, provide:
- name: Clear, descriptive name of the design element
- description: Brief description of purpose/functionality
- type: Category (Service, Class, Interface, Component, Database, UI, etc.)
- section: Section reference from the document (if available)

The response will be automatically structured with the required fields."""
    
    @staticmethod
    def requirements_with_design_elements_human_prompt(content: str, file_path: str, sdd_traceability_matrix: List[Dict[str, Any]]) -> str:
        """Human prompt for requirements and design elements extraction"""
        return f"""Analyze the following Software Requirements Specification content and extract both requirements and design elements, using the provided traceability matrix from SDD as context:

File: {file_path}

Content:
{content}

Traceability Matrix from SDD (for context):
{json.dumps(sdd_traceability_matrix, indent=2)}

Extract requirements and design elements and return them as a JSON object."""
    
    @staticmethod
    def design_element_relationships_system_prompt() -> str:
        """System prompt for creating design element relationships"""
        return """You are an expert software architect analyzing design elements and their relationships. Your task is to identify meaningful relationships between design elements based on their names, descriptions, types, typical software architecture patterns, and the provided traceability matrix context.

The traceability matrix shows existing relationships from the SDD documentation. Use this context to:
1. Understand the architectural structure and dependencies
2. Identify consistent relationship patterns
3. Find additional relationships that complement the existing ones
4. Ensure your identified relationships align with the documented architecture

For Design Element to Design Element (D→D) relationships, use ONLY these relationship types:
- refines: Element A elaborates or clarifies Element B (provides more detail or specific implementation)
- realizes: Element A manifests or embodies Element B (general manifestation relationship)
- depends_on: Element A depends on Element B to function (dependency relationships)

Selection Guidelines:
- Use "refines" when one design element provides more detailed specification of another
- Use "realizes" for general manifestation or embodiment relationships
- Use "depends_on" for functional dependencies where one element requires another to operate

For each relationship found, provide:
- source_id: ID of the source element
- target_id: ID of the target element  
- relationship_type: MUST be one of: "refines", "realizes", "depends_on"

Only identify relationships that make logical sense based on the element information and traceability matrix context. The response will be automatically structured. If no meaningful relationships exist, return an empty array."""
    
    @staticmethod
    def design_element_relationships_human_prompt(elements_data: List[Dict[str, Any]], sdd_traceability_matrix: List[Dict[str, Any]]) -> str:
        """Human prompt for design element relationship analysis"""
        return f"""Analyze the following design elements and identify meaningful relationships between them:

Design Elements:
{json.dumps(elements_data, indent=2)}

Traceability Matrix (for context):
{json.dumps(sdd_traceability_matrix, indent=2)}

Identify relationships between these design elements and return them as a JSON array."""
    
    @staticmethod
    def requirement_design_links_system_prompt() -> str:
        """System prompt for creating requirement-to-design links"""
        return """You are an expert software architect analyzing the relationships between requirements and design elements. Your task is to identify which design elements satisfy, implement, or realize specific requirements, using the provided traceability matrix from SDD documentation as authoritative context.

The traceability matrix shows existing relationships documented in the SDD. Use this as your primary source, and supplement with logical mappings where:
1. The matrix explicitly shows requirement-to-design relationships
2. Requirements and design elements have clear semantic connections
3. Design elements are described as implementing specific functional requirements
4. Non-functional requirements are addressed by architectural design elements

For Requirement to Design Element (R→D) relationships, use ONLY these relationship types:
- satisfies: Design element formally fulfills the requirement's needs (most common for D→R, but used as R→D here)
- realizes: Design element manifests or embodies the requirement concept (general manifestation relationship)

Selection Guidelines:
- Use "satisfies" when a design element clearly meets or fulfills a requirement's specifications
- Use "realizes" for general manifestation where the design element embodies the requirement concept
- Note: "implements" is reserved for Code→Design relationships only

For each relationship found, provide:
- source_id: ID of the requirement
- target_id: ID of the design element
- relationship_type: MUST be one of: "satisfies", "realizes"

Prioritize relationships from the traceability matrix, then identify additional logical connections. The response will be automatically structured. If no meaningful relationships exist, return an empty array."""
    
    @staticmethod
    def requirement_design_links_human_prompt(requirements_data: List[Dict[str, Any]], 
                                            design_elements_data: List[Dict[str, Any]], 
                                            sdd_traceability_matrix: List[Dict[str, Any]], 
                                            sdd_content: Dict[str, str]) -> str:
        """Human prompt for requirement-to-design link analysis"""
        return f"""Analyze the following requirements and design elements to identify which design elements satisfy or implement which requirements, using the traceability matrix as authoritative context:

Requirements:
{json.dumps(requirements_data, indent=2)}

Design Elements:
{json.dumps(design_elements_data, indent=2)}

Traceability Matrix (authoritative source):
{json.dumps(sdd_traceability_matrix, indent=2)}

SDD Content (for additional context):
{json.dumps(sdd_content, indent=2)}

Identify relationships between requirements and design elements and return them as a JSON array."""
    
    @staticmethod
    def design_code_links_system_prompt() -> str:
        """System prompt for creating design-to-code links"""
        return """You are an expert software architect analyzing the relationships between design elements and code components. Your task is to identify meaningful mappings between abstract design concepts and their concrete implementations in code, using the provided traceability matrix for context.

The traceability matrix shows existing relationships from the SDD documentation. Use this context to:
1. Understand which design elements are already mapped to requirements or other artifacts
2. Identify implementation patterns and architectural consistency
3. Find code components that implement the documented design elements
4. Ensure your mappings align with the documented architecture

For Design Element to Code Component (D→C) relationships, use ONLY these relationship types:
- implements: Code component implements the design element (reverse of C→D implements)
- realizes: Code component realizes/materializes the design concept (general manifestation relationship)

Selection Guidelines:
- Use "implements" when code provides direct implementation of the design element's specification
- Use "realizes" for general manifestation where code embodies the design concept
- Note: This is the reverse perspective of C→D relationships for consistency with our traceability model

For each relationship found, provide:
- source_id: ID of the design element
- target_id: ID of the code component
- relationship_type: MUST be one of: "implements", "realizes"

Analyze the design element names, descriptions, types against the code component names, paths, and content previews to identify logical connections. Use the traceability matrix to understand the architectural context. The response will be automatically structured. If no meaningful relationships exist, return an empty array."""
    
    @staticmethod
    def design_code_links_human_prompt(elements_data: List[Dict[str, Any]], 
                                     components_data: List[Dict[str, Any]], 
                                     sdd_traceability_matrix: List[Dict[str, Any]]) -> str:
        """Human prompt for design-to-code link analysis"""
        return f"""Analyze the following design elements and code components to identify meaningful relationships between them:

Design Elements:
{json.dumps(elements_data, indent=2)}

Code Components:
{json.dumps(components_data, indent=2)}

Traceability Matrix (for context):
{json.dumps(sdd_traceability_matrix, indent=2)}

Identify relationships between design elements and code components and return them as a JSON array.""" 