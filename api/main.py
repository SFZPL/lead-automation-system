#!/usr/bin/env python3
"""FastAPI backend exposing Perplexity and Apollo follow-up helpers."""

# Force reload
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Literal

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from modules.logger import setup_logging
from modules.perplexity_workflow import PerplexityWorkflow
from modules.perplexity_client import PerplexityClient
from modules.apollo_followup import ApolloFollowUpService
from modules.post_contact_automation import PostContactAutomationService, PostContactAction
from modules.lost_lead_analyzer import LostLeadAnalyzer
from modules.proposal_followup_analyzer import ProposalFollowupAnalyzer
from modules.outlook_client import OutlookClient
from modules.email_token_store import EmailTokenStore
from modules.odoo_client import OdooClient
from api.auth import get_auth_service, get_current_user, get_database, AuthService
from api.database import Database

logger = logging.getLogger(__name__)

# In-memory cache for proposal followups analysis
proposal_followups_cache = {
    "data": None,
    "timestamp": None,
    "params": None
}

app = FastAPI(
    title="Lead Automation API",
    description="Generate Perplexity prompts, parse results, and prepare Apollo follow-up emails.",
    version="1.1.0",
)

ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:3001',
    'http://localhost:3002',
    'http://127.0.0.1:3000',
    'http://127.0.0.1:3001',
    'http://127.0.0.1:3002',
    'https://lead-automation-system.onrender.com',
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


def _setup_logging() -> Config:
    config = Config()
    setup_logging(config, "INFO")
    return config


def get_workflow() -> PerplexityWorkflow:
    config = _setup_logging()
    return PerplexityWorkflow(config)


def get_followup_service() -> ApolloFollowUpService:
    config = _setup_logging()
    return ApolloFollowUpService(config=config)


def get_post_contact_service() -> PostContactAutomationService:
    config = _setup_logging()
    return PostContactAutomationService(config=config)


def get_lost_lead_analyzer() -> LostLeadAnalyzer:
    config = _setup_logging()
    return LostLeadAnalyzer(config=config)


