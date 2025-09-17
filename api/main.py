#!/usr/bin/env python3
"""
FastAPI Backend for Lead Automation System
Provides REST API endpoints for the web interface
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import json

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from modules.enrichment_pipeline import EnrichmentPipeline
from modules.odoo_client import OdooClient
from modules.sheets_client import GoogleSheetsClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state for tracking operations
active_operations: Dict[str, Dict] = {}
websocket_connections: List[WebSocket] = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic"""
    logger.info("Lead Automation API starting up...")
    yield
    logger.info("📴 Lead Automation API shutting down...")

# Create FastAPI app
app = FastAPI(
    title="Lead Automation System API",
    description="Modern web interface for lead extraction and enrichment",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class LeadData(BaseModel):
    id: int
    name: str
    email: str
    company: str
    phone: Optional[str] = None
    mobile: Optional[str] = None
    linkedin: Optional[str] = None
    job_title: Optional[str] = None
    title: Optional[str] = None
    contact_name: Optional[str] = None
    quality_score: Optional[int] = None
    enriched: bool = False
    industry: Optional[str] = None
    company_size: Optional[str] = None
    description: Optional[str] = None
    salesperson: Optional[str] = None
    website: Optional[str] = None
    full_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

class PipelineStatus(BaseModel):
    operation_id: str
    status: str
    progress: float
    current_step: str
    leads_processed: int
    total_leads: int
    errors: List[str] = []
    started_at: datetime
    estimated_completion: Optional[datetime] = None

class ConfigData(BaseModel):
    odoo_url: str
    odoo_db: str
    odoo_username: str
    salesperson_name: str
    batch_size: int
    max_concurrent_requests: int

class OperationRequest(BaseModel):
    lead_ids: Optional[List[int]] = None
    config_override: Optional[Dict[str, Any]] = None

# WebSocket manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")

    async def broadcast(self, message: Dict):
        logger.info(f"Broadcasting to {len(self.active_connections)} clients: {message}")
        disconnected_clients = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
                logger.info("Message sent successfully to client")
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected_clients.append(connection)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            self.disconnect(client)

manager = ConnectionManager()

# Serve static files for the web interface BEFORE API routes
if os.path.exists("frontend/build"):
    app.mount("/static", StaticFiles(directory="frontend/build/static"), name="static")

# API Routes
@app.get("/")
async def root():
    """Root endpoint - serve the web interface or API info"""
    frontend_path = "frontend/build/index.html"
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    else:
        return {
            "message": "Lead Automation System API v2.0",
            "status": "running",
            "frontend": "not_built",
            "api_docs": "/docs",
            "api_endpoints": {
                "health": "/api/health",
                "config": "/api/config", 
                "leads": "/api/leads",
                "operations": "/api/operations"
            },
            "note": "Frontend not built. Use /docs for API interface or run 'python start.py --setup' to build frontend."
        }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now()}

@app.get("/api/test")
async def test_connection():
    """Test API connection"""
    print("TEST ENDPOINT CALLED - Frontend is connected!")
    return {"status": "connected", "message": "API is working"}

@app.get("/api/config")
async def get_config():
    """Get current configuration"""
    try:
        config = Config()
        return {
            "odoo_url": config.ODOO_URL,
            "odoo_db": config.ODOO_DB,
            "odoo_username": config.ODOO_USERNAME,
            "salesperson_name": config.SALESPERSON_NAME,
            "batch_size": config.BATCH_SIZE,
            "max_concurrent_requests": config.MAX_CONCURRENT_REQUESTS,
            "google_service_account_configured": os.path.exists(config.GOOGLE_SERVICE_ACCOUNT_FILE),
            "apify_token_configured": bool(config.APIFY_API_TOKEN),
        }
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/validate-config")
async def validate_config():
    """Validate system configuration"""
    try:
        config = Config()
        validation_result = config.validate()
        return validation_result
    except Exception as e:
        logger.error(f"Error validating config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/leads/count")
