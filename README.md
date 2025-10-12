# Perplexity Lead Enrichment Tool

This project streamlines a manual enrichment workflow built around Perplexity.ai and now automates post-call follow ups. It pulls unenriched leads from Odoo, builds a structured prompt you can paste into Perplexity, parses the AI response back into Odoo, generates personalized follow-up emails for Apollo leads you could not reach by phone, and captures answered-call summaries right back into Odoo.

## Features
- Generate rich, context-aware prompts for Perplexity based on the latest unenriched Odoo leads.
- Parse Perplexity output into structured data that matches the original lead list.
- Push enriched details (LinkedIn, job title, company data, quality score) back to Odoo with a single command.
- Produce tailored Apollo follow-up emails for unanswered calls that merge call outcomes with live Odoo context and a proposed meeting slot.
- Capture answered-call Maqsam transcriptions as internal Odoo notes after a quick confirmation step.
- Diagnose lost opportunities by combining Odoo chatter and email threads, then generate LLM-powered re-engagement plans.
- Lightweight FastAPI backend that exposes the same generate/parse actions for custom front-ends.

## Prerequisites
- Python 3.8+
- Access to your Odoo instance with API credentials
- Apollo API access token (for the missed-call follow-up workflow)
- Optional: Node.js if you plan to run the existing React front-end

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in Odoo, Apollo, and follow-up defaults inside .env
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

### 3. Automate post-first-contact workflow
```bash
python post_contact_automation.py --limit 5
```
- Presents a personalized email for no-answer calls and lets you confirm before dispatch.
- Pulls Maqsam transcriptions for answered calls and uploads them as internal notes after a confirmation prompt.
- Use `--lookback-hours` to scope the Apollo query window (defaults to the value in `.env`).
- Add `--yes` to auto-approve all suggested actions (useful for scripted runs).

### 4. Generate Apollo follow-up emails
```bash
python apollo_followup.py --limit 5
```
- `--limit` caps the number of emails produced (defaults to 10).
- `--lookback-hours` filters for calls placed within the last N hours (defaults to the value in `.env`).
- Add `--json` for machine-readable output.

The script fetches "no answer" calls from Apollo, matches each contact to their Odoo lead, and produces a personalized email based on Odoo notes, stage, and your configured value proposition.

### 5. Analyse a lost lead
```bash
curl -X POST "http://localhost:8000/lost-leads/{lead_id}/analysis"   -H "Content-Type: application/json"   -d '{"max_internal_notes": 6, "max_emails": 4}'
```
- Replace `{lead_id}` with the Odoo opportunity ID you want to review.
- Optional `max_internal_notes` and `max_emails` let you control how much chatter and email context is fed to the LLM.
- The response contains the lead details, the structured analysis, and the snippets that were provided to the model.

Use `GET /lost-leads?limit=20` to discover recently closed/lost opportunities before analysing a specific record.

## Web Interface
- Start the FastAPI backend (`uvicorn api.main:app --reload --host 127.0.0.1 --port 8000`) and the React dev server (`npm start` inside `frontend/`).
- Open `http://localhost:3000/post-contact` to review the **Post-Contact Automation** tab. Each card previews the email or internal note that will be sent and requires a manual confirmation.
- Open `http://localhost:3000/lost-leads` to diagnose closed/lost opportunities. The page lists recent deals, lets you trigger an LLM review, and surfaces the plan alongside the notes and email snippets used.
- The existing tabs still cover Perplexity prompt generation, Apollo follow-ups, lead overview, and configuration.

### Alternative Scripts
`perplexity_enrichment.py` and `perplexity_enrichment_simple.py` offer the same workflow with slightly different console formatting. They share the same underlying `PerplexityWorkflow` logic.

## FastAPI Backend
Launch the API with uvicorn:
```bash
uvicorn api.main:app --reload
```
Endpoints:
- `GET /health` - health check
- `POST /perplexity/generate` - returns the prompt plus a minimal lead preview list
- `POST /perplexity/parse` - accepts raw Perplexity output and (optionally) updates Odoo

## Configuration Reference
`Config` reads the following values from `.env`:

### Odoo
- `ODOO_URL`
- `ODOO_DB`
- `ODOO_USERNAME`
- `ODOO_PASSWORD`
- `ODOO_INSECURE_SSL` (set to `0` to enforce SSL verification)
- `SALESPERSON_NAME` (filter leads to a specific owner)

### Apollo follow-up
- `APOLLO_API_KEY`
- `APOLLO_BASE_URL` (default `https://api.apollo.io/v1`)
- `APOLLO_NO_ANSWER_DISPOSITIONS` (comma-delimited list, default `no answer,missed`)
- `APOLLO_PAGE_SIZE`
- `APOLLO_MAX_PAGES`
- `APOLLO_LOOKBACK_HOURS`
- `APOLLO_API_KEY_IN_BODY` (`1` to include `api_key` in request payloads for legacy endpoints)

### Email personalization
- `FOLLOWUP_VALUE_PROP` (text inserted into each email - `{company}` will be replaced when available)
- `FOLLOWUP_CALENDAR_LINK` (optional link shared in CTA)
- `FOLLOWUP_SENDER_TITLE`
- `FOLLOWUP_SENDER_EMAIL`
- `FOLLOWUP_PROPOSED_SLOT` (sentence fragment that proposes a meeting time and appears above the CTA link)

### Post-contact automation
- `POST_CONTACT_MAX_CALLS` (default cap on combined email/note actions fetched per run)
- `POST_CONTACT_LOOKBACK_HOURS` (window for scanning Apollo calls)

### OpenAI / LLM
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (defaults to `gpt-4o-mini`)
- `OPENAI_API_BASE` (defaults to `https://api.openai.com/v1`)

### Lost lead analysis
- `LOST_LEAD_MAX_NOTES` (number of internal notes to include per analysis)
- `LOST_LEAD_MAX_EMAILS` (number of customer emails to include per analysis)
- `LOST_LEAD_ANALYSIS_SUMMARY_LENGTH` (token budget for the LLM response)

### Maqsam transcription service
- `MAQSAM_API_KEY`
- `MAQSAM_BASE_URL` (defaults to `https://api.maqsam.com`)
- `MAQSAM_TIMEOUT`
- `MAQSAM_CALL_ID_KEYS` (comma-delimited call id fields to probe within Apollo payloads)

### SMTP delivery (optional)
- `EMAIL_SMTP_HOST`
- `EMAIL_SMTP_PORT`
- `EMAIL_SMTP_USERNAME`
- `EMAIL_SMTP_PASSWORD`
- `EMAIL_FROM_ADDRESS`
- `EMAIL_SMTP_USE_TLS`

## Legacy Automation Code
All internal web scraping, LinkedIn enrichment, and Google Sheets automation has been removed. The project now focuses exclusively on the Perplexity-assisted flow plus the Apollo follow-up workflow described above.
