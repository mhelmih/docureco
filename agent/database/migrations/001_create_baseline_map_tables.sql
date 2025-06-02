-- Docureco Database Schema Migration
-- Creates tables for baseline traceability map storage

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Main baseline maps table
CREATE TABLE IF NOT EXISTS baseline_maps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repository TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Ensure unique baseline map per repository/branch
    UNIQUE(repository, branch)
);

-- Requirements table
CREATE TABLE IF NOT EXISTS requirements (
    id TEXT NOT NULL,
    baseline_map_id UUID NOT NULL REFERENCES baseline_maps(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    type TEXT NOT NULL, -- 'Functional' or 'Non-functional'
    priority TEXT NOT NULL DEFAULT 'Medium', -- 'High', 'Medium', 'Low'
    section TEXT NOT NULL, -- SRS section reference
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (id, baseline_map_id)
);

-- Design elements table
CREATE TABLE IF NOT EXISTS design_elements (
    id TEXT NOT NULL,
    baseline_map_id UUID NOT NULL REFERENCES baseline_maps(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    type TEXT NOT NULL, -- 'Class', 'Module', 'Component', 'Interface', etc.
    section TEXT NOT NULL, -- SDD section reference
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (id, baseline_map_id)
);

-- Code components table
CREATE TABLE IF NOT EXISTS code_components (
    id TEXT NOT NULL,
    baseline_map_id UUID NOT NULL REFERENCES baseline_maps(id) ON DELETE CASCADE,
    path TEXT NOT NULL, -- File path or component path
    type TEXT NOT NULL, -- 'File', 'Class', 'Function', 'Method', etc.
    name TEXT, -- Component name if applicable (class name, function name)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (id, baseline_map_id)
);

-- Traceability links table
CREATE TABLE IF NOT EXISTS traceability_links (
    id TEXT NOT NULL,
    baseline_map_id UUID NOT NULL REFERENCES baseline_maps(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL, -- 'Requirement', 'DesignElement', 'CodeComponent'
    source_id TEXT NOT NULL,
    target_type TEXT NOT NULL, -- 'Requirement', 'DesignElement', 'CodeComponent'
    target_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL, -- 'implements', 'realizes', 'depends_on', 'contains', etc.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (id, baseline_map_id)
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_baseline_maps_repository ON baseline_maps(repository);
CREATE INDEX IF NOT EXISTS idx_baseline_maps_repository_branch ON baseline_maps(repository, branch);
CREATE INDEX IF NOT EXISTS idx_baseline_maps_updated_at ON baseline_maps(updated_at);

CREATE INDEX IF NOT EXISTS idx_requirements_baseline_map_id ON requirements(baseline_map_id);
CREATE INDEX IF NOT EXISTS idx_requirements_type ON requirements(type);
CREATE INDEX IF NOT EXISTS idx_requirements_priority ON requirements(priority);

CREATE INDEX IF NOT EXISTS idx_design_elements_baseline_map_id ON design_elements(baseline_map_id);
CREATE INDEX IF NOT EXISTS idx_design_elements_type ON design_elements(type);

CREATE INDEX IF NOT EXISTS idx_code_components_baseline_map_id ON code_components(baseline_map_id);
CREATE INDEX IF NOT EXISTS idx_code_components_path ON code_components(path);
CREATE INDEX IF NOT EXISTS idx_code_components_type ON code_components(type);

CREATE INDEX IF NOT EXISTS idx_traceability_links_baseline_map_id ON traceability_links(baseline_map_id);
CREATE INDEX IF NOT EXISTS idx_traceability_links_source ON traceability_links(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_traceability_links_target ON traceability_links(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_traceability_links_relationship ON traceability_links(relationship_type);

-- Function to update updated_at column automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers to automatically update updated_at
CREATE TRIGGER update_baseline_maps_updated_at 
    BEFORE UPDATE ON baseline_maps 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_requirements_updated_at 
    BEFORE UPDATE ON requirements 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_design_elements_updated_at 
    BEFORE UPDATE ON design_elements 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_code_components_updated_at 
    BEFORE UPDATE ON code_components 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_traceability_links_updated_at 
    BEFORE UPDATE ON traceability_links 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Row Level Security (RLS) policies for Supabase
ALTER TABLE baseline_maps ENABLE ROW LEVEL SECURITY;
ALTER TABLE requirements ENABLE ROW LEVEL SECURITY;
ALTER TABLE design_elements ENABLE ROW LEVEL SECURITY;
ALTER TABLE code_components ENABLE ROW LEVEL SECURITY;
ALTER TABLE traceability_links ENABLE ROW LEVEL SECURITY;

-- Policy to allow service role full access (for Docureco agent operations)
-- Note: In production, you might want more restrictive policies
CREATE POLICY "Allow service role full access on baseline_maps" ON baseline_maps
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Allow service role full access on requirements" ON requirements
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Allow service role full access on design_elements" ON design_elements
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Allow service role full access on code_components" ON code_components
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Allow service role full access on traceability_links" ON traceability_links
    FOR ALL USING (auth.role() = 'service_role');

-- Optional: Allow authenticated users read-only access to baseline maps
-- Uncomment these if you want to provide read-only access through Supabase dashboard
/*
CREATE POLICY "Allow authenticated read access on baseline_maps" ON baseline_maps
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Allow authenticated read access on requirements" ON requirements
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Allow authenticated read access on design_elements" ON design_elements
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Allow authenticated read access on code_components" ON code_components
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Allow authenticated read access on traceability_links" ON traceability_links
    FOR SELECT USING (auth.role() = 'authenticated');
*/

-- Insert some example data for testing (optional)
/*
INSERT INTO baseline_maps (repository, branch) VALUES ('mhelmih/docureco', 'main');

INSERT INTO requirements (id, baseline_map_id, title, description, type, priority, section) 
SELECT 'REQ-001', id, 'User Authentication', 'System must authenticate users', 'Functional', 'High', '3.1.1'
FROM baseline_maps WHERE repository = 'mhelmih/docureco' AND branch = 'main';

INSERT INTO design_elements (id, baseline_map_id, name, description, type, section)
SELECT 'DE-001', id, 'AuthService', 'Authentication service class', 'Class', '4.2.1'
FROM baseline_maps WHERE repository = 'mhelmih/docureco' AND branch = 'main';

INSERT INTO code_components (id, baseline_map_id, path, type, name)
SELECT 'CC-001', id, 'src/auth/AuthService.java', 'Class', 'AuthService'
FROM baseline_maps WHERE repository = 'mhelmih/docureco' AND branch = 'main';

INSERT INTO traceability_links (id, baseline_map_id, source_type, source_id, target_type, target_id, relationship_type)
SELECT 'TL-001', id, 'Requirement', 'REQ-001', 'DesignElement', 'DE-001', 'implements'
FROM baseline_maps WHERE repository = 'mhelmih/docureco' AND branch = 'main';

INSERT INTO traceability_links (id, baseline_map_id, source_type, source_id, target_type, target_id, relationship_type)
SELECT 'TL-002', id, 'DesignElement', 'DE-001', 'CodeComponent', 'CC-001', 'realizes'
FROM baseline_maps WHERE repository = 'mhelmih/docureco' AND branch = 'main';
*/ 