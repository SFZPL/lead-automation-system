#!/usr/bin/env python3
"""FastAPI backend exposing only Perplexity-based enrichment helpers."""

import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from modules.logger import setup_logging
from modules.perplexity_workflow import PerplexityWorkflow

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Perplexity Lead Enrichment API",
    description="Generate Perplexity prompts and push parsed results back to Odoo.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:3000', 'http://localhost:3002', 'http://127.0.0.1:3000', 'http://127.0.0.1:3002'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


def get_workflow() -> PerplexityWorkflow:
    config = Config()
    setup_logging(config, "INFO")
    return PerplexityWorkflow(config)


class LeadPreview(BaseModel):
    id: int
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    email: Optional[str] = None
    linkedin: Optional[str] = None


class GenerateResponse(BaseModel):
    prompt: str
    lead_count: int
    leads: List[LeadPreview]


class ParseRequest(BaseModel):
    results_text: str
    update: bool = True


class ParseResponse(BaseModel):
    parsed_count: int
    updated: int
    failed: int
    errors: List[str]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/perplexity/generate", response_model=GenerateResponse)
def generate_prompt() -> GenerateResponse:
    workflow = get_workflow()

    prompt, leads = workflow.generate_enrichment_prompt()

    if not leads:
        raise HTTPException(status_code=404, detail="No unenriched leads found")

    previews = [
        LeadPreview(
            id=lead.get("id"),
            full_name=lead.get("Full Name") or lead.get("name"),
            company_name=lead.get("Company Name") or lead.get("partner_name"),
            email=lead.get("email"),
            linkedin=lead.get("LinkedIn Link"),
        )
        for lead in leads
        if lead.get("id") is not None
    ]

    return GenerateResponse(prompt=prompt, lead_count=len(leads), leads=previews)


@app.post("/perplexity/parse", response_model=ParseResponse)
def parse_results(payload: ParseRequest) -> ParseResponse:
    workflow = get_workflow()

    _, original_leads = workflow.generate_enrichment_prompt()
    if not original_leads:
        raise HTTPException(status_code=409, detail="No leads available to reconcile the results against")

    enriched = workflow.parse_perplexity_results(payload.results_text, original_leads)
    if not enriched:
        raise HTTPException(status_code=422, detail="Unable to parse Perplexity response")

    updated = 0
    failed = 0
    errors: List[str] = []

    if payload.update:
        outcome = workflow.update_leads_in_odoo(enriched)
        if not outcome.get("success", False):
            raise HTTPException(status_code=500, detail=outcome.get("error", "Unknown error"))
        updated = outcome.get("updated", 0)
        failed = outcome.get("failed", 0)
        errors = outcome.get("errors", [])

    return ParseResponse(
        parsed_count=len(enriched),
        updated=updated,
        failed=failed,
        errors=errors,
    )
