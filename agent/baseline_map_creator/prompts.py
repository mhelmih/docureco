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
2. Identify and extract the traceability matrix from the SDD, which maps requirements to design elements. If no traceability matrix is found, return an empty array for traceability_matrix.

For each design element found, provide:
- reference_id: Design element identifier reference from the document (e.g., 'C01', 'UC01', 'M01', etc.)
- name: Clear, descriptive name of the design element with its type (e.g., AddBook Class)
- description: Brief description of purpose/functionality
- type: Category (Use Case, Scenario, Class, Interface, Component, Database Table, UI, Diagram, Service, Query, Algorithm, Process, Procedure, Module, etc.)
- section: Section reference from the document. Please choose more specific section name (full with number, name, and/or title. Not just number or title). For example, if the section is "4.1.1 Class: Book", the section should be "4.1.1 Class: Book".

For the traceability matrix, provide relationships between ANY artifacts (requirements, design elements, etc.) found:
- source_id: ID of the source artifact (e.g., 'REQ-001', 'DE001', etc.). If the source artifact is a design element, use the reference_id of the design element. If the source artifact is a requirement, use the reference_id of the requirement.
- target_id: ID of the target artifact (e.g., 'DE-002', 'UC01', etc.). If the target artifact is a design element, use the reference_id of the design element. If the target artifact is a requirement, use the reference_id of the requirement.
- relationship_type: Leave this field as "unclassified" (will be classified later)
- source_file: File path where this relationship was found

**CRITICAL INSTRUCTIONS:**
- Anything extracted from the traceability matrix as a design element should have `Traceability Matrix Element - <element_type>` as the type. For example, if the element is a requirement, the type should be `Traceability Matrix Element - Requirement`.
- For every relationship in the traceability matrix, the target_id MUST exactly match the reference_id field from the extracted design elements. If the source_id is not a design element, it is OK to use the source_id as it is because it will be verified in the next step.
- If you cannot find a valid reference_id for the target_id, SKIP that relationship.
- Do NOT use class names, section titles, or any other label as an ID. Only use the reference_id from the extracted elements.
- If the SDD traceability matrix uses a different label (e.g., just "Book"), you MUST map it to the correct reference_id you extracted (e.g., "Book-Class").
- If you cannot confidently map a matrix entry to a valid reference_id, SKIP that relationship.

NOTES:
- The SDD will be provided in the markdown format.
- Images in markdown format would look like this:
```
![Diagram Name](image_path.png)
```
- Please be aware of the diagram images in the SDD because all images in the SDD are already described textually in the SDD.
- All design elements need to be extracted from the SDD because the design elements will be used to create a traceability map (requirements <-> design elements, design elements <-> design elements, design elements <-> code components).
- This traceability map will be used to track code changes impact to the documentation and will be used to generate documentation update recommendations. So, extract as many design elements as possible from the SDD.
- The explicit traceability matrix inside the SDD will be used as a baseline for the traceability map.
- Use the design element identifier used in the SDD for reference_id field if available. If the design element identifier is not available, use the design element name and the type as the reference_id (for example, there is a class "Book" without ID but it is in the section "4.1.1 Class: Book" then the reference_id should be "Book-Class").
- The explicit traceability matrix inside the SDD may not use the reference_id rule like we defined for the design elements. So, please look at the table header to know that type of design element the id is referring to before extracting the traceability matrix. For example, there is a class "Book" without ID and we extract it with the reference_id "Book-Class". The traceability matrix may be only using "Book" as the id. If the table header is "Related Class", then the id "Book" is referring to the class Book the design element that we extracted with reference_id "Book-Class". If this is the case, please use the reference_id "Book-Class" for the id "Book" in the traceability matrix.

The response will be automatically structured with the required fields."""
    
    @staticmethod
    def design_elements_with_matrix_human_prompt(content: str, file_path: str) -> str:
        """Human prompt for design elements and matrix extraction"""
        return f"""Analyze the following Software Design Document content and extract both design elements and their traceability matrix:

File Path: {file_path}

Content:
{content}"""
    
    @staticmethod
    def requirements_with_design_elements_system_prompt() -> str:
        """System prompt for extracting requirements and design elements from SRS"""
        return """You are an expert software architect analyzing Software Requirements Specification (SRS) documents. Your task is to:

1. Extract functional and non-functional requirements from the SRS.
2. Identify and extract design elements (usually the initial design elements produced from the requirements analysis) from the SRS (which are typically use cases, components, classes, interfaces, tables, diagrams, scenarios, activities, flowchart, DFD, etc.) that are directly referenced or implied by the SRS.
3. Use the provided traceability matrix from SDD to help identify requirements that must be extracted from the SRS because they are already mapped to design elements in the SDD.
4. If there is an explicit traceability matrix in the SRS, use it to help identify requirements and (initial) design elements that must be extracted from the SRS.

