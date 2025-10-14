import sys
import os
import re
import html
from typing import Dict, List, Any, Tuple, Optional, Iterable
import requests
from itertools import count
from config import Config
import logging

logger = logging.getLogger(__name__)

class OdooRpcError(Exception):
    """Custom exception for Odoo RPC errors"""
    pass

class OdooClient:
    """Enhanced Odoo client for lead extraction and management"""
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.session = None
        self.uid = None
        self.call_kw_endpoint = None
        self._id_counter = count(1)
        
    def _make_endpoint(self, base_url: str, path: str) -> str:
        """Create full endpoint URL"""
        return f"{base_url.rstrip('/')}{path}"
    
    def _json_http(self, endpoint: str, params: Dict[str, Any]) -> Any:
        """Make JSON-RPC HTTP request"""
        payload = {
            'jsonrpc': '2.0',
            'method': 'call',
            'params': params,
            'id': next(self._id_counter),
        }
        resp = self.session.post(endpoint, json=payload, timeout=60, allow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
        if 'error' in data and data['error']:
            raise OdooRpcError(str(data['error']))
        return data.get('result')
    
    def _call_kw(self, model: str, method: str, args: List[Any] = None, kwargs: Dict[str, Any] = None) -> Any:
        """Make call_kw request to Odoo"""
        if not self.call_kw_endpoint:
            raise RuntimeError("Not connected to Odoo. Call connect() first.")
        
        return self._json_http(self.call_kw_endpoint, {
            'model': model,
            'method': method,
            'args': args or [],
            'kwargs': kwargs or {},
        })
    
    def connect(self) -> bool:
        """Connect to Odoo and authenticate"""
        try:
            self.session = requests.Session()
            self.session.verify = False if self.config.ODOO_INSECURE_SSL else True
            self.session.headers.update({'Content-Type': 'application/json'})
            
            base_url = self.config.ODOO_URL
            auth_endpoint = self._make_endpoint(base_url, "/web/session/authenticate")
            self.call_kw_endpoint = self._make_endpoint(base_url, "/web/dataset/call_kw")
            
            try:
                result = self._json_http(auth_endpoint, {
                    'db': self.config.ODOO_DB,
                    'login': self.config.ODOO_USERNAME,
                    'password': self.config.ODOO_PASSWORD,
                })
            except requests.HTTPError as http_err:
                # Handle Odoo redirect case
                resp = http_err.response
                if resp and resp.status_code == 404 and 'www.odoo.com/typo' in (resp.url or ''):
                    try:
                        from urllib.parse import urlparse, parse_qs
                        query = parse_qs(urlparse(resp.url).query)
                        hosting = (query.get('hosting') or [None])[0]
                        if hosting:
                            base_url = f"https://{hosting}"
                            auth_endpoint = self._make_endpoint(base_url, "/web/session/authenticate")
                            self.call_kw_endpoint = self._make_endpoint(base_url, "/web/dataset/call_kw")
                            result = self._json_http(auth_endpoint, {
                                'db': self.config.ODOO_DB,
                                'login': self.config.ODOO_USERNAME,
                                'password': self.config.ODOO_PASSWORD,
                            })
                        else:
                            raise
                    except Exception:
                        raise
                else:
                    raise
            
            self.uid = (result or {}).get('uid')
            if not self.uid:
                raise RuntimeError("Authentication failed. Check credentials.")
            
            logger.info(f"Successfully connected to Odoo as user ID: {self.uid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Odoo: {e}")
            return False
    
    def find_user_id(self, name: str) -> Optional[int]:
        """Find user ID by name"""
        try:
            # Exact match first
            users = self._call_kw('res.users', 'search_read', [], {
                'domain': [['name', '=', name]],
                'fields': ['name'],
                'limit': 1,
            })
            if users:
                return users[0]['id']
            
            # Fallback to ilike
            users = self._call_kw('res.users', 'search_read', [], {
                'domain': [['name', 'ilike', name]],
                'fields': ['name'],
                'limit': 1,
            })
            if users:
                return users[0]['id']
            
            return None
        except Exception as e:
            logger.error(f"Error finding user '{name}': {e}")
            return None
    

    def get_leads_by_emails(
        self,
        emails: List[str],
        fields: Optional[List[str]] = None,
        salesperson_name: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch CRM leads keyed by email address."""

        if not emails:
            return {}

        unique_emails = sorted({(email or '').strip().lower() for email in emails if email})
        if not unique_emails:
            return {}

        fields_to_fetch = fields or [
            'id',
            'name',
            'contact_name',
            'partner_name',
            'email_from',
            'phone',
            'mobile',
            'function',
            'stage_id',
            'user_id',
            'description',
            'expected_revenue',
        ]

        results: Dict[str, Dict[str, Any]] = {}
        user_id: Optional[int] = None
        if salesperson_name:
            user_id = self.find_user_id(salesperson_name)
            if not user_id:
                logger.warning("Salesperson '%s' not found while filtering leads by email", salesperson_name)

        chunk_size = 50
        for start_index in range(0, len(unique_emails), chunk_size):
            chunk = unique_emails[start_index:start_index + chunk_size]
            if user_id:
                domain: List[Any] = [['user_id', '=', user_id], ['email_from', 'in', chunk]]
            else:
                domain = [['email_from', 'in', chunk]]

            try:
                records = self._call_kw(
                    'crm.lead',
                    'search_read',
                    [domain],
                    {'fields': fields_to_fetch, 'limit': len(chunk)},
                )
            except Exception as exc:
                logger.error("Error fetching leads by email chunk: %s", exc)
                continue

            for record in records or []:
                email_value = (record.get('email_from') or '').strip().lower()
                if not email_value:
                    continue

                processed = dict(record)
                stage_id = record.get('stage_id')
                if isinstance(stage_id, (list, tuple)) and len(stage_id) == 2:
                    processed['stage_name'] = stage_id[1]
                user_ref = record.get('user_id')
                if isinstance(user_ref, (list, tuple)) and len(user_ref) == 2:
                    processed['salesperson_name'] = user_ref[1]
                name_source = record.get('contact_name') or record.get('name') or ''
                processed['first_name'] = name_source.split()[0] if name_source else ''
                results[email_value] = processed

        return results

    def get_leads_by_names(
        self,
        names: List[str],
        fields: Optional[List[str]] = None,
        salesperson_name: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch CRM leads by contact name (for cases where email is missing)."""

        if not names:
            return {}

        unique_names = sorted({(name or '').strip() for name in names if name})
        if not unique_names:
            return {}

        fields_to_fetch = fields or [
            'id',
            'name',
            'contact_name',
            'partner_name',
            'email_from',
            'phone',
            'mobile',
            'function',
            'stage_id',
            'user_id',
            'description',
            'expected_revenue',
        ]

        results: Dict[str, Dict[str, Any]] = {}
        user_id: Optional[int] = None
        if salesperson_name:
            user_id = self.find_user_id(salesperson_name)
            if not user_id:
                logger.warning("Salesperson '%s' not found while filtering leads by name", salesperson_name)

        chunk_size = 50
        for start_index in range(0, len(unique_names), chunk_size):
            chunk = unique_names[start_index:start_index + chunk_size]
            name_filters: List[Any] = []
            for i, name in enumerate(chunk):
                if i > 0:
                    name_filters.insert(0, '|')
                name_filters.extend([
                    '|',
                    ['contact_name', 'ilike', name],
                    ['name', 'ilike', name]
                ])

            if user_id:
                domain: List[Any] = [['user_id', '=', user_id]] + name_filters
            else:
                domain = name_filters

            try:
                records = self._call_kw(
                    'crm.lead',
                    'search_read',
                    [domain],
                    {'fields': fields_to_fetch, 'limit': len(chunk) * 5},
                )
            except Exception as exc:
                logger.error("Error fetching leads by name chunk: %s", exc)
                continue

            for record in records or []:
                contact_name = (record.get('contact_name') or record.get('name') or '').strip()
                if not contact_name:
                    continue

                processed = dict(record)
                stage_id = record.get('stage_id')
                if isinstance(stage_id, (list, tuple)) and len(stage_id) == 2:
                    processed['stage_name'] = stage_id[1]
                user_ref = record.get('user_id')
                if isinstance(user_ref, (list, tuple)) and len(user_ref) == 2:
                    processed['salesperson_name'] = user_ref[1]
                processed['first_name'] = contact_name.split()[0] if contact_name else ''

                # Key by normalized name for matching
                results[contact_name.lower()] = processed

        return results

    def get_unenriched_leads(self, salesperson_name: str = None, batch_size: int = 500) -> List[Dict[str, Any]]:
        """Extract unenriched leads from Odoo"""
        salesperson_name = salesperson_name or self.config.SALESPERSON_NAME
        
        try:
            user_id = self.find_user_id(salesperson_name)
            if not user_id:
                raise RuntimeError(f"Salesperson '{salesperson_name}' not found")
            
            # Fields to fetch - expanded to include all available Odoo data
            fields_to_fetch = [
                'id',
                'name',               # Full Name (from opportunity name)
                'partner_name',       # Company Name
                'email_from',         # Email
                'phone',              # Phone
                'mobile',             # Mobile phone
                'function',           # Job Role/Position
                'contact_name',       # Contact Name
                'title',              # Title (Mr, Ms, etc)
                'x_studio_linkedin_profile',  # LinkedIn Profile (html field)
                'website',            # Website
                'x_studio_quality',   # Quality (Out of 5)
                'user_id',            # Salesperson
                'street',             # Street address
                'street2',            # Street 2
                'city',               # City
                'state_id',           # State
                'zip',                # ZIP code
                'country_id',         # Country
                'partner_id',         # Partner/Company ID for additional data
            ]
            
            # Domain filter: Salesperson = specified user AND not enriched (empty quality)
            domain = [
                '&',
                ['user_id', '=', user_id],
                '|', '|',
                ['x_studio_quality', '=', False],
                ['x_studio_quality', '=', None],
                ['x_studio_quality', '=', ''],
            ]
            
            # Get lead IDs first
            lead_ids = self._call_kw('crm.lead', 'search', [domain], {'limit': 0})
            logger.info(f"Found {len(lead_ids)} unenriched leads for {salesperson_name}")
            
            # Batch read leads
            all_records = []
            for start in range(0, len(lead_ids), batch_size):
                chunk = lead_ids[start:start + batch_size]
                records = self._call_kw('crm.lead', 'read', [chunk], {'fields': fields_to_fetch})
                all_records.extend(records)
            
            # Process and clean the data
            processed_leads = []
            for lead in all_records:
                # Extract LinkedIn URL from HTML field
                linkedin_link = self._extract_first_url_from_html(lead.get('x_studio_linkedin_profile') or '')
                
                # Get salesperson name
                salesperson = ''
                if isinstance(lead.get('user_id'), (list, tuple)) and len(lead['user_id']) == 2:
                    salesperson = lead['user_id'][1] or ''
                
                # Get state name  
                state = ''
                if isinstance(lead.get('state_id'), (list, tuple)) and len(lead['state_id']) == 2:
                    state = lead['state_id'][1] or ''
                
                # Get country name
                country = ''
                if isinstance(lead.get('country_id'), (list, tuple)) and len(lead['country_id']) == 2:
                    country = lead['country_id'][1] or ''
                
                # Format address
                address_parts = [
                    lead.get('street', ''),
                    lead.get('street2', ''),
                    lead.get('city', ''),
                    state,
                    lead.get('zip', ''),
                    country
                ]
                full_address = ', '.join([part for part in address_parts if part]).strip(', ')
                
                processed_lead = {
                    'id': lead.get('id'),
                    'Full Name': lead.get('name') or '',
                    'Company Name': lead.get('partner_name') or '',
                    'LinkedIn Link': linkedin_link,
                    'Company Size': '',  # To be enriched
                    'Industry': '',  # To be enriched
                    'Company Revenue Estimated': '',  # To be enriched
                    'Job Role': lead.get('function') or '',
                    'Company year EST': '',  # To be enriched
                    'Phone': lead.get('phone') or '',
                    'Mobile': lead.get('mobile') or '',
                    'Salesperson': salesperson,
                    'Quality (Out of 5)': '',  # To be enriched
                    'Enriched': 'No',
                    'Title': lead.get('title') or '',
                    'Contact Name': lead.get('contact_name') or '',
                    'Full Address': full_address,
                    'Street': lead.get('street', ''),
                    'Street2': lead.get('street2', ''),
                    'City': lead.get('city', ''),
                    'State': state,
                    'ZIP': lead.get('zip', ''),
                    'Country': country,
                    # Additional fields for processing
                    'email': lead.get('email_from') or '',
                    'website': lead.get('website') or '',
                }
                processed_leads.append(processed_lead)
            
            return processed_leads
            
        except Exception as e:
            logger.error(f"Error extracting leads: {e}")
            return []
    
    def update_lead(self, lead_id: int, values: Dict[str, Any]) -> bool:
        """Update a lead in Odoo with enriched data"""
        try:
            # Map our column names to Odoo field names based on your requirements
            odoo_fields = {}

            # Company Name (partner_name in crm.lead)
            if 'Company Name' in values and values['Company Name']:
                odoo_fields['partner_name'] = str(values['Company Name']).strip()

            # Website (website in crm.lead)
            if 'website' in values and values['website']:
                website = str(values['website']).strip()
                if website and not website.startswith(('http://', 'https://')):
                    website = f'https://{website}'
                odoo_fields['website'] = website

            # Language (lang_id in crm.lead) - would need to map to language ID
            # For now, we'll skip this as it requires language code mapping

            # Email (email_from in crm.lead)
            if 'email' in values and values['email']:
                email = str(values['email']).strip()
                if '@' in email:
                    odoo_fields['email_from'] = email

            # Job Position (function in crm.lead)
            if 'Job Role' in values and values['Job Role']:
                odoo_fields['function'] = str(values['Job Role']).strip()

            # Phone (phone in crm.lead)
            if 'Phone' in values and values['Phone']:
                phone = str(values['Phone']).strip()
                if phone and phone.lower() not in ['not found', 'n/a', 'none']:
                    odoo_fields['phone'] = phone

            # Mobile (mobile in crm.lead)
            if 'Mobile' in values and values['Mobile']:
                mobile = str(values['Mobile']).strip()
                if mobile and mobile.lower() not in ['not found', 'n/a', 'none']:
                    odoo_fields['mobile'] = mobile

            # LinkedIn Profile (x_studio_linkedin_profile)
            if 'LinkedIn Link' in values and values['LinkedIn Link']:
                linkedin = str(values['LinkedIn Link']).strip()
                if linkedin and linkedin.lower() not in ['not found', 'n/a', 'none']:
                    # Store as HTML link for the HTML field
                    linkedin_html = f'<a href="{linkedin}" target="_blank">{linkedin}</a>'
                    odoo_fields['x_studio_linkedin_profile'] = linkedin_html

            # Quality (x_studio_quality) - selection field with keys like "[0/5]", "[1/5]", etc.
            if 'Quality (Out of 5)' in values and values['Quality (Out of 5)']:
                quality = str(values['Quality (Out of 5)']).strip()
                if quality and quality.isdigit():
                    # Map quality to the selection key format used in Odoo (e.g. '4/5')
                    quality_key = f"{quality}/5"
                    odoo_fields['x_studio_quality'] = quality_key

            # City and Country fields if available
            if 'City' in values and values['City']:
                city = str(values['City']).strip()
                if city and city.lower() not in ['not found', 'n/a', 'none']:
                    odoo_fields['city'] = city

            # For country, we would need to map to country_id, which requires looking up the country ID
            # We'll store it in a notes field or create a custom field for now

            # Log what we're updating
            if odoo_fields:
                logger.info(f"Updating lead {lead_id} with fields: {list(odoo_fields.keys())}")
                self._call_kw('crm.lead', 'write', [[lead_id], odoo_fields])
                logger.info(f"Successfully updated lead {lead_id} with enriched data")

            # Build internal note with additional enrichment info
            note_parts = []
            note_parts.append("📊 **Enrichment Data**\n")

            # Company LinkedIn
            if 'Company LinkedIn' in values and values['Company LinkedIn']:
                company_linkedin = str(values['Company LinkedIn']).strip()
                if company_linkedin and company_linkedin.lower() not in ['not found', 'n/a', 'none']:
                    note_parts.append(f"**Company LinkedIn:** {company_linkedin}")

            # Industry
            if 'Industry' in values and values['Industry']:
                industry = str(values['Industry']).strip()
                if industry and industry.lower() not in ['not found', 'n/a', 'none']:
                    note_parts.append(f"**Industry:** {industry}")

            # Company Size
            if 'Company Size' in values and values['Company Size']:
                company_size = str(values['Company Size']).strip()
                if company_size and company_size.lower() not in ['not found', 'n/a', 'none']:
                    note_parts.append(f"**Company Size:** {company_size}")

            # Revenue Estimate
            if 'Company Revenue Estimated' in values and values['Company Revenue Estimated']:
                revenue = str(values['Company Revenue Estimated']).strip()
                if revenue and revenue.lower() not in ['not found', 'n/a', 'none']:
                    note_parts.append(f"**Revenue Estimate:** {revenue}")

            # Founded
            if 'Company year EST' in values and values['Company year EST']:
                founded = str(values['Company year EST']).strip()
                if founded and founded.lower() not in ['not found', 'n/a', 'none']:
                    note_parts.append(f"**Founded:** {founded}")

            # Location
            if 'Location' in values and values['Location']:
                location = str(values['Location']).strip()
                if location and location.lower() not in ['not found', 'n/a', 'none']:
                    note_parts.append(f"**Location:** {location}")

            # Company Description
            if 'Company Description' in values and values['Company Description']:
                description = str(values['Company Description']).strip()
                if description and description.lower() not in ['not found', 'n/a', 'none']:
                    note_parts.append(f"**Company Description:** {description}")

            # Notes
            if 'Notes' in values and values['Notes']:
                notes = str(values['Notes']).strip()
                if notes and notes.lower() not in ['not found', 'n/a', 'none']:
                    note_parts.append(f"**Notes:** {notes}")

            # Append internal note if we have any data
            if len(note_parts) > 1:  # More than just the header
                internal_note = "\n".join(note_parts)
                self.append_internal_note(lead_id, internal_note, subject="Perplexity Enrichment Data")

            return True

        except Exception as e:
            logger.error(f"Error updating lead {lead_id}: {e}")
            return False
    
    def bulk_update_leads(self, lead_updates: List[Tuple[int, Dict[str, Any]]]) -> int:
        """Bulk update multiple leads"""
        success_count = 0
        for lead_id, values in lead_updates:
            if self.update_lead(lead_id, values):
                success_count += 1
        return success_count

    def append_internal_note(self, lead_id: int, note: str, subject: Optional[str] = None) -> bool:
        """Append an internal note to a lead via message_post."""
        cleaned = (note or "").strip()
        if not cleaned:
            logger.debug("append_internal_note called with empty note for lead %s", lead_id)
            return False

        try:
            kwargs = {'subtype_xmlid': 'mail.mt_note'}
            if subject:
                kwargs['subject'] = subject
            self._call_kw('crm.lead', 'message_post', [[lead_id], cleaned], kwargs)
            logger.info("Appended internal note to lead %s", lead_id)
            return True
        except Exception as exc:
            logger.error("Failed to append internal note to lead %s: %s", lead_id, exc)
            return False

    def get_lead_details(self, lead_id: int, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Fetch a single lead/opportunity record by ID."""
        default_fields = fields or [
            'id',
            'name',
            'type',
            'stage_id',
            'probability',
            'active',
            'won_status',
            'lost_reason_id',
            'expected_revenue',
            'prorated_revenue',
            'recurring_revenue',
            'partner_id',
            'partner_name',
            'contact_name',
            'email_from',
            'phone',
            'mobile',
            'function',
            'title',
            'user_id',
            'team_id',
            'campaign_id',
            'medium_id',
            'source_id',
            'referred',
            'tag_ids',
            'description',
            'lead_properties',
            'message_ids',
            'message_partner_ids',
            'date_deadline',
            'date_closed',
            'date_open',
            'date_conversion',
            'date_last_stage_update',
            'create_date',
            'write_date',
            'company_id',
            'priority',
            'kanban_state',
            # Address fields
            'street',
            'street2',
            'city',
            'state_id',
            'zip',
            'country_id',
            'website',
            'lang_id',
            # Custom studio fields (x_studio_*)
            'x_studio_service',
            'x_studio_agreement_type',
            'x_studio_quality',
            'x_studio_linkedin_profile',
        ]
        try:
            records = self._call_kw(
                'crm.lead',
                'read',
                [[lead_id]],
                {'fields': default_fields},
            )
        except Exception as exc:
            logger.error("Error fetching lead %s: %s", lead_id, exc)
            return {}
        if not records:
            return {}
        record = records[0]
        # Flatten many2one tuples for convenience
        for key in list(record.keys()):
            value = record[key]
            if isinstance(value, (list, tuple)) and len(value) == 2 and isinstance(value[0], int):
                record[f"{key}_id"] = value[0]
                record[key] = value[1]
        return record

    def get_lost_leads(
        self,
        limit: int = 20,
        salesperson_name: Optional[str] = None,
        fields: Optional[List[str]] = None,
        type_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return recently lost leads/opportunities.
        Fetches leads with probability = 0, regardless of active status.
        Optionally filter by type: 'lead' or 'opportunity'.
        """
        user_id: Optional[int] = None
        if salesperson_name:
            user_id = self.find_user_id(salesperson_name)
            if not user_id:
                logger.warning("Salesperson '%s' not found while fetching lost leads", salesperson_name)

        # Build domain with type filter
        if type_filter and type_filter.lower() in ['lead', 'opportunity']:
            domain: List[Any] = [
                ['type', '=', type_filter.lower()],
                ['probability', '=', 0],
            ]
            logger.info(f"Filtering lost leads by type: {type_filter.lower()}")
        else:
            domain = [
                ['type', 'in', ['lead', 'opportunity']],
                ['probability', '=', 0],
            ]
            logger.info("Fetching all lost leads (both leads and opportunities)")

        if user_id:
            domain.append(['user_id', '=', user_id])

        fields_to_fetch = fields or [
            'id', 'name', 'stage_id', 'lost_reason_id',
            'expected_revenue', 'probability', 'partner_name', 'email_from',
            'phone', 'mobile', 'user_id', 'create_date', 'write_date', 'contact_name',
            'type', 'campaign_id', 'source_id', 'tag_ids', 'description', 'active',
        ]

        try:
            records = self._call_kw(
                'crm.lead',
                'search_read',
                [domain],
                {
                    'fields': fields_to_fetch,
                    'limit': limit,
                    'order': 'write_date desc',
                    'context': {'active_test': False},
                },
            ) or []
        except Exception as exc:
            logger.error("Error fetching lost leads: %s", exc)
            return []

        for record in records:
            for key, value in list(record.items()):
                if isinstance(value, (list, tuple)) and len(value) == 2 and isinstance(value[0], int):
                    record[f"{key}_id"] = value[0]
                    record[key] = value[1]

        if records:
            logger.info(f"Found {len(records)} lost leads. Sample type values: {[r.get('type') for r in records[:3]]}")

        return records

    def get_lead_messages(
        self,
        lead_id: int,
        limit: int = 20,
        message_types: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch chatter messages (emails, notes, notifications) for a lead."""
        """Fetch chatter messages (emails, notes, notifications) for a lead."""
        domain: List[Any] = [
            ['model', '=', 'crm.lead'],
            ['res_id', '=', lead_id],
        ]
        message_types_list = list(message_types) if message_types else None
        if message_types_list:
            domain.append(['message_type', 'in', message_types_list])

        fields = [
            'id',
            'date',
            'author_id',
            'email_from',
            'body',
            'subject',
            'message_type',
            'subtype_id',
            'partner_ids',
            'model',
            'res_id',
            'tracking_value_ids',
            'reply_to',
            'parent_id',
        ]

        try:
            messages = self._call_kw(
                'mail.message',
                'search_read',
                [domain],
                {
                    'fields': fields,
                    'limit': limit,
                    'order': 'date desc',
                },
            ) or []
        except Exception as exc:
            logger.error("Error fetching messages for lead %s: %s", lead_id, exc)
            return []

        for message in messages:
            subtype = message.get('subtype_id')
            if isinstance(subtype, (list, tuple)) and len(subtype) == 2:
                message['subtype_name'] = subtype[1]
                message['subtype_id'] = subtype[0]
            author = message.get('author_id')
            if isinstance(author, (list, tuple)) and len(author) == 2:
                message['author_name'] = author[1]
                message['author_id'] = author[0]
        return messages
    
    def _extract_first_url_from_html(self, html_text: str) -> str:
        """Extract first URL from HTML text"""
        if not html_text:
            return ""
        try:
            # Find first href URL
            match = re.search(r'href=["\']([^"\']+)["\']', html_text, flags=re.IGNORECASE)
            if match:
                return match.group(1)
            # Fallback: strip tags to get visible text
            text = re.sub(r"<[^>]+>", " ", html_text)
            text = html.unescape(text)
            text = re.sub(r"\s+", " ", text).strip()
            return text
        except Exception:
            return html_text

    def _map_language_to_code(self, language: str) -> Optional[str]:
        """Map language name to Odoo language code"""
        language_mapping = {
            'english': 'en_US',
            'arabic': 'ar_001',
            'french': 'fr_FR',
            'spanish': 'es_ES',
            'german': 'de_DE',
            'italian': 'it_IT',
            'portuguese': 'pt_PT',
            'russian': 'ru_RU',
            'chinese': 'zh_CN',
            'japanese': 'ja_JP',
            'korean': 'ko_KR',
            'dutch': 'nl_NL',
            'turkish': 'tr_TR',
            'hebrew': 'he_IL',
            'hindi': 'hi_IN'
        }

        return language_mapping.get(language.lower())

