# docureco

Docureco is an AI-powered GitHub Action that analyzes code changes and provides recommendations for updating the Software Requirements Specification (SRS) and Software Design Document (SDD).

## Tech Stack
- Python 3.x
- LangChain / LangGraph
- PostgreSQL
- Repomix
- GitHub Actions

## Setup
1. Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```
2. Install dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. Configure PostgreSQL database and ensure `DATABASE_URL` in your `.env` is correct.

## Local Usage
Run the agent locally to see recommendations based on the current working directory:
```bash
python -m docureco.main
```

## GitHub Action
A workflow is provided at `.github/workflows/agent.yml` that triggers on pull requests and posts recommendations as part of the CI process.