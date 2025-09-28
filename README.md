# Perplexity Lead Enrichment Tool

This project streamlines a manual enrichment workflow built around Perplexity.ai. It pulls unenriched leads from Odoo, builds a structured prompt you can paste into Perplexity, and parses the AI response back into Odoo once you paste the results.

## Features
- Generate rich, context-aware prompts for Perplexity based on the latest unenriched Odoo leads.
- Parse Perplexity output into structured data that matches the original lead list.
- Push enriched details (LinkedIn, job title, company data, quality score) back to Odoo with a single command.
- Lightweight FastAPI backend that exposes the same generate/parse actions for custom front-ends.

## Prerequisites
- Python 3.8+
- Access to your Odoo instance with API credentials
- Optional: Node.js if you plan to run the existing React front-end

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in Odoo credentials inside .env
```

## CLI Usage
Run all commands from the project root.

### 1. Generate a Perplexity prompt
```bash
python main.py generate --output prompt.txt
```
This fetches unenriched leads, creates an optimized prompt, and writes it to `prompt.txt`. Paste the prompt into [https://perplexity.ai](https://perplexity.ai) and run the search.

### 2. Parse Perplexity results and update Odoo
Save Perplexity's answer to a text file, then run:
```bash
python main.py parse results.txt --preview
```
- `--preview` shows a quick summary of what was parsed.
- Add `--no-update` if you only want to check the parsing without touching Odoo.

### Alternative Scripts
`perplexity_enrichment.py` and `perplexity_enrichment_simple.py` offer the same workflow with slightly different console formatting. They share the same underlying `PerplexityWorkflow` logic.

## FastAPI Backend
Launch the API with uvicorn:
```bash
uvicorn api.main:app --reload
```
Endpoints:
- `GET /health` – health check
- `POST /perplexity/generate` – returns the prompt plus a minimal lead preview list
- `POST /perplexity/parse` – accepts raw Perplexity output and (optionally) updates Odoo

## Configuration Reference
`Config` now only reads the values that are required for the manual workflow:
- `ODOO_URL`
- `ODOO_DB`
- `ODOO_USERNAME`
- `ODOO_PASSWORD`
- `ODOO_INSECURE_SSL` (set to `0` to enforce SSL verification)
- `SALESPERSON_NAME` (filter leads to a specific owner)

## Legacy Automation Code
All internal web scraping, LinkedIn enrichment, and Google Sheets automation has been removed. The project now focuses exclusively on the Perplexity-assisted flow described above.
