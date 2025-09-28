import sys
import os
import re
import html
from typing import Dict, List, Any, Tuple, Optional
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
                return True
            else:
                logger.warning(f"No valid fields to update for lead {lead_id}")
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
