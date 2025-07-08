-- Migration: Remove all embedding-related functionality
-- Removes vector embeddings as they are not needed for traceability-based impact analysis
-- The new approach uses direct traceability links instead of semantic search

-- Drop vector search functions if they exist
DROP FUNCTION IF EXISTS public.search_requirements_by_vector(vector, float, integer);
DROP FUNCTION IF EXISTS public.search_design_elements_by_vector(vector, float, integer);
DROP FUNCTION IF EXISTS public.search_code_components_by_vector(vector, float, integer);

-- Drop vector indexes if they exist
DROP INDEX IF EXISTS idx_requirements_title_embedding;
DROP INDEX IF EXISTS idx_requirements_description_embedding;
DROP INDEX IF EXISTS idx_requirements_combined_embedding;
DROP INDEX IF EXISTS idx_design_elements_name_embedding;
DROP INDEX IF EXISTS idx_design_elements_description_embedding;
DROP INDEX IF EXISTS idx_design_elements_combined_embedding;
DROP INDEX IF EXISTS idx_code_components_path_embedding;
DROP INDEX IF EXISTS idx_code_components_name_embedding;

-- Remove embedding columns from requirements table
ALTER TABLE public.requirements 
DROP COLUMN IF EXISTS title_embedding,
DROP COLUMN IF EXISTS description_embedding,
DROP COLUMN IF EXISTS combined_embedding;

-- Remove embedding columns from design_elements table
ALTER TABLE public.design_elements
DROP COLUMN IF EXISTS name_embedding,
DROP COLUMN IF EXISTS description_embedding,
DROP COLUMN IF EXISTS combined_embedding;

-- Remove embedding columns from code_components table
ALTER TABLE public.code_components
DROP COLUMN IF EXISTS path_embedding,
DROP COLUMN IF EXISTS name_embedding;

-- Remove pgvector extension if it exists and no other tables are using it
-- Note: Be careful with this in production, only run if you're sure no other tables use vector columns
-- DROP EXTENSION IF EXISTS vector; 