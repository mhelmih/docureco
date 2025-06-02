-- Vector Embeddings Enhancement for Docureco Database
-- Adds vector embeddings for semantic search capabilities

-- Enable pgvector extension for vector operations
CREATE EXTENSION IF NOT EXISTS vector;

-- Add vector columns to requirements table
ALTER TABLE requirements 
ADD COLUMN IF NOT EXISTS title_embedding vector(1536),
ADD COLUMN IF NOT EXISTS description_embedding vector(1536),
ADD COLUMN IF NOT EXISTS combined_embedding vector(1536);

-- Add vector columns to design elements table  
ALTER TABLE design_elements
ADD COLUMN IF NOT EXISTS name_embedding vector(1536),
ADD COLUMN IF NOT EXISTS description_embedding vector(1536),
ADD COLUMN IF NOT EXISTS combined_embedding vector(1536);

-- Add vector columns to code components table
ALTER TABLE code_components
ADD COLUMN IF NOT EXISTS path_embedding vector(1536),
ADD COLUMN IF NOT EXISTS name_embedding vector(1536);

-- Create indexes for efficient vector similarity search
CREATE INDEX IF NOT EXISTS idx_requirements_title_embedding 
ON requirements USING ivfflat (title_embedding vector_cosine_ops) 
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_requirements_description_embedding 
ON requirements USING ivfflat (description_embedding vector_cosine_ops) 
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_requirements_combined_embedding 
ON requirements USING ivfflat (combined_embedding vector_cosine_ops) 
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_design_elements_name_embedding 
ON design_elements USING ivfflat (name_embedding vector_cosine_ops) 
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_design_elements_description_embedding 
ON design_elements USING ivfflat (description_embedding vector_cosine_ops) 
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_design_elements_combined_embedding 
ON design_elements USING ivfflat (combined_embedding vector_cosine_ops) 
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_code_components_path_embedding 
ON code_components USING ivfflat (path_embedding vector_cosine_ops) 
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_code_components_name_embedding 
ON code_components USING ivfflat (name_embedding vector_cosine_ops) 
WITH (lists = 100);

-- Function to find similar requirements by vector similarity
CREATE OR REPLACE FUNCTION find_similar_requirements(
    query_embedding vector(1536),
    similarity_threshold float DEFAULT 0.7,
    max_results int DEFAULT 10,
    target_baseline_map_id uuid DEFAULT NULL
)
RETURNS TABLE (
    id text,
    title text,
    description text,
    similarity float
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        r.id,
        r.title,
        r.description,
        1 - (r.combined_embedding <=> query_embedding) AS similarity
    FROM requirements r
    WHERE 
        (target_baseline_map_id IS NULL OR r.baseline_map_id = target_baseline_map_id)
        AND r.combined_embedding IS NOT NULL
        AND (1 - (r.combined_embedding <=> query_embedding)) >= similarity_threshold
    ORDER BY r.combined_embedding <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- Function to find similar design elements by vector similarity
CREATE OR REPLACE FUNCTION find_similar_design_elements(
    query_embedding vector(1536),
    similarity_threshold float DEFAULT 0.7,
    max_results int DEFAULT 10,
    target_baseline_map_id uuid DEFAULT NULL
)
RETURNS TABLE (
    id text,
    name text,
    description text,
    similarity float
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        de.id,
        de.name,
        de.description,
        1 - (de.combined_embedding <=> query_embedding) AS similarity
    FROM design_elements de
    WHERE 
        (target_baseline_map_id IS NULL OR de.baseline_map_id = target_baseline_map_id)
        AND de.combined_embedding IS NOT NULL
        AND (1 - (de.combined_embedding <=> query_embedding)) >= similarity_threshold
    ORDER BY de.combined_embedding <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- Function to find similar code components by vector similarity
CREATE OR REPLACE FUNCTION find_similar_code_components(
    query_embedding vector(1536),
    similarity_threshold float DEFAULT 0.7,
    max_results int DEFAULT 10,
    target_baseline_map_id uuid DEFAULT NULL
)
RETURNS TABLE (
    id text,
    path text,
    name text,
    similarity float
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        cc.id,
        cc.path,
        cc.name,
        1 - (COALESCE(cc.name_embedding, cc.path_embedding) <=> query_embedding) AS similarity
    FROM code_components cc
    WHERE 
        (target_baseline_map_id IS NULL OR cc.baseline_map_id = target_baseline_map_id)
        AND (cc.name_embedding IS NOT NULL OR cc.path_embedding IS NOT NULL)
        AND (1 - (COALESCE(cc.name_embedding, cc.path_embedding) <=> query_embedding)) >= similarity_threshold
    ORDER BY COALESCE(cc.name_embedding, cc.path_embedding) <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- Update RLS policies to include vector columns
-- (Existing policies already cover these columns since they use FOR ALL)

-- Comments for documentation
COMMENT ON COLUMN requirements.title_embedding IS 'Vector embedding of requirement title for semantic search';
COMMENT ON COLUMN requirements.description_embedding IS 'Vector embedding of requirement description for semantic search';
COMMENT ON COLUMN requirements.combined_embedding IS 'Vector embedding of combined title + description for semantic search';
COMMENT ON COLUMN design_elements.name_embedding IS 'Vector embedding of design element name for semantic search';
COMMENT ON COLUMN design_elements.description_embedding IS 'Vector embedding of design element description for semantic search';
COMMENT ON COLUMN design_elements.combined_embedding IS 'Vector embedding of combined name + description for semantic search';
COMMENT ON COLUMN code_components.path_embedding IS 'Vector embedding of code component path for semantic search';
COMMENT ON COLUMN code_components.name_embedding IS 'Vector embedding of code component name for semantic search';

-- Note: Vector embeddings should be generated using OpenAI text-embedding-3-small (1536 dimensions)
-- or similar embedding model and inserted via the application layer 