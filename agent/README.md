# Docureco Agent

Document Update Recommendator - AI Agent untuk analisis otomatis perubahan dokumentasi SRS dan SDD berdasarkan perubahan kode dalam GitHub Pull Requests.

## Overview

Docureco adalah agen inteligensi berbasis LLM (Large Language Model) yang dirancang untuk membantu pengembang menjaga sinkronisasi yang akurat antara kode sumber yang berevolusi dengan dokumentasi esensial, yaitu Software Requirements Specification (SRS) dan Software Design Document (SDD).

### Fitur Utama

- 🔍 **Analisis Perubahan Kode Otomatis**: Menganalisis perubahan kode dalam PR menggunakan framework 4W (What, Where, Why, How)
- 🗺️ **Traceability Mapping**: Memetakan hubungan antara kode, elemen desain, dan requirements
- 🎯 **Impact Assessment**: Menilai dampak perubahan kode terhadap dokumentasi SRS/SDD
- 📝 **Rekomendasi Cerdas**: Menghasilkan rekomendasi pembaruan dokumentasi yang spesifik dan actionable
- 🔗 **Integrasi GitHub**: Terintegrasi langsung dengan GitHub Actions dan PR workflow
- 🤖 **Powered by Grok 3**: Menggunakan Grok 3 Mini Reasoning (High) untuk analisis yang akurat

## Arsitektur

### Komponen Utama

1. **Document Update Recommendator**
   - PR Event Handler
   - Code Changes Analyzer
   - Impact Assessor
   - Recommendation Generator
   - Recommendation Poster

2. **Initial Baseline Map Creator**
   - Repo Artifact Fetcher
   - Mapping Engine
   - Map Storage Manager

3. **Baseline Map Updater**
   - Merged Changes Fetcher
   - Incremental Map Updater
   - Map Storage Manager

### Workflow

```mermaid
graph TD
    A[PR Opened/Updated] --> B[Scan PR Context]
    B --> C[Analyze Code Changes]
    C --> D[Assess Documentation Impact]
    D --> E[Generate Recommendations]
    E --> F[Post to PR & Update Status]
```

## Setup

### 1. Dependencies

Install dependencies menggunakan pip:

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

Copy file `config.env.example` dan sesuaikan konfigurasi:

```bash
cp config.env.example .env
```

#### Required Variables

```env
# LLM Configuration
GROK_API_KEY=your_grok_api_key_here
GITHUB_TOKEN=your_github_token_here

# Database (Supabase)
DATABASE_URL=postgresql://username:password@host:port/database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key_here
```

#### Optional Variables

```env
# LLM Provider (default: grok)
DOCURECO_LLM_PROVIDER=grok
DOCURECO_LLM_MODEL=grok-3-mini-reasoning-high

# OpenAI Fallback
OPENAI_API_KEY=your_openai_api_key_here

# Performance tuning
DOCURECO_LLM_TEMPERATURE=0.1
DOCURECO_LLM_MAX_TOKENS=4000
```

### 3. GitHub Actions Setup

Tambahkan secrets dan variables di repository settings:

#### Secrets
- `GROK_API_KEY`: API key untuk Grok 3
- `OPENAI_API_KEY`: API key OpenAI (fallback)
- `DATABASE_URL`: Connection string untuk database
- `SUPABASE_URL`: URL project Supabase
- `SUPABASE_SERVICE_ROLE_KEY`: Service role key Supabase

#### Variables (Optional)
- `DOCURECO_LLM_PROVIDER`: Provider LLM (default: grok)
- `DOCURECO_LLM_MODEL`: Model yang digunakan
- `LOG_LEVEL`: Level logging (default: INFO)

### 4. Repository Requirements

Untuk berfungsi optimal, repository harus memiliki:

- 📄 **Dokumen SRS** dalam format Markdown
- 📄 **Dokumen SDD** dalam format Markdown dengan traceability matrix
- 💻 **Source code** yang well-documented
- 📝 **Commit messages** yang deskriptif

## Usage

### Automatic Trigger

