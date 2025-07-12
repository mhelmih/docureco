# Docureco Agent

Document-Code Traceability Analysis Agent with modular workflow architecture.

## 🏗️ Architecture

The agent is organized into three main workflow packages, each with a consistent structure:

```
agent/
├── baseline_map_creator/          # Create baseline traceability maps
│   ├── __init__.py               # Package exports
│   ├── main.py                   # CLI entry point
│   ├── workflow.py               # LangGraph workflow implementation
│   └── prompts.py                # LLM prompts for this workflow
├── baseline_map_updater/          # Update existing traceability maps
│   ├── __init__.py               # Package exports
│   ├── main.py                   # CLI entry point
│   ├── workflow.py               # LangGraph workflow implementation
│   └── prompts.py                # LLM prompts for this workflow
├── document_update_recommender/   # Recommend documentation updates
│   ├── __init__.py               # Package exports
│   ├── main.py                   # CLI entry point
│   ├── workflow.py               # LangGraph workflow implementation
│   └── prompts.py                # LLM prompts for this workflow
├── config/                        # Configuration management
├── database/                      # Database access layer
├── llm/                          # LLM client implementations
├── models/                       # Data models
├── main.py                       # Main dispatcher
└── __init__.py                   # Agent package exports
```

## 🚀 Usage

### Main Dispatcher

Use the main dispatcher to run any workflow:

```bash
# Create baseline traceability map
python -m agent baseline-map-creator owner/repo --branch main

# Update existing traceability map
python -m agent baseline-map-updater owner/repo --since 2024-01-01

# Get documentation update recommendations
python -m agent document-update-recommender owner/repo --output recommendations.md
```

### Direct Workflow Execution

You can also run workflows directly:

```bash
# Run baseline map creator directly
python -m agent.baseline_map_creator owner/repo --branch main --force

# Run baseline map updater directly
python -m agent.baseline_map_updater owner/repo --since HEAD~5

# Run document update recommender directly
python -m agent.document_update_recommender owner/repo --format json --output results.json
```

## 📋 Workflows

### 1. Baseline Map Creator

**Purpose**: Creates initial traceability maps from repository documentation and code.

**Key Features**:
- SDD-first analysis with traceability matrix extraction
- Requirements extraction from SRS with design element context
- Precise relationship type enforcement (implements, satisfies, refines, realizes, depends_on)
- Fail-fast error handling with no fallbacks
- Repomix integration for efficient repository scanning

**Usage**:
```bash
python -m agent baseline-map-creator owner/repo \
  --branch main \
  --force \
  --log-level DEBUG
```

### 2. Baseline Map Updater

**Purpose**: Updates existing traceability maps when repository changes occur.

**Key Features**:
- Change impact analysis
- Incremental vs full recreation strategies
- Smart update prioritization
- Relationship consistency maintenance

**Usage**:
```bash
python -m agent baseline-map-updater owner/repo \
  --branch main \
  --since 2024-01-01 \
  --log-level INFO
```

### 3. Document Update Recommender

**Purpose**: Recommends documentation updates based on code changes and traceability analysis.

**Key Features**:
- Code change impact analysis
- Prioritized recommendations
- Multiple output formats (JSON, Markdown, Text)
- Quality assessment
- Actionable suggestions

**Usage**:
```bash
python -m agent document-update-recommender owner/repo \
  --branch main \
  --since HEAD~10 \
  --output recommendations.md \
  --format markdown
```

## 🔧 Configuration

Each workflow uses shared configuration from:
- `config/llm_config.py` - LLM client configuration
- Environment variables for API keys and settings
- `config.env.example` - Example environment configuration

## 🏛️ Architecture Benefits

### 1. **Modularity**
- Each workflow is self-contained
- Independent development and testing
- Clear separation of concerns

### 2. **Consistency**
- Uniform structure across all workflows
- Consistent CLI interfaces
- Standardized prompt management

### 3. **Maintainability**
- Easy to add new workflows
- Isolated changes don't affect other workflows
- Clear code organization

### 4. **Scalability**
- Workflows can be deployed independently
- Easy to parallelize execution
- Microservice-ready architecture

### 5. **Developer Experience**
- Clear entry points for each workflow
- Comprehensive CLI help
- Consistent error handling

## 🔗 Relationship Types

The agent uses academically precise relationship types:

### Design Element ↔ Design Element (D→D)
- **refines**: Elaborates or clarifies another element
- **realizes**: Manifests or embodies another element
- **depends_on**: Requires another element to function

### Requirement ↔ Design Element (R→D)
- **satisfies**: Design element fulfills requirement specifications
- **realizes**: Design element embodies requirement concept

### Design Element ↔ Code Component (D→C)
- **implements**: Code provides direct implementation
- **realizes**: Code embodies design concept

## 📊 Data Models

All workflows use shared data models from `models/docureco_models.py`:
- `BaselineMapModel` - Complete traceability map
- `RequirementModel` - Software requirements
- `DesignElementModel` - Design artifacts
- `CodeComponentModel` - Code components
- `TraceabilityLinkModel` - Relationships between artifacts

## 🛠️ Development

### Adding New Workflows

1. Create new package directory: `agent/new_workflow/`
2. Implement the four core files:
   - `__init__.py` - Package exports
   - `main.py` - CLI entry point
   - `workflow.py` - LangGraph workflow
   - `prompts.py` - LLM prompts
3. Update `agent/__init__.py` to export the new workflow
4. Update `agent/main.py` to include the new workflow in the dispatcher

### Testing

Each workflow can be tested independently:
```bash
# Test specific workflow
python -m pytest agent/baseline_map_creator/tests/

# Test all workflows
python -m pytest agent/
```

## 📈 Performance

- **Repomix Integration**: Fast repository scanning without API rate limits
- **Parallel Processing**: Multiple LLM calls can run concurrently
- **Efficient Prompts**: Optimized prompts reduce token usage
- **Fail-Fast**: Quick error detection prevents wasted processing

## 🔒 Security

- Environment-based configuration
- No hardcoded secrets
- Secure database connections
- Input validation and sanitization

---

*Docureco Agent - Making documentation and code traceability effortless* 🚀 