def _to_iso(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return None


def _serialize_call_info(call: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not call:
        return {}

    raw_call = call.get('raw_call') if isinstance(call.get('raw_call'), dict) else {}

    def _first(*keys: str) -> Optional[Any]:
        for key in keys:
            if key in call and call[key]:
                return call[key]
            if key in raw_call and raw_call[key]:
                return raw_call[key]
        return None

    result: Dict[str, Any] = {
        'id': _first('call_id', 'id'),
        'disposition': _first('call_disposition', 'disposition'),
        'duration_seconds': _first('duration_seconds', 'duration'),
        'last_called_at': _to_iso(
            _first('last_called_at_dt', 'last_called_at', 'called_at', 'updated_at')
        ),
        'notes': _first('notes', 'note'),
    }
    return {key: value for key, value in result.items() if value is not None}


def _serialize_lead_info(lead: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not lead:
        return {}
    result: Dict[str, Any] = {
        'id': lead.get('id'),
        'name': lead.get('name') or lead.get('contact_name'),
        'company': lead.get('partner_name') or lead.get('Company Name') or lead.get('company'),
        'stage_name': lead.get('stage_name'),
        'salesperson': lead.get('salesperson_name') or lead.get('Salesperson'),
        'phone': lead.get('phone') or lead.get('mobile'),
    }
    return {key: value for key, value in result.items() if value is not None}


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


class EnrichSingleLeadRequest(BaseModel):
    lead_id: int


class EnrichSingleLeadResponse(BaseModel):
    success: bool
    lead_id: int
    enriched_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class EnrichBatchRequest(BaseModel):
    lead_ids: List[int]


class EnrichedLeadResult(BaseModel):
    lead_id: int
    success: bool
    current_data: Optional[Dict[str, Any]] = None
    suggested_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class EnrichBatchResponse(BaseModel):
    total: int
    successful: int
    failed: int
    results: List[EnrichedLeadResult]


class PushApprovedRequest(BaseModel):
    approved_leads: List[Dict[str, Any]]


class PushApprovedResponse(BaseModel):
    total: int
    successful: int
    failed: int
    errors: List[str]


class FollowUpCall(BaseModel):
    id: Optional[str] = None
    disposition: Optional[str] = None
    direction: Optional[str] = None
    duration_seconds: Optional[int] = None
    last_called_at: Optional[str] = None
    notes: Optional[str] = None


class FollowUpLead(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    stage_name: Optional[str] = None
    salesperson: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None


class FollowUpItem(BaseModel):
    email: str
    subject: str
    body: str
    call: FollowUpCall
    odoo_lead: FollowUpLead


class FollowUpResponse(BaseModel):
    count: int
    items: List[FollowUpItem]


class PostContactCall(BaseModel):
    id: Optional[str] = None
    disposition: Optional[str] = None
    duration_seconds: Optional[int] = None
    last_called_at: Optional[str] = None
    notes: Optional[str] = None


class PostContactLead(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    company: Optional[str] = None
    stage_name: Optional[str] = None
    salesperson: Optional[str] = None
    phone: Optional[str] = None


class PostContactActionPayload(BaseModel):
    action_type: Literal["email", "note"]
    contact_email: str
    odoo_lead_id: int
    subject: Optional[str] = None
    body: Optional[str] = None
    note_body: Optional[str] = None
    transcription: Optional[str] = None
    call: Optional[PostContactCall] = None
    odoo_lead: Optional[PostContactLead] = None


class PostContactActionsResponse(BaseModel):
    count: int
    actions: List[PostContactActionPayload]


class ExecuteActionRequest(PostContactActionPayload):
    pass


class ExecuteActionResponse(BaseModel):
    success: bool
    message: Optional[str] = None


class LostLeadSummary(BaseModel):
    id: int
    name: str
    record_type: Optional[str] = None  # 'lead' or 'opportunity'
    partner_name: Optional[str] = None
    contact_name: Optional[str] = None
    stage: Optional[str] = None
    lost_reason: Optional[str] = None
    lost_reason_category: Optional[str] = None
    probability: Optional[float] = None
    expected_revenue: Optional[float] = None
    salesperson: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    create_date: Optional[str] = None
    last_update: Optional[str] = None


class LostLeadListResponse(BaseModel):
    count: int
    items: List[LostLeadSummary]

    class Config:
        # Ensure None values are included in JSON response
        json_encoders = {}
        use_enum_values = True


class LostLeadAnalysisRequest(BaseModel):
    max_internal_notes: Optional[int] = None
    max_emails: Optional[int] = None
    user_identifier: Optional[str] = None  # Email address for Outlook search
    include_outlook_emails: bool = False  # Whether to search Outlook emails


class LostLeadMessage(BaseModel):
    id: Optional[int]
    date: Optional[str]
    formatted_date: Optional[str]
    author: Optional[str]
    subject: Optional[str]
    body: str


class LostLeadAnalysisResponse(BaseModel):
    lead: Dict[str, Any]
    analysis: Dict[str, Any]
    internal_notes: List[LostLeadMessage]
    emails: List[LostLeadMessage]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/test-type")
def test_type() -> dict:
    """Test endpoint to debug type field issue."""
    from pydantic import BaseModel
    from typing import Optional

    class TestModel(BaseModel):
        id: int
        record_type: Optional[str] = None
        type: Optional[str] = None

    obj = TestModel(id=1, record_type="test_record", type="test_type")
    return {
        "object": obj.dict(),
        "pydantic_version": __import__("pydantic").VERSION
    }


@app.post("/perplexity/generate", response_model=GenerateResponse)
def generate_prompt() -> GenerateResponse:
    workflow = get_workflow()

    prompt, leads = workflow.generate_enrichment_prompt()

    if not leads:
        return GenerateResponse(prompt="", lead_count=0, leads=[])

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


@app.post("/perplexity/enrich-single", response_model=EnrichSingleLeadResponse)
def enrich_single_lead(payload: EnrichSingleLeadRequest) -> EnrichSingleLeadResponse:
    """Enrich a single lead using Perplexity API"""
    try:
        config = Config()
        workflow = PerplexityWorkflow(config)
        perplexity_client = PerplexityClient(config)

        # Connect to Odoo and get the lead
        if not workflow.odoo.connect():
            return EnrichSingleLeadResponse(
                success=False,
                lead_id=payload.lead_id,
                error="Failed to connect to Odoo"
            )

        # Fetch the specific lead by ID
        lead_data = workflow.odoo._call_kw(
            'crm.lead', 'read',
            [[payload.lead_id]],
            {'fields': [
                'id', 'name', 'partner_name', 'email_from', 'phone', 'mobile',
                'function', 'contact_name', 'x_studio_linkedin_profile'
            ]}
        )

        if not lead_data:
            return EnrichSingleLeadResponse(
                success=False,
                lead_id=payload.lead_id,
                error=f"Lead {payload.lead_id} not found"
            )

        # Convert to the format expected by the workflow
        lead = lead_data[0]
        formatted_lead = {
            'id': lead.get('id'),
            'Full Name': lead.get('name') or lead.get('contact_name') or '',
            'Company Name': lead.get('partner_name') or '',
            'email': lead.get('email_from') or '',
            'Phone': lead.get('phone') or '',
            'Mobile': lead.get('mobile') or '',
            'Job Role': lead.get('function') or '',
        }

        # Generate prompt for this single lead
        prompt = workflow.generate_single_lead_prompt(formatted_lead)
        logger.info(f"Generated enrichment prompt for lead {payload.lead_id}")

        # Call Perplexity API
        perplexity_response = perplexity_client.enrich_lead(formatted_lead, prompt)

        if not perplexity_response:
            return EnrichSingleLeadResponse(
                success=False,
                lead_id=payload.lead_id,
                error="Perplexity API returned no response"
            )

        # Parse the response
        enriched_leads = workflow.parse_perplexity_results(perplexity_response, [formatted_lead])

        if not enriched_leads:
            return EnrichSingleLeadResponse(
                success=False,
                lead_id=payload.lead_id,
                error="Failed to parse Perplexity response"
            )

        enriched_data = enriched_leads[0]
        logger.info(f"Successfully enriched lead {payload.lead_id}")

        return EnrichSingleLeadResponse(
            success=True,
            lead_id=payload.lead_id,
            enriched_data=enriched_data
        )

    except Exception as e:
        logger.error(f"Error enriching lead {payload.lead_id}: {str(e)}")
        return EnrichSingleLeadResponse(
            success=False,
            lead_id=payload.lead_id,
            error=str(e)
        )


@app.post("/perplexity/enrich-batch", response_model=EnrichBatchResponse)
def enrich_batch_leads(payload: EnrichBatchRequest) -> EnrichBatchResponse:
    """Enrich multiple leads using Perplexity API in ONE batch call - returns comparison data for review"""
    results = []
    successful = 0
    failed = 0

    config = Config()
    workflow = PerplexityWorkflow(config)
    perplexity_client = PerplexityClient(config)

    # Connect to Odoo
    if not workflow.odoo.connect():
        return EnrichBatchResponse(
            total=len(payload.lead_ids),
            successful=0,
            failed=len(payload.lead_ids),
            results=[
                EnrichedLeadResult(
                    lead_id=lead_id,
                    success=False,
                    error="Failed to connect to Odoo"
                )
                for lead_id in payload.lead_ids
            ]
        )

    try:
        # Fetch ALL leads from Odoo
        all_leads_data = workflow.odoo._call_kw(
            'crm.lead', 'read',
            [payload.lead_ids],
            {'fields': [
                'id', 'name', 'partner_name', 'email_from', 'phone', 'mobile',
                'function', 'contact_name', 'x_studio_linkedin_profile',
                'website', 'city', 'country_id', 'x_studio_quality'
            ]}
        )

        # Build map of current data and formatted leads
        current_data_map = {}
        formatted_leads = []

        for lead in all_leads_data:
            lead_id = lead.get('id')

            # Store current data
            current_data_map[lead_id] = {
                'id': lead_id,
                'Full Name': lead.get('name') or lead.get('contact_name') or '',
                'Company Name': lead.get('partner_name') or '',
                'email': lead.get('email_from') or '',
                'Phone': lead.get('phone') or '',
                'Mobile': lead.get('mobile') or '',
                'Job Role': lead.get('function') or '',
                'LinkedIn Link': lead.get('x_studio_linkedin_profile') or '',
                'website': lead.get('website') or '',
                'City': lead.get('city') or '',
                'Country': lead.get('country_id')[1] if lead.get('country_id') else '',
                'Quality (Out of 5)': lead.get('x_studio_quality') or '',
            }

            # Format for enrichment
            formatted_leads.append({
                'id': lead_id,
                'Full Name': lead.get('name') or lead.get('contact_name') or '',
                'Company Name': lead.get('partner_name') or '',
                'email': lead.get('email_from') or '',
                'Phone': lead.get('phone') or '',
                'Mobile': lead.get('mobile') or '',
                'Job Role': lead.get('function') or '',
            })

        # Generate ONE batch prompt for ALL leads
        logger.info(f"Generating batch prompt for {len(formatted_leads)} leads")
        batch_prompt = workflow._build_comprehensive_prompt(formatted_leads)

        # Call Perplexity ONCE with all leads
        logger.info(f"Calling Perplexity API with batch of {len(formatted_leads)} leads")
        perplexity_response = perplexity_client.search(batch_prompt, max_tokens=8000)

        # DEBUG: Save full raw response
        if perplexity_response:
            with open('c:/Users/Geeks/Desktop/Programming_Files/Leads/perplexity_raw_response.txt', 'w', encoding='utf-8') as f:
                f.write(perplexity_response)
            logger.info(f"Perplexity raw response saved to perplexity_raw_response.txt ({len(perplexity_response)} chars)")

        if not perplexity_response:
            # All leads failed
            for lead_id in payload.lead_ids:
                results.append(EnrichedLeadResult(
                    lead_id=lead_id,
                    success=False,
                    current_data=current_data_map.get(lead_id),
                    error="Perplexity API returned no response"
                ))
            return EnrichBatchResponse(
                total=len(payload.lead_ids),
                successful=0,
                failed=len(payload.lead_ids),
                results=results
            )

        # Parse batch response (this works reliably!)
        logger.info(f"Parsing batch response ({len(perplexity_response)} characters)")
        enriched_leads = workflow.parse_perplexity_results(perplexity_response, formatted_leads)

        # Match enriched leads back to lead_ids
        enriched_map = {lead.get('id'): lead for lead in enriched_leads}

        for lead_id in payload.lead_ids:
            if lead_id in enriched_map:
                results.append(EnrichedLeadResult(
                    lead_id=lead_id,
                    success=True,
                    current_data=current_data_map.get(lead_id),
                    suggested_data=enriched_map[lead_id]
                ))
                successful += 1
            else:
                results.append(EnrichedLeadResult(
                    lead_id=lead_id,
                    success=False,
                    current_data=current_data_map.get(lead_id),
                    error="Lead not found in Perplexity response"
                ))
                failed += 1

        logger.info(f"Batch enrichment complete: {successful} successful, {failed} failed")

    except Exception as e:
        logger.error(f"Error in batch enrichment: {str(e)}")
        # Return error for all leads
        for lead_id in payload.lead_ids:
            results.append(EnrichedLeadResult(
                lead_id=lead_id,
                success=False,
                error=str(e)
            ))
        failed = len(payload.lead_ids)

    return EnrichBatchResponse(
        total=len(payload.lead_ids),
        successful=successful,
        failed=failed,
        results=results
    )


@app.post("/perplexity/push-approved", response_model=PushApprovedResponse)
def push_approved_enrichments(payload: PushApprovedRequest) -> PushApprovedResponse:
    """Push approved enrichment data to Odoo"""
    config = Config()
    workflow = PerplexityWorkflow(config)

    if not payload.approved_leads:
        return PushApprovedResponse(
            total=0,
            successful=0,
            failed=0,
            errors=["No leads provided"]
        )

    logger.info(f"Pushing {len(payload.approved_leads)} approved leads to Odoo")

    try:
        outcome = workflow.update_leads_in_odoo(payload.approved_leads)

        if not outcome.get("success", False):
            return PushApprovedResponse(
                total=len(payload.approved_leads),
                successful=0,
                failed=len(payload.approved_leads),
                errors=[outcome.get("error", "Unknown error")]
            )

        updated = outcome.get("updated", 0)
        failed = outcome.get("failed", 0)
        errors = outcome.get("errors", [])

        logger.info(f"Successfully pushed {updated} leads to Odoo, {failed} failed")

        return PushApprovedResponse(
            total=len(payload.approved_leads),
            successful=updated,
            failed=failed,
            errors=errors
        )

    except Exception as e:
        logger.error(f"Error pushing approved leads to Odoo: {str(e)}")
        return PushApprovedResponse(
            total=len(payload.approved_leads),
            successful=0,
            failed=len(payload.approved_leads),
            errors=[str(e)]
        )


@app.get("/apollo/followups", response_model=FollowUpResponse)
def get_apollo_followups(limit: int = 10, lookback_hours: Optional[int] = None) -> FollowUpResponse:
    service = get_followup_service()
    try:
        followups = service.prepare_followups(limit=limit, lookback_hours=lookback_hours)
    except Exception as exc:
        logger.error("Failed to prepare Apollo follow-ups: %s", exc)
        raise HTTPException(status_code=500, detail="Unable to generate Apollo follow-ups")

    items: List[FollowUpItem] = []
    for item in followups:
        email = item.get('email')
        subject = item.get('subject', '')
        body = item.get('body', '')
        if not email or not subject or not body:
            continue

        call = item.get('call') or {}
        odoo_lead = item.get('odoo_lead') or {}
        items.append(
            FollowUpItem(
                email=email,
                subject=subject,
                body=body,
                call=FollowUpCall(
                    id=call.get('id'),
                    disposition=call.get('disposition'),
                    direction=call.get('direction'),
                    duration_seconds=call.get('duration_seconds'),
                    last_called_at=call.get('last_called_at'),
                    notes=call.get('notes'),
                ),
                odoo_lead=FollowUpLead(
                    id=odoo_lead.get('id'),
                    name=odoo_lead.get('name'),
                    stage_name=odoo_lead.get('stage_name'),
                    salesperson=odoo_lead.get('salesperson'),
                    phone=str(odoo_lead.get('phone')) if odoo_lead.get('phone') else None,
                    company=odoo_lead.get('company'),
                ),
            )
        )

    return FollowUpResponse(count=len(items), items=items)


@app.get("/post-contact/actions", response_model=PostContactActionsResponse)
def get_post_contact_actions(limit: int = 10, lookback_hours: Optional[int] = None) -> PostContactActionsResponse:
    service = get_post_contact_service()
    try:
        actions = service.prepare_actions(limit=limit, lookback_hours=lookback_hours)
    except Exception as exc:
        logger.error("Failed to prepare post-contact actions: %s", exc)
        raise HTTPException(status_code=500, detail="Unable to prepare post-contact actions")

    serialized: List[PostContactActionPayload] = []
    for action in actions:
        call_info = _serialize_call_info(action.call)
        lead_info = _serialize_lead_info(action.odoo_lead)

        serialized.append(
            PostContactActionPayload(
                action_type=action.action_type,  # type: ignore[arg-type]
                contact_email=action.contact_email,
                odoo_lead_id=int(action.odoo_lead_id),
                subject=action.subject,
                body=action.body,
                note_body=action.note_body,
                transcription=action.transcription,
                call=PostContactCall(**call_info) if call_info else None,
                odoo_lead=PostContactLead(**lead_info) if lead_info else None,
            )
        )

    return PostContactActionsResponse(count=len(serialized), actions=serialized)


@app.post("/post-contact/execute", response_model=ExecuteActionResponse)
def execute_post_contact_action(payload: ExecuteActionRequest) -> ExecuteActionResponse:
    service = get_post_contact_service()
    action = PostContactAction(
        action_type=payload.action_type,
        contact_email=payload.contact_email,
        odoo_lead_id=payload.odoo_lead_id,
        subject=payload.subject,
        body=payload.body,
        note_body=payload.note_body,
        transcription=payload.transcription,
        call=payload.call.dict() if payload.call else {},
        odoo_lead=payload.odoo_lead.dict() if payload.odoo_lead else {},
    )

    try:
        if payload.action_type == "email":
            success = service.execute_email(action)
            message = "Email sent successfully"
        else:
            success = service.execute_note(action)
            message = "Note uploaded to Odoo"
    except Exception as exc:
        logger.error("Failed to execute post-contact action: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to execute post-contact action")

    if not success:
        raise HTTPException(status_code=500, detail="Action did not complete successfully")

    return ExecuteActionResponse(success=True, message=message)


@app.get("/lost-leads", response_model=LostLeadListResponse, response_model_exclude_none=False)
def list_lost_leads(
    limit: int = 20,
    salesperson: Optional[str] = None,
    type_filter: Optional[str] = None
) -> LostLeadListResponse:
    analyzer = get_lost_lead_analyzer()
    try:
        leads = analyzer.list_lost_leads(
            limit=limit,
            salesperson_name=salesperson,
            type_filter=type_filter
        )
    except Exception as exc:
        logger.error("Failed to fetch lost leads: %s", exc)
        raise HTTPException(status_code=500, detail="Unable to fetch lost leads")

    items: List[LostLeadSummary] = []
    for lead in leads:
        try:
            lead_id = int(lead.get("id"))
        except Exception:
            logger.debug("Skipping lead with missing id: %s", lead)
            continue
        def _str_or_none(value):
            """Convert Odoo False values to None for optional string fields."""
            return value if isinstance(value, str) else None

        lead_type = _str_or_none(lead.get("type"))
        logger.debug(f"Lead {lead_id}: raw type={lead.get('type')}, processed type={lead_type}")

        items.append(
            LostLeadSummary(
                id=lead_id,
                name=lead.get("name") or "Untitled Opportunity",
                record_type=lead_type,
                partner_name=_str_or_none(lead.get("partner_name")),
                contact_name=_str_or_none(lead.get("contact_name")),
                stage=_str_or_none(lead.get("stage_id")),
                lost_reason=_str_or_none(lead.get("lost_reason")),
                lost_reason_category=_str_or_none(lead.get("lost_reason_id")),
                probability=lead.get("probability"),
                expected_revenue=lead.get("expected_revenue"),
                salesperson=_str_or_none(lead.get("user_id")),
                email=_str_or_none(lead.get("email_from")),
                phone=_str_or_none(lead.get("phone")),
                mobile=_str_or_none(lead.get("mobile")),
                create_date=_str_or_none(lead.get("create_date")),
                last_update=_str_or_none(lead.get("write_date")),
            )
        )

    response = LostLeadListResponse(count=len(items), items=items)
    if items:
        logger.info(f"First item record_type field: {items[0].record_type}")
        logger.info(f"First item dict: {items[0].dict()}")
    return response


@app.post("/lost-leads/{lead_id}/analysis", response_model=LostLeadAnalysisResponse)
def analyze_lost_lead(
    lead_id: int,
    payload: LostLeadAnalysisRequest,
) -> LostLeadAnalysisResponse:
    analyzer = get_lost_lead_analyzer()
    try:
        result = analyzer.analyze_lost_lead(
            lead_id,
            max_internal_notes=payload.max_internal_notes,
            max_emails=payload.max_emails,
            user_identifier=payload.user_identifier,
            include_outlook_emails=payload.include_outlook_emails,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to analyze lost lead %s: %s", lead_id, exc)
        raise HTTPException(status_code=500, detail="Unable to analyze lost lead")

    def _map_messages(messages: List[Dict[str, Any]]) -> List[LostLeadMessage]:
        mapped: List[LostLeadMessage] = []
        for message in messages:
            # Ensure all fields are proper types
            subject = message.get("subject")
            if subject is None or subject is False:
                subject = ""
            elif not isinstance(subject, str):
                subject = str(subject)

            mapped.append(
                LostLeadMessage(
                    id=message.get("id"),
                    date=message.get("date"),
                    formatted_date=message.get("formatted_date"),
                    author=message.get("author") or "",
                    subject=subject,
                    body=message.get("body") or "",
                )
            )
        return mapped

    return LostLeadAnalysisResponse(
        lead=result.get("lead", {}),
        analysis=result.get("analysis", {}),
        internal_notes=_map_messages(result.get("internal_notes", [])),
        emails=_map_messages(result.get("emails", [])),
    )


# ============================================================================
# PROPOSAL FOLLOW-UP ENDPOINTS
# ============================================================================

class ProposalFollowupSettings(BaseModel):
    """Settings for proposal follow-up analysis."""
    days_back: int = 7
    no_response_days: int = 3


class ProposalFollowupSummary(BaseModel):
    """Summary counts for proposal follow-ups."""
    unanswered_count: int
    pending_proposals_count: int
    total_count: int
    days_back: int
    no_response_days: int
    last_updated: Optional[str] = None


class ProposalFollowupThread(BaseModel):
    """Single email thread needing follow-up."""
    conversation_id: str
    external_email: str
    subject: str
    days_waiting: int
    last_contact_date: Optional[str] = None
    proposal_date: Optional[str] = None
    odoo_lead: Optional[Dict[str, Any]] = None
    analysis: Optional[Dict[str, Any]] = None
    classification: Optional[Dict[str, Any]] = None  # AI classification: is_lead, confidence, category


class ProposalFollowupResponse(BaseModel):
    """Response containing all proposal follow-up data."""
    summary: ProposalFollowupSummary
    unanswered: List[ProposalFollowupThread]
    pending_proposals: List[ProposalFollowupThread]


@app.get("/proposal-followups", response_model=ProposalFollowupResponse)
def get_proposal_followups(
    days_back: int = 3,
    no_response_days: int = 3,
    engage_email: str = "automated.response@prezlab.com",
    force_refresh: bool = False
):
    """
    Get proposal follow-up analysis from engage inbox.

    Args:
        days_back: Number of days to look back for emails (default: 3)
        no_response_days: Days threshold for "no response" (default: 3)
        engage_email: Email of the engage monitoring account
        force_refresh: Force refresh analysis instead of using cache

    Returns:
        Summary and categorized threads needing follow-up with last_updated timestamp
    """
    global proposal_followups_cache

    # Check if we have cached data with matching parameters
    cache_params = {"days_back": days_back, "no_response_days": no_response_days, "engage_email": engage_email}
    if not force_refresh and proposal_followups_cache["data"] and proposal_followups_cache["params"] == cache_params:
        logger.info("Returning cached proposal follow-ups analysis")
        cached_response = proposal_followups_cache["data"]
        # Add last_updated timestamp to summary
        cached_response.summary.last_updated = proposal_followups_cache["timestamp"]
        return cached_response

    try:
        logger.info(f"Running new proposal follow-ups analysis (days_back={days_back}, no_response_days={no_response_days})")
        analyzer = ProposalFollowupAnalyzer()
        result = analyzer.get_proposal_followups(
            user_identifier=engage_email,
            days_back=days_back,
            no_response_days=no_response_days
        )

        # Create timestamp
        timestamp = datetime.utcnow().isoformat() + "Z"

        response = ProposalFollowupResponse(
            summary=ProposalFollowupSummary(**result["summary"], last_updated=timestamp),
            unanswered=[ProposalFollowupThread(**thread) for thread in result["unanswered"]],
            pending_proposals=[ProposalFollowupThread(**thread) for thread in result["pending_proposals"]]
        )

        # Cache the result
        proposal_followups_cache = {
            "data": response,
            "timestamp": timestamp,
            "params": cache_params
        }

        return response
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting proposal follow-ups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/proposal-followups/analyze-thread")
def analyze_followup_thread(thread_data: Dict[str, Any]):
    """
    Analyze a specific email thread and generate follow-up draft.

    Args:
        thread_data: Thread data with conversation_id and thread messages

    Returns:
        Analysis with summary, sentiment, urgency, and draft email
    """
    try:
        analyzer = ProposalFollowupAnalyzer()
        analysis = analyzer.analyze_thread_with_llm(thread_data)
        return analysis
    except Exception as e:
        logger.error(f"Error analyzing thread: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# EMAIL / OUTLOOK OAUTH2 ENDPOINTS
# ============================================================================

def get_outlook_client() -> OutlookClient:
    """Get or create Outlook client instance."""
    return OutlookClient(config=Config())


def get_token_store() -> EmailTokenStore:
    """Get or create token store instance."""
    return EmailTokenStore()


class EmailAuthResponse(BaseModel):
    authorization_url: str
    state: str


class EmailAuthCallbackRequest(BaseModel):
    code: str
    state: str
    user_identifier: Optional[str] = None  # e.g., Odoo user email or ID


class EmailAuthStatusResponse(BaseModel):
    authorized: bool
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    expires_soon: bool = False


@app.get("/auth/outlook/start", response_model=EmailAuthResponse)
def start_outlook_auth(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Start OAuth2 flow for Outlook/Microsoft email.
    Returns authorization URL for user to visit.
    Requires authentication.
    """
    import secrets

    outlook = get_outlook_client()

    # Generate random state for CSRF protection
    # Include user ID in state for verification
    state = f"{current_user['id']}:{secrets.token_urlsafe(32)}"

    auth_url = outlook.get_authorization_url(state=state)

    return EmailAuthResponse(
        authorization_url=auth_url,
        state=state
    )


@app.get("/auth/outlook/callback", response_class=RedirectResponse)
async def outlook_auth_callback(request: Request, code: str, state: str):
    """
    Handle OAuth2 callback from Microsoft (GET with query params).
    Redirects to frontend callback page which will complete the flow.
    """
    # Redirect to frontend with the code and state
    # Frontend will call the POST endpoint to complete the exchange
    cfg = Config()
    frontend_url = cfg.FRONTEND_URL.rstrip('/')
    frontend_callback_url = f"{frontend_url}/auth/outlook/callback?code={code}&state={state}"
    return RedirectResponse(url=frontend_callback_url)


@app.post("/auth/outlook/callback")
def outlook_auth_callback_post(
    request: EmailAuthCallbackRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Database = Depends(get_database)
):
    """
    Complete OAuth2 callback (POST from frontend).
    Exchange authorization code for tokens and store them for the current user.
    Requires authentication.
    """
    outlook = get_outlook_client()
    token_store = get_token_store()

    try:
        # Verify state contains current user ID
        if request.state and ":" in request.state:
            state_user_id = int(request.state.split(":")[0])
            if state_user_id != current_user["id"]:
                raise HTTPException(status_code=403, detail="State verification failed")

        # Exchange code for tokens
        token_response = outlook.exchange_code_for_tokens(request.code)

        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")
        expires_in = token_response.get("expires_in", 3600)

        if not access_token or not refresh_token:
            raise HTTPException(status_code=400, detail="Invalid token response from Microsoft")

        # Get user info from Microsoft
        user_info = outlook.get_user_info(access_token)
        user_email = user_info.get("mail") or user_info.get("userPrincipalName")
        user_name = user_info.get("displayName")

        # Use user ID as identifier for token storage
        user_identifier = str(current_user["id"])

        # Store tokens in file system (backwards compatibility)
        success = token_store.save_tokens(
            user_identifier=user_identifier,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            user_email=user_email,
            user_name=user_name,
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to store tokens")

        # Also store in database
        db.update_user_settings(
            user_id=current_user["id"],
            outlook_tokens={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": expires_in,
                "user_email": user_email,
                "user_name": user_name
            },
            user_identifier=user_identifier
        )

        return {
            "success": True,
            "user_email": user_email,
            "user_name": user_name,
            "message": "Email authorization successful"
        }

    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/outlook/status", response_model=EmailAuthStatusResponse)
def get_email_auth_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Check if current user has authorized email access."""
    token_store = get_token_store()
    user_identifier = str(current_user["id"])

    tokens = token_store.get_tokens(user_identifier)

    if not tokens:
        return EmailAuthStatusResponse(authorized=False)

    is_expired = token_store.is_token_expired(user_identifier)

    return EmailAuthStatusResponse(
        authorized=True,
        user_email=tokens.get("user_email"),
        user_name=tokens.get("user_name"),
        expires_soon=is_expired
    )


@app.delete("/auth/outlook")
def revoke_email_auth(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Database = Depends(get_database)
):
    """Revoke email authorization for current user."""
    token_store = get_token_store()
    user_identifier = str(current_user["id"])

    success = token_store.delete_tokens(user_identifier)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to revoke authorization")

    # Also clear from database
    db.update_user_settings(
        user_id=current_user["id"],
        outlook_tokens=None
    )

    return {"success": True, "message": "Email authorization revoked"}


# ============================================================================
# SYSTEM EMAIL OAUTH2 ENDPOINTS (for automated.response@prezlab.com)
# ============================================================================

@app.get("/auth/outlook/system/start", response_model=EmailAuthResponse)
def start_system_outlook_auth(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Start OAuth2 flow for system email (automated.response@prezlab.com).
    Admin only. Returns authorization URL for user to visit.
    """
    # Could add admin check here if needed
    # if current_user["role"] != "admin":
    #     raise HTTPException(status_code=403, detail="Admin access required")

    import secrets

    outlook = get_outlook_client()

    # Use special state prefix to identify system auth
    state = f"SYSTEM:{secrets.token_urlsafe(32)}"

    # Force account selection so user can choose automated.response account
    auth_url = outlook.get_authorization_url(state=state, force_account_selection=True)

    return EmailAuthResponse(
        authorization_url=auth_url,
        state=state
    )


@app.post("/auth/outlook/system/callback")
def system_outlook_auth_callback_post(
    request: EmailAuthCallbackRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Complete OAuth2 callback for system email (POST from frontend).
    Exchange authorization code for tokens and store them for system account.
    """
    outlook = get_outlook_client()
    token_store = get_token_store()

    try:
        # Verify state is for system auth
        if not request.state or not request.state.startswith("SYSTEM:"):
            raise HTTPException(status_code=403, detail="Invalid state for system auth")

        # Exchange code for tokens
        token_response = outlook.exchange_code_for_tokens(request.code)

        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")
        expires_in = token_response.get("expires_in", 3600)

        if not access_token or not refresh_token:
            raise HTTPException(status_code=400, detail="Invalid token response from Microsoft")

        # Get user info from Microsoft
        user_info = outlook.get_user_info(access_token)
        user_email = user_info.get("mail") or user_info.get("userPrincipalName")
        user_name = user_info.get("displayName")

        # Use fixed identifier for system account
        system_identifier = "automated.response@prezlab.com"

        # Store tokens in file system
        success = token_store.save_tokens(
            user_identifier=system_identifier,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            user_email=user_email,
            user_name=user_name,
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to store tokens")

        return {
            "success": True,
            "user_email": user_email,
            "user_name": user_name,
            "message": "System email authorization successful"
        }

    except Exception as e:
        logger.error(f"Error in system OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/outlook/system/status", response_model=EmailAuthStatusResponse)
def get_system_email_auth_status():
    """Check if system email (automated.response@prezlab.com) has authorized access."""
    token_store = get_token_store()
    system_identifier = "automated.response@prezlab.com"

    tokens = token_store.get_tokens(system_identifier)

    if not tokens:
        return EmailAuthStatusResponse(authorized=False)

    is_expired = token_store.is_token_expired(system_identifier)

    return EmailAuthStatusResponse(
        authorized=True,
        user_email=tokens.get("user_email"),
        user_name=tokens.get("user_name"),
        expires_soon=is_expired
    )


@app.delete("/auth/outlook/system")
def revoke_system_email_auth(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Revoke system email authorization. Admin only."""
    # Could add admin check here if needed
    # if current_user["role"] != "admin":
    #     raise HTTPException(status_code=403, detail="Admin access required")

    token_store = get_token_store()
    system_identifier = "automated.response@prezlab.com"

    success = token_store.delete_tokens(system_identifier)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to revoke system authorization")

    return {"success": True, "message": "System email authorization revoked"}


@app.get("/auth/outlook/users")
def list_authorized_users():
    """List all users who have authorized email access (admin endpoint)."""
    token_store = get_token_store()
    users = token_store.list_authorized_users()
    return {"users": users, "count": len(users)}


class SendEmailRequest(BaseModel):
    to: List[str]
    subject: str
    body: str
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    include_engage_cc: bool = True  # Automatically CC engage@prezlab.com


@app.post("/email/send")
def send_email(
    request: SendEmailRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Send an email from current user with automatic CC to engage@prezlab.com.
    Requires authentication and email authorization.
    """
    outlook = get_outlook_client()
    token_store = get_token_store()
    user_identifier = str(current_user["id"])

    try:
        # Get tokens
        tokens = token_store.get_tokens(user_identifier)
        if not tokens:
            raise HTTPException(
                status_code=400,
                detail="Email not authorized. Please connect your email first."
            )

        # Refresh token if expired
        access_token = tokens.get("access_token")
        if token_store.is_token_expired(user_identifier):
            refresh_token = tokens.get("refresh_token")
            token_response = outlook.refresh_access_token(refresh_token)
            access_token = token_response.get("access_token")
            token_store.update_access_token(
                user_identifier,
                access_token,
                token_response.get("expires_in", 3600)
            )

        # Add engage@prezlab.com to CC if requested
        cc_list = list(request.cc or [])
        if request.include_engage_cc and "engage@prezlab.com" not in cc_list:
            cc_list.append("engage@prezlab.com")

        # Send email
        success = outlook.send_email(
            access_token=access_token,
            to=request.to,
            subject=request.subject,
            body=request.body,
            cc=cc_list if cc_list else None,
            bcc=request.bcc
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to send email")

        return {
            "success": True,
            "message": "Email sent successfully",
            "cc_list": cc_list
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CALL FLOW GENERATION ENDPOINTS
# ============================================================================

class EnrichedLead(BaseModel):
    id: int
    name: str
    partner_name: Optional[str] = None
    email_from: Optional[str] = None
    stage_name: Optional[str] = None
    salesperson_name: Optional[str] = None
    description: Optional[str] = None
    function: Optional[str] = None


class EnrichedLeadsResponse(BaseModel):
    count: int
    leads: List[EnrichedLead]


class CallFlowGenerateRequest(BaseModel):
    lead_id: int


@app.get("/enriched-leads", response_model=EnrichedLeadsResponse)
def get_enriched_leads():
    """Get list of leads that have been enriched (have quality rating)."""
    config = _setup_logging()
    odoo = OdooClient(config)

    if not odoo.connect():
        raise HTTPException(status_code=500, detail="Failed to connect to Odoo")

    try:
        # Find Dareen's user ID
        salesperson_name = config.SALESPERSON_NAME
        user_id = odoo.find_user_id(salesperson_name)

        # Enriched leads are those that either:
        # 1. Have a quality rating (x_studio_quality is not empty), OR
        # 2. Don't belong to Dareen
        # This is the opposite of unenriched leads
        domain = [
            '|',
            ['x_studio_quality', '!=', False],
            ['user_id', '!=', user_id] if user_id else ['id', '!=', -1]
        ]

        fields = [
            'id', 'name', 'partner_name', 'email_from', 'stage_id',
            'user_id', 'description', 'function', 'x_studio_quality'
        ]

        leads_data = odoo._call_kw(
            'crm.lead',
            'search_read',
            [domain],
            {
                'fields': fields,
                'limit': 100,
                'order': 'write_date desc'
            }
        )

        enriched_leads = []
        for lead in leads_data:
            enriched_leads.append(
                EnrichedLead(
                    id=lead.get('id'),
                    name=lead.get('name') or 'Untitled Lead',
                    partner_name=lead.get('partner_name') if isinstance(lead.get('partner_name'), str) else None,
                    email_from=lead.get('email_from') if isinstance(lead.get('email_from'), str) else None,
                    stage_name=lead.get('stage_id')[1] if lead.get('stage_id') and isinstance(lead.get('stage_id'), (list, tuple)) else None,
                    salesperson_name=lead.get('user_id')[1] if lead.get('user_id') and isinstance(lead.get('user_id'), (list, tuple)) else None,
                    description=lead.get('description') if isinstance(lead.get('description'), str) else None,
                    function=lead.get('function') if isinstance(lead.get('function'), str) else None,
                )
            )

        return EnrichedLeadsResponse(count=len(enriched_leads), leads=enriched_leads)

    except Exception as exc:
        logger.error(f"Failed to fetch enriched leads: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch enriched leads: {str(exc)}")


@app.post("/call-flow/generate")
def generate_call_flow(request: CallFlowGenerateRequest):
    """Generate a personalized discovery call flow document for a lead."""
    import io
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from openai import OpenAI

    config = _setup_logging()
    odoo = OdooClient(config)

    if not odoo.connect():
        raise HTTPException(status_code=500, detail="Failed to connect to Odoo")

    # Fetch the lead data
    try:
        lead_data = odoo._call_kw(
            'crm.lead',
            'search_read',
            [[('id', '=', request.lead_id)]],
            {
                'fields': ['id', 'name', 'partner_name', 'email_from', 'stage_id',
                          'user_id', 'description', 'function', 'phone', 'mobile'],
                'limit': 1
            }
        )

        if not lead_data:
            raise HTTPException(status_code=404, detail="Lead not found")

        lead = lead_data[0]

    except Exception as exc:
        logger.error(f"Failed to fetch lead {request.lead_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch lead: {str(exc)}")

    # Extract lead information
    lead_name = lead.get('name') or 'Unknown'
    partner_name = lead.get('partner_name') if isinstance(lead.get('partner_name'), str) else 'Unknown Company'
    description = lead.get('description') if isinstance(lead.get('description'), str) else ''
    job_title = lead.get('function') if isinstance(lead.get('function'), str) else 'Unknown'
    stage = lead.get('stage_id')[1] if lead.get('stage_id') and isinstance(lead.get('stage_id'), (list, tuple)) else 'Unknown'

    # Generate personalized content using LLM
    try:
        openai_client = OpenAI(api_key=config.OPENAI_API_KEY)

        prompt = f"""You are a sales consultant helping to prepare for a discovery call. Based on the Air France Discovery Call Flow methodology, create personalized content for each of the 7 sections below.

LEAD INFORMATION:
- Contact Name: {lead_name}
- Company: {partner_name}
- Job Title: {job_title}
- Current Stage: {stage}
- Enriched Notes: {description[:500] if description else 'No additional context available'}

DISCOVERY CALL FLOW SECTIONS:
1. Business Problem - Identify core challenges this lead/company might face
2. Current State - Explore their current approach and situation
3. Cause Analysis - Understand potential root causes of their challenges
4. Negative Impact - Explore consequences of not solving these issues
5. Desired Outcome - Their ideal future state and goals
6. Process - How they currently handle workflows related to our solution
7. Stakeholders - Who are the key decision-makers and influencers

For each section, provide:
- A brief objective (1-2 sentences)
- 3-4 dialogue-friendly questions tailored to {lead_name} at {partner_name}

Format your response as JSON with this structure:
{{
  "sections": [
    {{
      "title": "Business Problem",
      "objective": "...",
      "questions": ["...", "...", "..."]
    }},
    ...
  ]
}}

Make the questions conversational, open-ended, and specifically relevant to {job_title} at {partner_name}. Reference any relevant context from the enriched notes."""

        response = openai_client.chat.completions.create(
            model=config.OPENAI_MODEL or 'gpt-5-mini',
            messages=[
                {"role": "system", "content": "You are an expert sales consultant who creates personalized discovery call frameworks. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=2000,
            response_format={"type": "json_object"}
        )

        import json
        call_flow_data = json.loads(response.choices[0].message.content)

    except Exception as exc:
        logger.error(f"Failed to generate call flow content: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to generate call flow: {str(exc)}")

    # Create the Word document
    try:
        doc = Document()

        # Set document margins
        sections = doc.sections
        for section in sections:
            section.top_margin = Inches(1)
            section.bottom_margin = Inches(1)
            section.left_margin = Inches(1)
            section.right_margin = Inches(1)

        # Title
        title = doc.add_heading(f'Discovery Call Flow - {lead_name}', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Subtitle with company info
        subtitle = doc.add_paragraph()
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = subtitle.add_run(f'{partner_name} | {job_title}')
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(128, 128, 128)

        doc.add_paragraph()  # Spacing

        # Add each section
        sections_data = call_flow_data.get('sections', [])
        for i, section_data in enumerate(sections_data, 1):
            # Section title
            section_title = doc.add_heading(f"{i}. {section_data.get('title', '')}", 1)
            section_title.alignment = WD_ALIGN_PARAGRAPH.LEFT

            # Objective
            objective_para = doc.add_paragraph()
            objective_para.add_run('Objective: ').bold = True
            objective_para.add_run(section_data.get('objective', ''))

            # Questions
            questions_heading = doc.add_paragraph()
            questions_heading.add_run('Discussion Questions:').bold = True

            questions = section_data.get('questions', [])
            for question in questions:
                doc.add_paragraph(question, style='List Bullet')

            doc.add_paragraph()  # Spacing between sections

        # Add footer with preparation notes
        doc.add_paragraph()
        footer = doc.add_paragraph()
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer.add_run('Prepared by PrezLab Lead Automation Hub')
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(150, 150, 150)

        # Save to bytes buffer
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)

        # Return as downloadable file
        filename = f"Discovery_Call_Flow_{lead_name.replace(' ', '_')}.docx"

        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as exc:
        logger.error(f"Failed to create document: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to create document: {str(exc)}")


# ============================================================================
# DASHBOARD SUMMARY ENDPOINT
# ============================================================================

class DashboardSummary(BaseModel):
    """Dashboard summary data aggregated from all features."""
    high_priority_count: int
    high_priority_items: List[Dict[str, Any]]
    stats: Dict[str, Any]  # Now includes last_updated timestamp
    recent_activity: List[Dict[str, Any]]


@app.get("/dashboard/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    engage_email: str = "automated.response@prezlab.com"
):
    """
    Get dashboard summary with data from all features.

    Args:
        engage_email: Email address for engage group monitoring

    Returns:
        Aggregated dashboard data
    """
    try:
        high_priority_items = []
        stats = {}
        recent_activity = []

        # 1. Get Proposal Follow-ups data from cache
        try:
            # Use cached data if available, otherwise return zeros
            if proposal_followups_cache["data"]:
                followups_data = proposal_followups_cache["data"]
                unanswered_count = followups_data.summary.unanswered_count
                pending_proposals_count = followups_data.summary.pending_proposals_count
                stats["unanswered_emails"] = unanswered_count
                stats["pending_proposals"] = pending_proposals_count
                stats["last_updated"] = proposal_followups_cache["timestamp"]

                followups_result = {
                    "summary": {
                        "unanswered_count": unanswered_count,
                        "pending_proposals_count": pending_proposals_count
                    },
                    "unanswered": [thread.dict() for thread in followups_data.unanswered],
                    "pending_proposals": [thread.dict() for thread in followups_data.pending_proposals]
                }
            else:
                # No cached data yet
                stats["unanswered_emails"] = 0
                stats["pending_proposals"] = 0
                stats["last_updated"] = None
                followups_result = {"summary": {"unanswered_count": 0, "pending_proposals_count": 0}, "unanswered": [], "pending_proposals": []}

            # Add high priority items (>5 days waiting)
            for item in followups_result["unanswered"]:
                if item["days_waiting"] >= 5:
                    high_priority_items.append({
                        "type": "email",
                        "subject": item["subject"],
                        "external_email": item["external_email"],
                        "days_waiting": item["days_waiting"],
                        "odoo_lead": item.get("odoo_lead"),
                        "source": "engage"
                    })

            for item in followups_result["pending_proposals"]:
                if item["days_waiting"] >= 5:
                    high_priority_items.append({
                        "type": "proposal",
                        "subject": item["subject"],
                        "external_email": item["external_email"],
                        "days_waiting": item["days_waiting"],
                        "odoo_lead": item.get("odoo_lead"),
                        "source": "engage"
                    })

            # Add recent activity
            for item in followups_result["unanswered"][:3]:  # Latest 3
                recent_activity.append({
                    "type": "email_received",
                    "description": f"Email from {item['external_email']}",
                    "time": item.get("last_contact_date", ""),
                    "subject": item["subject"]
                })

        except Exception as e:
            logger.error(f"Error fetching proposal follow-ups for dashboard: {e}")
            stats["unanswered_emails"] = 0
            stats["pending_proposals"] = 0

        # 2. Get Lost Leads data (placeholder - implement when lost leads uses engage)
        try:
            # TODO: Fetch lost leads data when implemented
            stats["lost_leads"] = 0
        except Exception as e:
            logger.error(f"Error fetching lost leads for dashboard: {e}")
            stats["lost_leads"] = 0

        # 3. Get Enrichment stats (placeholder)
        try:
            # TODO: Track enrichments in database and fetch count
            stats["enriched_today"] = 0
        except Exception as e:
            logger.error(f"Error fetching enrichment stats for dashboard: {e}")
            stats["enriched_today"] = 0

        # 4. Get Call Flow stats (placeholder)
        try:
            # TODO: Track call flows in database and fetch count
            stats["call_flows_generated"] = 0
        except Exception as e:
            logger.error(f"Error fetching call flow stats for dashboard: {e}")
            stats["call_flows_generated"] = 0

        # Sort high priority items by days waiting (descending)
        high_priority_items.sort(key=lambda x: x["days_waiting"], reverse=True)

        # Sort recent activity by time (most recent first)
        recent_activity.sort(key=lambda x: x.get("time", ""), reverse=True)

        return DashboardSummary(
            high_priority_count=len(high_priority_items),
            high_priority_items=high_priority_items[:10],  # Limit to 10
            stats=stats,
            recent_activity=recent_activity[:10]  # Limit to 10
        )

    except Exception as e:
        logger.error(f"Error getting dashboard summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================================================================
# Authentication Endpoints
# ===================================================================

class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: Dict[str, Any]


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str


@app.post("/auth/login", response_model=LoginResponse)
def login(request: LoginRequest, auth_service: AuthService = Depends(get_auth_service)):
    """Authenticate user and return access token."""
    user = auth_service.authenticate_user(request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = auth_service.create_access_token(
        user_id=user["id"],
        email=user["email"],
        role=user["role"]
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=user
    )


@app.post("/auth/register", response_model=UserResponse)
def register(
    request: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Register a new user."""
    try:
        user_id = auth_service.register_user(
            email=request.email,
            name=request.name,
            password=request.password,
            role="user"
        )

        user = auth_service.db.get_user_by_id(user_id)
        return UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            role=user["role"]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/auth/me", response_model=UserResponse)
def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current authenticated user."""
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        name=current_user["name"],
        role=current_user["role"]
    )


@app.get("/auth/users")
def list_users(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Database = Depends(get_database)
):
    """List all users (admin only)."""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    return db.list_users()