Docureco akan otomatis aktif ketika:
- Pull Request dibuka
- Pull Request di-update (push baru)
- Pull Request di-reopen

### Manual Trigger

Untuk membuat baseline traceability map:

1. Go to repository → Actions
2. Select "Docureco AI Agent" workflow
3. Click "Run workflow"
4. Choose branch dan jalankan

### Output

Docureco akan menghasilkan:

1. **PR Comments**: Rekomendasi pembaruan dokumentasi
2. **GitHub Checks**: Status analisis dan summary
3. **Logs**: Detail proses analisis untuk debugging

#### Contoh Output

```markdown
## 📋 Docureco Documentation Recommendations

Found **3** documentation update recommendations:

### 🟡 Recommendation 1: SDD
**Section:** DE_UserProfileModel
**Priority:** Moderate
**Action:** modify

Based on the addition of the UserProfile model, the SDD should be updated to include:
- Class diagram untuk UserProfile
- Description of data fields dan validation rules
- Integration dengan existing authentication system

---
```

## Configuration

### LLM Configuration

```python
# config/llm_config.py
class LLMConfig(BaseModel):
    provider: LLMProvider = Field(default=LLMProvider.GROK)
    model_name: str = Field(default="grok-3-mini-reasoning-high")
    temperature: float = Field(default=0.1)
    max_tokens: int = Field(default=4000)
```

### Task-Specific Settings

```python
# Berbeda temperature untuk berbagai tugas
code_analysis: temperature=0.1        # Konsisten untuk klasifikasi
traceability_mapping: temperature=0.2 # Sedikit lebih fleksibel
impact_assessment: temperature=0.15   # Balanced untuk penilaian
recommendation_generation: temperature=0.3  # Kreatif untuk text generation
```

## Development

### Project Structure

```
agent/
├── config/
│   ├── __init__.py
│   └── llm_config.py          # LLM configuration
├── llm/
│   ├── __init__.py
│   └── llm_client.py          # LLM client wrapper
├── models/
│   ├── __init__.py
│   └── docureco_models.py     # Pydantic models
├── workflows/
│   ├── __init__.py
│   └── docureco_workflow.py   # LangGraph workflow
├── main.py                    # Entry point
├── requirements.txt           # Dependencies
└── config.env.example        # Environment template
```

### Running Locally

```bash
# Set environment variables
export GROK_API_KEY="your_api_key"
export GITHUB_TOKEN="your_token"

# Run with mock PR data
python -m main
```

### Testing

```bash
# Run tests
pytest tests/

# Run with coverage
pytest tests/ --cov=agent
```

## API Reference

### Core Classes

#### DocurecoLLMClient

```python
from agent.llm import create_llm_client

client = create_llm_client()
response = await client.generate_response(
    prompt="Analyze this code change...",
    task_type="code_analysis",
    output_format="json"
)
```

#### DocurecoWorkflow

```python
from agent.workflows import create_docureco_workflow

workflow = create_docureco_workflow()
result = await workflow.execute({
    "pr_number": 123,
    "repository": "owner/repo",
    "changed_files": [...],
    "commit_messages": [...]
})
```

## Troubleshooting

### Common Issues

1. **LLM API Errors**
   ```
   Error: GROK_API_KEY not found
   Solution: Set GROK_API_KEY environment variable
   ```

2. **GitHub API Rate Limits**
   ```
   Solution: Ensure GITHUB_TOKEN has sufficient permissions
   ```

3. **Database Connection**
   ```
   Error: Connection to Supabase failed
   Solution: Verify DATABASE_URL dan SUPABASE_* variables
   ```

### Debugging

Enable debug logging:

```env
LOG_LEVEL=DEBUG
```

Check logs in GitHub Actions artifacts atau local output.

## Contributing

1. Fork repository
2. Create feature branch
3. Implement changes dengan tests
4. Update documentation
5. Submit Pull Request

## License

[MIT License](LICENSE)

## Support

Untuk pertanyaan atau issues:
- Create GitHub Issue
- Check existing documentation
- Review logs untuk error details

---

**Docureco Agent** - Keeping your documentation in sync with your code! 🚀 