async def get_leads_count():
    """Get count of leads using same logic as /api/leads endpoint"""
    try:
        # Use the same logic as /api/leads to get consistent counts
        most_recent_leads = None
        most_recent_time = None

        for operation in active_operations.values():
            # Check both extract_leads and enrich_leads operations for the most recent data
            if ((operation.get('type') == 'extract_leads' or operation.get('type') == 'enrich_leads') and
                operation.get('status') == 'completed' and
                'leads_data' in operation):

                op_time = operation.get('started_at')
                if most_recent_time is None or op_time > most_recent_time:
                    most_recent_time = op_time
                    most_recent_leads = operation['leads_data']

        # If we have recent leads, use those
        if most_recent_leads:
            leads_data = most_recent_leads
        else:
            # Fallback: fetch fresh leads from Odoo
            config = Config()
            odoo_client = OdooClient(config)

            if not odoo_client.connect():
                raise HTTPException(status_code=500, detail="Failed to connect to Odoo")

            leads_data = odoo_client.get_unenriched_leads()

        # Count enriched vs unenriched leads
        total_count = len(leads_data)
        enriched_count = 0

        for lead in leads_data:
            enriched_status = lead.get('Enriched', 'No')
            if enriched_status in ['Yes', 'Partial']:
                enriched_count += 1

        unenriched_count = total_count - enriched_count

        return {
            "count": unenriched_count,
            "total": total_count,
            "enriched": enriched_count,
            "unenriched": unenriched_count
        }

    except Exception as e:
        logger.error(f"Error getting leads count: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/leads")
async def get_leads():
    """Get leads from the most recent extraction operation"""
    try:
        # First, try to get leads from the most recent extraction operation
        most_recent_leads = None
        most_recent_time = None
        
        for operation in active_operations.values():
            # Check both extract_leads and enrich_leads operations for the most recent data
            if ((operation.get('type') == 'extract_leads' or operation.get('type') == 'enrich_leads') and
                operation.get('status') == 'completed' and
                'leads_data' in operation):
                
                op_time = operation.get('started_at')
                if most_recent_time is None or op_time > most_recent_time:
                    most_recent_time = op_time
                    most_recent_leads = operation['leads_data']
        
        # If we have recent leads, use those
        if most_recent_leads:
            leads_data = most_recent_leads
        else:
            # Fallback: fetch fresh leads from Odoo
            config = Config()
            odoo_client = OdooClient(config)
            
            if not odoo_client.connect():
                raise HTTPException(status_code=500, detail="Failed to connect to Odoo")
            
            leads_data = odoo_client.get_unenriched_leads()
        
        # Convert to API format
        leads = []
        for lead in leads_data:
            # Handle different field name formats from different sources
            name = lead.get('Full Name') or lead.get('name', '')
            email = lead.get('email') or lead.get('email_from', '')
            company = lead.get('Company Name') or lead.get('partner_name', '')
            phone = lead.get('Phone') or lead.get('phone', '')
            linkedin = lead.get('LinkedIn Link') or lead.get('x_studio_linkedin_profile', '')
            job_title = lead.get('Job Role') or lead.get('function', '')
            quality_score = lead.get('Quality (Out of 5)') or lead.get('x_studio_quality')
            
            # Convert quality score to number if it exists
            if quality_score and str(quality_score).replace('.', '').isdigit():
                quality_score = float(quality_score)
            else:
                quality_score = None
                
            # Consider both 'Yes' and 'Partial' as enriched since quality scores are calculated
            enriched_status = lead.get('Enriched', 'No')
            enriched = enriched_status in ['Yes', 'Partial'] if 'Enriched' in lead else False
            
            # Extract enriched data
            industry = lead.get('Industry', '')
            company_size = lead.get('Company Size', '')
            description = lead.get('description', '')
            
            # Extract additional fields from Odoo
            mobile = lead.get('Mobile', '') or lead.get('mobile', '')
            title = lead.get('Title', '')
            contact_name = lead.get('Contact Name', '')
            salesperson = lead.get('Salesperson', '')
            website = lead.get('website', '')
            full_address = lead.get('Full Address', '')
            city = lead.get('City', '') or lead.get('city', '')
            state = lead.get('State', '')
            country = lead.get('Country', '')
            
            leads.append(LeadData(
                id=lead.get('id'),
                name=name,
                email=email,
                company=company,
                phone=phone,
                mobile=mobile,
                linkedin=linkedin,
                job_title=job_title,
                title=title,
                contact_name=contact_name,
                quality_score=quality_score,
                enriched=enriched,
                industry=industry,
                company_size=company_size,
                description=description,
                salesperson=salesperson,
                website=website,
                full_address=full_address,
                city=city,
                state=state,
                country=country
            ))
        
        return {"leads": leads, "total": len(leads)}
    
    except Exception as e:
        logger.error(f"Error getting leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/operations/extract-leads")
