#!/usr/bin/env python3
"""FastAPI backend exposing Perplexity and Apollo follow-up helpers."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from modules.logger import setup_logging
from modules.perplexity_workflow import PerplexityWorkflow
from modules.apollo_followup import ApolloFollowUpService
from modules.post_contact_automation import PostContactAutomationService, PostContactAction
from modules.lost_lead_analyzer import LostLeadAnalyzer
from modules.outlook_client import OutlookClient
from modules.email_token_store import EmailTokenStore
from modules.odoo_client import OdooClient

logger = logging.getLogger(__name__)

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
def start_outlook_auth():
    """
    Start OAuth2 flow for Outlook/Microsoft email.
    Returns authorization URL for user to visit.
    """
    import secrets

    outlook = get_outlook_client()

    # Generate random state for CSRF protection
    state = secrets.token_urlsafe(32)

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
    frontend_url = config.FRONTEND_URL.rstrip('/')
    frontend_callback_url = f"{frontend_url}/auth/outlook/callback?code={code}&state={state}"
    return RedirectResponse(url=frontend_callback_url)


@app.post("/auth/outlook/callback")
def outlook_auth_callback_post(request: EmailAuthCallbackRequest):
    """
    Complete OAuth2 callback (POST from frontend).
    Exchange authorization code for tokens and store them.
    """
    outlook = get_outlook_client()
    token_store = get_token_store()

    try:
        # Exchange code for tokens
        token_response = outlook.exchange_code_for_tokens(request.code)

        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")
        expires_in = token_response.get("expires_in", 3600)

        if not access_token or not refresh_token:
            raise HTTPException(status_code=400, detail="Invalid token response from Microsoft")

        # Get user info
        user_info = outlook.get_user_info(access_token)
        user_email = user_info.get("mail") or user_info.get("userPrincipalName")
        user_name = user_info.get("displayName")

        # Use provided identifier or default to email
        user_identifier = request.user_identifier or user_email

        # Store tokens
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

        return {
            "success": True,
            "user_email": user_email,
            "user_name": user_name,
            "message": "Email authorization successful"
        }

    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/outlook/status/{user_identifier}", response_model=EmailAuthStatusResponse)
def get_email_auth_status(user_identifier: str):
    """Check if a user has authorized email access."""
    token_store = get_token_store()

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


@app.delete("/auth/outlook/{user_identifier}")
def revoke_email_auth(user_identifier: str):
    """Revoke email authorization for a user."""
    token_store = get_token_store()

    success = token_store.delete_tokens(user_identifier)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to revoke authorization")

    return {"success": True, "message": "Email authorization revoked"}


@app.get("/auth/outlook/users")
def list_authorized_users():
    """List all users who have authorized email access (admin endpoint)."""
    token_store = get_token_store()
    users = token_store.list_authorized_users()
    return {"users": users, "count": len(users)}


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