For each requirement found, provide:
- reference_id: Requirement identifier reference from the document (e.g., 'REQ-001', 'UC01', 'M01', etc.)
- title: Clear, concise title of the requirement
- description: Detailed description of what is required
- type: Category (Functional, Non-Functional, Business, User, System, etc.)
- priority: Importance level (High, Medium, Low)
- section: Section reference from the document. Please choose more specific section name (full with number, name, and/or title. Not just number or title). For example, if the section is "4.1.1 Class: Book", the section should be "4.1.1 Class: Book".

For each design element found, provide:
- reference_id: Design element identifier reference from the document (e.g., 'C01', 'UC01', 'M01', etc.)
- name: Clear, descriptive name of the design element
- description: Brief description of purpose/functionality
- type: Category (Use Case, Scenario, Class, Interface, Component, Database Table, UI, Diagram, Service, Query, Algorithm, Process, Procedure, Module, etc.)
- section: Section reference from the document. Please choose more specific section name (full with number, name, and/or title. Not just number or title). For example, if the section is "4.1.1 Class: Book", the section should be "4.1.1 Class: Book".

NOTES:
- The SRS will be provided in the markdown format.
- Images in markdown format would look like this:
```
![Diagram Name](image_path.png)
```
- Please be aware of the diagram images in the SRS because all images in the SRS are already described textually in the SRS.
- All requirements and design elements need to be extracted from the SRS because they will be used to create a traceability map (requirements <-> design elements, design elements <-> design elements, design elements <-> code components).
- This traceability map will be used to track code changes impact to the documentation and will be used to generate documentation update recommendations. So, extract as many requirements and design elements as possible from the SRS.
- Use the requirement and design element identifier used in the SRS for reference_id field if available. If the requirement or design element identifier is not available, use the requirement or design element name as the reference_id (for example, there is a class "Book" without ID but it is in the section "4.1.1 Class: Book" then the reference_id should be "Book").

The response will be automatically structured with the required fields."""
    
    @staticmethod
    def requirements_with_design_elements_human_prompt(content: str, file_path: str, sdd_traceability_matrix: List[Dict[str, Any]]) -> str:
        """Human prompt for requirements and design elements extraction"""
        return f"""Analyze the following Software Requirements Specification content and extract both requirements and design elements, using the provided traceability matrix from SDD as context:

File Path: {file_path}

Content:
{content}

Traceability Matrix from SDD:
{json.dumps(sdd_traceability_matrix, indent=2)}

Extract requirements and design elements and return them as a JSON object."""
    
    @staticmethod
    def design_element_relationships_system_prompt() -> str:
        """System prompt for creating design element relationships"""
        return """You are an expert software architect analyzing design elements and their relationships.
    
TASK:
1. You will be given a list of design elements and a traceability matrix that shows existing relationships (unclassified) between requirements to design elements and design elements to design elements. 
2. Classify the existing relationships into meaningful relationships ONLY between design elements based on their IDs, names, descriptions, types, typical software architecture patterns, and the provided traceability matrix context. 
3. Identify more relationships that complement the existing ones (if any) and classify them.
4. Make sure your identified relationships are meaningful and logical based on the given context.
5. If no meaningful relationships exist, return an empty array.

For Design Element to Design Element (D→D) relationships, use ONLY these relationship types:
1. refines: Element A elaborates or clarifies Element B (provides more detail or specific implementation)
2. depends_on: Element A depends on Element B to function (dependency relationships)
3. realizes: Element A manifests or embodies Element B (general manifestation relationship)

Selection Guidelines:
- Use "refines" when one design element provides more detailed specification of another
- Use "depends_on" for functional dependencies where one element requires another to operate
- Use "realizes" for general manifestation or embodiment relationships.
- Only identify relationships that make logical sense based on the element information and traceability matrix context. If you are not sure about the relationship type, use "realizes" as the default relationship type.

For each relationship found, provide:
- source_id: ID of the source element. Use the reference_id of the source element.
- target_id: ID of the target element. Use the reference_id of the target element.
- relationship_type: MUST be one of: "refines", "realizes", "depends_on".

**CRITICAL INSTRUCTIONS:**
- For every relationship in the traceability matrix, the source_id and target_id MUST exactly match the reference_id field from the extracted design elements. If you cannot find a valid reference_id, SKIP that relationship.
- Do NOT use class names, section titles, or any other label as an ID. Only use the reference_id from the extracted elements.
- If you cannot confidently map a matrix entry to a valid reference_id, SKIP that relationship.

NOTES:
- The existing traceability matrix is extracted from SDD documentations.
- The design elements are extracted from SRS and SDD documentations. The design elements found in SRS are usually the initial design elements produced from the requirements analysis and modelling.
- The output (the relationships between design elements) will be used to create a traceability map (requirements <-> design elements, design elements <-> design elements, design elements <-> code components). 
- The traceability map will be used to track code changes impact to the documentation and will be used to generate documentation update recommendations.
- This step only produces the relationships between design elements. The requirements to design elements and design elements to code components relationships will be identified in the next step. So, please be careful when identifying the relationships between design elements.
- Because this is design-to-design mapping, you can know which traceability matrix entries are used to identify the relationships between design elements by checking the source_id and target_id which are design element reference_ids.
- Design-to-design relationships could be many-to-many but there will be no circular relationships.