async def start_lead_extraction(background_tasks: BackgroundTasks, request: OperationRequest = OperationRequest()):
    """Start lead extraction from Odoo"""
    operation_id = str(uuid.uuid4())
    
    # Initialize operation tracking
    active_operations[operation_id] = {
        "id": operation_id,
        "type": "extract_leads",
        "status": "starting",
        "progress": 0.0,
        "current_step": "Initializing",
        "leads_processed": 0,
        "total_leads": 0,
        "errors": [],
        "started_at": datetime.now().isoformat(),
        "estimated_completion": None
    }
    
    # Start background task
    background_tasks.add_task(run_lead_extraction, operation_id, request)
    
    return {"operation_id": operation_id, "status": "started"}

@app.post("/api/operations/enrich-leads")
async def start_lead_enrichment(background_tasks: BackgroundTasks, request: OperationRequest = OperationRequest()):
    """Start lead enrichment process"""
    logger.info("ENRICHMENT ENDPOINT CALLED - Starting lead enrichment")
    print("ENRICHMENT ENDPOINT CALLED - Starting lead enrichment")
    print("=" * 80)
    print("ENRICHMENT STARTING NOW! ENDPOINT WAS CALLED SUCCESSFULLY!")
    print("=" * 80)
    operation_id = str(uuid.uuid4())
    
    # Initialize operation tracking
    active_operations[operation_id] = {
        "id": operation_id,
        "type": "enrich_leads",
        "status": "starting",
        "progress": 0.0,
        "current_step": "Initializing enrichment",
        "leads_processed": 0,
        "total_leads": 0,
        "errors": [],
        "started_at": datetime.now().isoformat(),
        "estimated_completion": None
    }
    
    # Start background task
    background_tasks.add_task(run_lead_enrichment, operation_id, request)
    
    return {"operation_id": operation_id, "status": "started"}

@app.post("/api/operations/full-pipeline")
async def start_full_pipeline(background_tasks: BackgroundTasks, request: OperationRequest = OperationRequest()):
    """Start full lead automation pipeline"""
    operation_id = str(uuid.uuid4())
    
    # Initialize operation tracking
    active_operations[operation_id] = {
        "id": operation_id,
        "type": "full_pipeline",
        "status": "starting",
        "progress": 0.0,
        "current_step": "Initializing pipeline",
        "leads_processed": 0,
        "total_leads": 0,
        "errors": [],
        "started_at": datetime.now().isoformat(),
        "estimated_completion": None
    }
    
    # Start background task
    background_tasks.add_task(run_full_pipeline, operation_id, request)
    
    return {"operation_id": operation_id, "status": "started"}

@app.get("/api/operations/{operation_id}")
async def get_operation_status(operation_id: str):
    """Get status of an operation"""
    if operation_id not in active_operations:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    return active_operations[operation_id]

@app.get("/api/operations")
async def get_all_operations():
    """Get status of all operations"""
    return {"operations": list(active_operations.values())}

