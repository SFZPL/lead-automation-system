# Knowledge Base PDFs

Place your company PDF documents in this folder. They will be automatically loaded into the knowledge base when you run:

```bash
python scripts/seed_knowledge_base.py
```

## What to include

Add PDFs containing information about:
- Company overview and services
- Product/service descriptions
- Case studies
- Value propositions
- Pricing information
- Common objection responses
- Any other context that helps AI make better recommendations

## File naming

Use descriptive filenames:
- `prezlab_company_overview.pdf`
- `service_catalog.pdf`
- `case_studies.pdf`

## Usage

1. Add PDF files to this folder
2. Commit them to git
3. Run `python scripts/seed_knowledge_base.py` to upload them to Supabase
4. The AI will automatically use this context in analyses

The script skips files that are already uploaded, so you can run it multiple times safely.