The response will be automatically structured."""
    
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
        return """You are an expert software architect analyzing the relationships between requirements and design elements. 


TASK:
1. You will be given a list of requirements, a list of design elements, SDD content, and a traceability matrix that shows existing relationships (unclassified) between requirements to design elements and design elements to design elements.
2. Classify the existing relationships into meaningful relationships ONLY between requirements and design elements based on their IDs, names, descriptions, types, typical software architecture patterns, and the provided traceability matrix context.
3. Identify more relationships that complement the existing ones (if any) and classify them.
4. Make sure your identified relationships are meaningful and logical based on the given context.
5. If no meaningful relationships exist, return an empty array.

For Requirement to Design Element (R→D) relationships, use ONLY these relationship types:
- satisfies: Design element formally satisfies the requirement's needs (most common for D→R, but used as R→D here)
- realizes: Design element manifests or embodies the requirement concept (general manifestation relationship)

Selection Guidelines:
- Use "satisfies" when a design element clearly satisfies a requirement's specifications
- Use "realizes" for general manifestation where the design element embodies the requirement concept
- Only identify relationships that make logical sense based on the element information and traceability matrix context. If you are not sure about the relationship type, use "realizes" as the default relationship type.

For each relationship found, provide:
- source_id: ID of the requirement. Use the reference_id of the requirement.
- target_id: ID of the design element. Use the reference_id of the design element.
- relationship_type: MUST be one of: "satisfies", "realizes"

**CRITICAL INSTRUCTIONS:**
- For every relationship in the traceability matrix, the source_id and target_id MUST exactly match the reference_id field from the extracted requirements or design elements. If you cannot find a valid reference_id, SKIP that relationship.
- Do NOT use class names, section titles, or any other label as an ID. Only use the reference_id from the extracted elements.
- If you cannot confidently map a matrix entry to a valid reference_id, SKIP that relationship.

NOTES:
- The existing traceability matrix is extracted from SDD documentations first.
- The requirements are extracted from SRS documentations. The design elements are extracted from SRS and SDD documentations. The design elements found in SRS are usually the initial design elements produced from the requirements analysis and modelling.
- The output (the relationships between requirements and design elements) will be used to create a traceability map (requirements <-> design elements, design elements <-> design elements, design elements <-> code components). 
- The traceability map will be used to track code changes impact to the documentation and will be used to generate documentation update recommendations.
- This step only produces the relationships between requirements and design elements.
- Because this is requirements-to-design element mapping, you can know which traceability matrix entries are used to identify the relationships between requirements and design elements by checking the source_id which is a requirement reference_id.
- Requirements-to-design element mapping could be many-to-many.

The response will be automatically structured."""
    
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
        return """You are an expert software architect analyzing the relationships between design elements and code components. 

TASK:
1. You will be given a list of design elements, a list of code files, and a traceability matrix that shows existing relationships between design elements .
2. Analyze and identify the code components that are related to the design elements by checking the code component names, paths, and content against the design elements names, descriptions, and types.
3. Make sure your identified relationships are meaningful and logical based on the given context.
4. If no meaningful relationships exist, return an empty array.

For Design Element to Code Component (D→C) relationships, use ONLY these relationship types:
- implements: Code component implements the design element (reverse of C→D implements)
- realizes: Code component realizes/materializes the design concept (general manifestation relationship)

Selection Guidelines:
- Use "implements" when code provides direct implementation of the design element's specification
- Use "realizes" for general manifestation where code embodies the design concept
- Only identify relationships that make logical sense based on the element and code component information. If you are not sure about the relationship type, use "realizes" as the default relationship type.

For each relationship found, provide:
- source_id: ID of the design element. Use the reference_id of the design element.
- target_id: ID of the code component. Use the id of the code component.
- relationship_type: MUST be one of: "implements", "realizes"

NOTES:
- The design elements are extracted from SRS and SDD documentations. The design elements found in SRS are usually the initial design elements produced from the requirements analysis.
- The code components are extracted from the codebase using repomix. So, the code file content would be stripped and only shows the important signature of the code component.
- The output (the relationships between design elements and code components) will be used to create a traceability map (requirements <-> design elements, design elements <-> design elements, design elements <-> code components). 
- The traceability map will be used to track code changes impact to the documentation and will be used to generate documentation update recommendations.
- This step only produces the relationships between design elements and code components.
- Design-to-code mapping could be many-to-many.

The response will be automatically structured."""
    
    @staticmethod
    def design_code_links_human_prompt(elements_data: List[Dict[str, Any]], 
                                     components_data: List[Dict[str, Any]], 
                                     design_to_design_links: List[Dict[str, Any]]) -> str:
        """Human prompt for design-to-code link analysis"""
        return f"""Analyze the following design elements and code components to identify meaningful relationships between them:

Design Elements:
{json.dumps(elements_data, indent=2)}

Code Components:
{json.dumps(components_data, indent=2)}

Traceability Matrix Between Design Elements (for context):
{json.dumps(design_to_design_links, indent=2)}

Identify relationships between design elements and code components and return them as a JSON array.""" 