@app.delete("/api/operations/{operation_id}")
async def cancel_operation(operation_id: str):
    """Cancel an operation"""
    if operation_id not in active_operations:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    active_operations[operation_id]["status"] = "cancelled"
    return {"message": "Operation cancelled"}

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back for now - can be enhanced for bidirectional communication
            await manager.send_personal_message(f"Received: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Background task functions
async def run_lead_extraction(operation_id: str, request: OperationRequest):
    """Background task for lead extraction"""
    try:
        # Update status
        await update_operation_status(operation_id, "running", 10, "Connecting to Odoo")
        
        config = Config()
        odoo_client = OdooClient(config)
        
        if not odoo_client.connect():
            await update_operation_status(operation_id, "failed", 0, "Failed to connect to Odoo", 
                                        errors=["Could not establish connection to Odoo"])
            return
        
        await update_operation_status(operation_id, "running", 30, "Extracting leads from Odoo")
        
        leads = odoo_client.get_unenriched_leads()
        
        await update_operation_status(operation_id, "running", 80, f"Found {len(leads)} unenriched leads")
        
        # Store leads in operation data for later use
        active_operations[operation_id]["leads_data"] = leads
        active_operations[operation_id]["total_leads"] = len(leads)
        
        await update_operation_status(operation_id, "completed", 100, 
                                    f"Successfully extracted {len(leads)} leads")
        
    except Exception as e:
        logger.error(f"Error in lead extraction: {e}")
        await update_operation_status(operation_id, "failed", 0, "Lead extraction failed", 
                                    errors=[str(e)])

async def run_lead_enrichment(operation_id: str, request: OperationRequest):
    """Background task for lead enrichment"""
    try:
        config = Config()
        
        await update_operation_status(operation_id, "running", 5, "Starting enrichment pipeline")
        
        # Get the most recent extracted leads
        most_recent_leads = None
        for op in active_operations.values():
            if (op.get('type') == 'extract_leads' and 
                op.get('status') == 'completed' and
                'leads_data' in op):
                most_recent_leads = op['leads_data']
                break
        
        if not most_recent_leads:
            await update_operation_status(operation_id, "failed", 0, "No extracted leads found",
                                        errors=["Please extract leads first before enriching"])
            return
        
        await update_operation_status(operation_id, "running", 10, f"Found {len(most_recent_leads)} leads to enrich")
        print(f"BACKEND: Found {len(most_recent_leads)} leads to enrich")
        print(f"BACKEND: First lead sample: {most_recent_leads[0] if most_recent_leads else 'None'}")

        # Check what data is available for enrichment
        for i, lead in enumerate(most_recent_leads):
            print(f"BACKEND: Lead {i+1} enrichment data:")
            print(f"  - Website: '{lead.get('website', 'MISSING')}'")
            print(f"  - LinkedIn Link: '{lead.get('LinkedIn Link', 'MISSING')}'")
            print(f"  - Company Name: '{lead.get('Company Name', 'MISSING')}'")
            print(f"  - Full Name: '{lead.get('Full Name', 'MISSING')}'")
            if i >= 2:  # Only show first 3 leads
                break
        
        # Initialize pipeline
        pipeline = EnrichmentPipeline(config)
        
        # Define progress callback
        async def progress_callback(progress, message):
            await update_operation_status(operation_id, "running", 10 + (progress * 0.8), message)
        
        # Process leads in optimized batches
        print(f"BACKEND: Starting enrichment for {len(most_recent_leads)} leads")
        try:
            enriched_leads = await pipeline._enrich_leads_batch(most_recent_leads, progress_callback)
            
            # Store enriched leads in this enrichment operation
            active_operations[operation_id]['leads_data'] = enriched_leads

            # Also update the most recent extraction operation with enriched data
            for op in active_operations.values():
                if (op.get('type') == 'extract_leads' and
                    op.get('status') == 'completed' and
                    'leads_data' in op):
                    op['leads_data'] = enriched_leads
                    break
            
            enriched_count = sum(1 for lead in enriched_leads if lead.get('Enriched') in ['Yes', 'Partial'])
            
            print(f"BACKEND: Enrichment completed for {enriched_count}/{len(enriched_leads)} leads")
            
        except Exception as e:
            logger.error(f"Error in batch enrichment: {e}")
            raise e
        
        await update_operation_status(operation_id, "completed", 100, 
                                    f"Enrichment completed: {enriched_count}/{len(most_recent_leads)} leads processed")
        
    except Exception as e:
        logger.error(f"Error in lead enrichment: {e}")
        await update_operation_status(operation_id, "failed", 0, "Lead enrichment failed", 
                                    errors=[str(e)])

async def run_full_pipeline(operation_id: str, request: OperationRequest):
    """Background task for full pipeline"""
    try:
        config = Config()
        pipeline = EnrichmentPipeline(config)
        
        await update_operation_status(operation_id, "running", 5, "Starting full automation pipeline")
        
        # Run the complete pipeline with progress updates
        result = await pipeline.run_full_pipeline()
        
        if result and result.get('status') == 'completed':
            stats = result.get('stats', {})
            await update_operation_status(operation_id, "completed", 100, 
                                        f"Pipeline completed: {stats.get('leads_enriched', 0)} leads enriched")
        else:
            await update_operation_status(operation_id, "failed", 0, "Pipeline failed",
                                        errors=[result.get('error', 'Unknown error')])
        
    except Exception as e:
        logger.error(f"Error in full pipeline: {e}")
        await update_operation_status(operation_id, "failed", 0, "Full pipeline failed", 
                                    errors=[str(e)])

async def update_operation_status(operation_id: str, status: str, progress: float, 
                                current_step: str, errors: List[str] = None):
    """Update operation status and broadcast to connected clients"""
    if operation_id in active_operations:
        active_operations[operation_id].update({
            "status": status,
            "progress": progress,
            "current_step": current_step,
            "last_updated": datetime.now().isoformat()
        })
        
        if errors:
            active_operations[operation_id]["errors"].extend(errors)
        
        # Create a JSON-serializable copy for WebSocket broadcast
        broadcast_data = active_operations[operation_id].copy()
        if "started_at" in broadcast_data and isinstance(broadcast_data["started_at"], datetime):
            broadcast_data["started_at"] = broadcast_data["started_at"].isoformat()
        
        # Broadcast to WebSocket clients
        try:
            message = {
                "type": "operation_update",
                "operation_id": operation_id,
                "data": broadcast_data
            }
            logger.info(f"Broadcasting WebSocket message: {message}")
            await manager.broadcast(message)
        except Exception as e:
            logger.error(f"Error broadcasting to WebSocket: {e}")

@app.get("/api/export/csv")
async def export_leads_csv():
    """Export all leads to CSV format"""
    try:
        from modules.csv_exporter import CSVExporter
        from config import Config

        config = Config()
        csv_exporter = CSVExporter(config)

        # Get all leads from the API
        leads_response = await get_leads()
        leads_data = []

        for lead in leads_response["leads"]:
            # Convert LeadData object to dict for CSV export
            lead_dict = {
                'id': lead.id,
                'Full Name': lead.name,
                'Company Name': lead.company,
                'LinkedIn Link': lead.linkedin,
                'Company Size': '',
                'Industry': lead.industry,
                'Company Revenue Estimated': '',
                'Job Role': lead.job_title,
                'Company year EST': '',
                'Phone': lead.phone,
                'Mobile': lead.mobile,
                'Salesperson': lead.salesperson,
                'Quality (Out of 5)': lead.quality_score,
                'Enriched': 'Yes' if lead.enriched else 'No',
                'email': lead.email,
                'website': lead.website,
                'city': lead.city,
                'state': lead.state,
                'country': lead.country,
                'description': lead.description
            }
            leads_data.append(lead_dict)

        if not leads_data:
            raise HTTPException(status_code=404, detail="No leads found to export")

        # Generate timestamp for filename
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"leads_export_{timestamp}.csv"

        # Export to CSV
        csv_path = csv_exporter.export_leads_to_csv(leads_data, filename)

        # Return the CSV file
        return FileResponse(
            path=csv_path,
            filename=filename,
            media_type='text/csv',
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logger.error(f"Error exporting CSV: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

# Handle React Router routes - this should be at the very end
if os.path.exists("frontend/build"):
    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        # Don't handle paths that start with /api or /ws
        if path.startswith("api/") or path.startswith("ws"):
            raise HTTPException(status_code=404, detail="Not found")
            
        # Handle specific files like manifest.json, favicon.ico, etc.
        file_path = f"frontend/build/{path}"
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        
        # For all other routes (React Router), serve the main index.html
        return FileResponse("frontend/build/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )
