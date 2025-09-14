import sys
import os
import csv
import re
import html
from typing import Dict, List, Any, Tuple
import ssl
import json
from itertools import count
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

try:
    import requests
except Exception:
    requests = None


ODOO_URL = os.getenv('ODOO_URL', 'https://prezlab-staging-22061821.dev.odoo.com')
ODOO_DB = os.getenv('ODOO_DB', 'prezlab-staging-22061821')
ODOO_USERNAME = os.getenv('ODOO_USERNAME')
ODOO_PASSWORD = os.getenv('ODOO_PASSWORD')

SALESPERSON_NAME = os.getenv('SALESPERSON_NAME', 'Dareen Fuqaha')
OUTPUT_CSV = "leads_dareen_fuqaha.csv"

"""
This script uses JSON-RPC (HTTP) instead of XML-RPC to better handle redirects and staging cert issues.
"""

# Allow disabling SSL verification for staging hosts with mismatched certs
INSECURE_SSL = str(os.environ.get("ODOO_INSECURE_SSL", "0")).lower() in ("1", "true", "yes")

CURRENT_BASE_URL = ODOO_URL.rstrip('/')

def _make_endpoint(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"
_id_counter = count(1)


class OdooRpcError(Exception):
    pass


def extract_first_url_from_html(html_text: str) -> str:
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


def prevent_excel_date(value: str) -> str:
    """Avoid Excel interpreting values like 1/5 as dates by using the fraction slash.
    If value matches N/5 for N in 0..5, replace '/' with '⁄'.
    """
    if not value:
        return ''
    text = str(value).strip()
    if re.fullmatch(r"[0-5]/5", text):
        return text.replace('/', '⁄')
    return text


def to_excel_column_name(index_one_based: int) -> str:
    """Convert 1-based index to Excel column name (1 -> A, 27 -> AA)."""
    name = []
    n = index_one_based
    while n > 0:
        n, rem = divmod(n - 1, 26)
        name.append(chr(65 + rem))
    return ''.join(reversed(name))


def get_field_definitions(session: 'requests.Session', call_kw_endpoint: str, model: str) -> Dict[str, Any]:
    return _call_kw(session, call_kw_endpoint, model, 'fields_get', [], {'attributes': ['string', 'type', 'selection']})


def _json_http(session: 'requests.Session', endpoint: str, params: Dict[str, Any]) -> Any:
    payload = {
        'jsonrpc': '2.0',
        'method': 'call',
        'params': params,
        'id': next(_id_counter),
    }
    resp = session.post(endpoint, json=payload, timeout=60, allow_redirects=True)
    resp.raise_for_status()
    data = resp.json()
    if 'error' in data and data['error']:
        raise OdooRpcError(str(data['error']))
    return data.get('result')


def _call_kw(session: 'requests.Session', call_kw_endpoint: str, model: str, method: str,
             args: List[Any] | None = None, kwargs: Dict[str, Any] | None = None) -> Any:
    return _json_http(session, call_kw_endpoint, {
        'model': model,
        'method': method,
        'args': args or [],
        'kwargs': kwargs or {},
    })


def connect_to_odoo() -> Tuple['requests.Session', int, str]:
    if requests is None:
        raise RuntimeError("The 'requests' package is required. Please install it with 'pip install requests'.")
    session = requests.Session()
    # Follow redirects by default; disable SSL verification if requested
    session.verify = False if INSECURE_SSL else True
    session.headers.update({'Content-Type': 'application/json'})
    base_url = CURRENT_BASE_URL
    auth_endpoint = _make_endpoint(base_url, "/web/session/authenticate")
    call_kw_endpoint = _make_endpoint(base_url, "/web/dataset/call_kw")
    try:
        result = _json_http(session, auth_endpoint, {
            'db': ODOO_DB,
            'login': ODOO_USERNAME,
            'password': ODOO_PASSWORD,
        })
    except requests.HTTPError as http_err:
        # Handle Odoo typo redirect case: try switching to the hosting domain if indicated
        resp = http_err.response
        if resp is not None and resp.status_code == 404 and 'www.odoo.com/typo' in (resp.url or ''):
            try:
                from urllib.parse import urlparse, parse_qs
                query = parse_qs(urlparse(resp.url).query)
                hosting = (query.get('hosting') or [None])[0]
                if hosting:
                    base_url = f"https://{hosting}"
                    auth_endpoint = _make_endpoint(base_url, "/web/session/authenticate")
                    call_kw_endpoint = _make_endpoint(base_url, "/web/dataset/call_kw")
                    # Retry authenticate on hosting domain
                    result = _json_http(session, auth_endpoint, {
                        'db': ODOO_DB,
                        'login': ODOO_USERNAME,
                        'password': ODOO_PASSWORD,
                    })
                else:
                    raise
            except Exception:
                raise
        else:
            raise
    uid = (result or {}).get('uid')
    if not uid:
        raise RuntimeError("Authentication to Odoo failed. Check credentials.")
    return session, uid, call_kw_endpoint


def get_selection_labels(session: 'requests.Session', call_kw_endpoint: str, uid: int, password: str,
                         model: str, field_names: List[str]) -> Dict[str, Dict[str, str]]:
    fields_def = _call_kw(session, call_kw_endpoint, model, 'fields_get', [field_names], {
        'attributes': ['string', 'type', 'selection']
    })
    mapping: Dict[str, Dict[str, str]] = {}
    for field, meta in fields_def.items():
        if meta.get('type') == 'selection':
            mapping[field] = {str(k): v for k, v in (meta.get('selection') or [])}
    return mapping


def find_user_id(session: 'requests.Session', call_kw_endpoint: str, uid: int, password: str, name: str) -> int:
    # Exact name match first
    users = _call_kw(session, call_kw_endpoint, 'res.users', 'search_read', [], {
        'domain': [['name', '=', name]],
        'fields': ['name'],
        'limit': 1,
    })
    if users:
        return users[0]['id']
    # Fallback to ilike
    users = _call_kw(session, call_kw_endpoint, 'res.users', 'search_read', [], {
        'domain': [['name', 'ilike', name]],
        'fields': ['name'],
        'limit': 1,
    })
    if users:
        return users[0]['id']
    raise RuntimeError(f"User with name '{name}' not found.")


def batched_read_leads(session: 'requests.Session', call_kw_endpoint: str, uid: int, password: str,
                        domain: List[List[Any]], fields: List[str], batch_size: int = 500) -> List[Dict[str, Any]]:
    ids = _call_kw(session, call_kw_endpoint, 'crm.lead', 'search', [domain], {'limit': 0})
    all_records: List[Dict[str, Any]] = []
    for start in range(0, len(ids), batch_size):
        chunk = ids[start:start + batch_size]
        recs = _call_kw(session, call_kw_endpoint, 'crm.lead', 'read', [chunk], {'fields': fields})
        all_records.extend(recs)
    return all_records


def main() -> None:
    try:
        session, uid, call_kw_endpoint = connect_to_odoo()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    try:
        user_id = find_user_id(session, call_kw_endpoint, uid, ODOO_PASSWORD, SALESPERSON_NAME)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    fields_to_fetch = [
        'name',               # Opportunity
        'email_from',         # Email
        'city',               # City
        'country_id',         # Country (m2o)
        'user_id',            # Salesperson (m2o)
        'phone',              # Phone
        'function',           # Job Position
        'x_studio_linkedin_profile',  # LinkedIn Profile (html)
        'website',            # Website
        'x_studio_quality',   # Quality (selection)
        'x_studio_service',   # Service (selection)
        'partner_id',         # Customer (m2o)
        'partner_name',       # Company Name (char)
    ]

    try:
        selection_map = get_selection_labels(
            session, call_kw_endpoint, uid, ODOO_PASSWORD, 'crm.lead', ['x_studio_quality', 'x_studio_service']
        )
    except Exception:
        selection_map = {}

    # Filter: Salesperson = Dareen AND Quality empty/undefined
    domain = [
        '&',
        ['user_id', '=', user_id],
        '|', '|',
        ['x_studio_quality', '=', False],
        ['x_studio_quality', '=', None],
        ['x_studio_quality', '=', ''],
    ]

    try:
        leads = batched_read_leads(session, call_kw_endpoint, uid, ODOO_PASSWORD, domain, fields_to_fetch, batch_size=500)
    except Exception as e:
        print(f"ERROR reading leads: {e}")
        sys.exit(1)

    # Prepare CSV rows
    header = [
        'Opportunity',
        'Customer',
        'Company Name',
        'Email',
        'City',
        'Country',
        'Salesperson',
        'Phone',
        'Job Position',
        'LinkedIn Profile',
        'Website',
        'Quality',
        'Service',
        'Source',
        'Enriched?',
        'Company size',
        'Company revenue',
        'Request',
    ]

    rows: List[List[str]] = []

    for lead in leads:
        country_name = ''
        if isinstance(lead.get('country_id'), (list, tuple)) and len(lead['country_id']) == 2:
            country_name = lead['country_id'][1] or ''

        salesperson_name = ''
        if isinstance(lead.get('user_id'), (list, tuple)) and len(lead['user_id']) == 2:
            salesperson_name = lead['user_id'][1] or ''

        quality_code = lead.get('x_studio_quality')
        quality_label = selection_map.get('x_studio_quality', {}).get(str(quality_code), quality_code or '')

        service_code = lead.get('x_studio_service')
        service_label = selection_map.get('x_studio_service', {}).get(str(service_code), service_code or '')

        linkedin_value = extract_first_url_from_html(lead.get('x_studio_linkedin_profile') or '')

        customer_name = ''
        if isinstance(lead.get('partner_id'), (list, tuple)) and len(lead['partner_id']) == 2:
            customer_name = lead['partner_id'][1] or ''
        company_name = lead.get('partner_name') or ''

        row = [
            lead.get('name') or '',
            customer_name,
            company_name,
            lead.get('email_from') or '',
            lead.get('city') or '',
            country_name,
            salesperson_name,
            lead.get('phone') or '',
            lead.get('function') or '',
            linkedin_value,
            lead.get('website') or '',
            prevent_excel_date(quality_label or ''),
            service_label or '',
            'Meta/Site',
            '',
            '',  # Company size (empty)
            '',  # Company revenue (empty)
            '',  # Request (empty)
        ]
        rows.append(row)

    output_path = os.path.join(os.getcwd(), OUTPUT_CSV)
    tmp_output_path = output_path + ".tmp"
    try:
        with open(tmp_output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
        # Replace atomically to avoid permission issues if file is open
        try:
            if os.path.exists(output_path):
                os.replace(tmp_output_path, output_path)
            else:
                os.rename(tmp_output_path, output_path)
        except PermissionError:
            # Fallback: write to a timestamped file
            alt_path = os.path.join(os.getcwd(), f"leads_dareen_fuqaha_{int(__import__('time').time())}.csv")
            os.rename(tmp_output_path, alt_path)
            output_path = alt_path
        print(f"Exported {len(rows)} leads to: {output_path}")
    except Exception as e:
        print(f"ERROR writing CSV: {e}")
        sys.exit(1)

    # Try exporting to Google Sheets if service account credentials are available
    try:
        try:
            import gspread  # type: ignore
        except Exception:
            gspread = None
        if gspread is None:
            print("Google Sheets export skipped: gspread not installed. Run: pip install gspread google-auth")
            return

        sa_file = (
            os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
            or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            or os.path.join(os.getcwd(), "google_service_account.json")
        )
        if not os.path.exists(sa_file):
            print(
                "Google Sheets export skipped: service account JSON not found. "
                f"Place it at '{sa_file}' or set GOOGLE_SERVICE_ACCOUNT_FILE."
            )
            return

        gc = gspread.service_account(filename=sa_file)

        spreadsheet_id = os.environ.get("GSHEET_SPREADSHEET_ID")
        spreadsheet_title = os.environ.get("GSHEET_SPREADSHEET_TITLE", "EXTRACTION")
        share_with = os.environ.get("GSHEET_SHARE_WITH")
        if spreadsheet_id:
            sh = gc.open_by_key(spreadsheet_id)
        else:
            # Try open by title if shared with the service account; else create
            try:
                sh = gc.open(spreadsheet_title)
            except Exception:
                name = spreadsheet_title or f"Leads - Dareen Fuqaha {datetime.now().strftime('%Y-%m-%d')}"
                sh = gc.create(name)
                if share_with:
                    try:
                        sh.share(share_with, perm_type='user', role='writer', notify=False)
                    except Exception as share_err:
                        print(f"Warning: could not share spreadsheet with {share_with}: {share_err}")

        # Select worksheet
        worksheet_title = os.environ.get("GSHEET_WORKSHEET_TITLE", "Sheet1")
        try:
            ws = sh.worksheet(worksheet_title)
        except Exception:
            try:
                ws = sh.add_worksheet(title=worksheet_title, rows=max(2, len(rows) + 10), cols=max(11, len(header) + 5))
            except Exception:
                ws = sh.sheet1
        ws.clear()
        # Write values without Sheets auto-parsing
        ws.update(range_name='A1', values=[header] + rows, value_input_option='RAW')
        # Add data validation (dropdown) for Source and Qualified? + ensure Phone as TEXT via batchUpdate
        try:
            end_row = len(rows) + 1  # 1-based inclusive end row for A1, exclusive for API
            sheet_id = ws.id
            source_col_index = header.index('Source') + 1
            qualified_col_index = header.index('Enriched?') + 1
            phone_col_index = header.index('Phone') + 1

            requests = [
                {
                    'setDataValidation': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': 1,
                            'endRowIndex': end_row,
                            'startColumnIndex': source_col_index - 1,
                            'endColumnIndex': source_col_index,
                        },
                        'rule': {
                            'condition': {
                                'type': 'ONE_OF_LIST',
                                'values': [{'userEnteredValue': v} for v in ['Meta/Site', 'Maqsam', 'Instagram']],
                            },
                            'showCustomUi': True,
                            'strict': True,
                        },
                    }
                },
                {
                    'setDataValidation': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': 1,
                            'endRowIndex': end_row,
                            'startColumnIndex': qualified_col_index - 1,
                            'endColumnIndex': qualified_col_index,
                        },
                        'rule': {
                            'condition': {
                                'type': 'ONE_OF_LIST',
                                'values': [{'userEnteredValue': v} for v in ['yes']],
                            },
                            'showCustomUi': True,
                            'strict': False,
                        },
                    }
                },
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': 1,
                            'endRowIndex': end_row,
                            'startColumnIndex': phone_col_index - 1,
                            'endColumnIndex': phone_col_index,
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'numberFormat': {'type': 'TEXT'}
                            }
                        },
                        'fields': 'userEnteredFormat.numberFormat'
                    }
                }
            ]

            ws.spreadsheet.batch_update({'requests': requests})
        except Exception as dv_err:
            print(f"Warning: could not apply dropdowns/formatting: {dv_err}")
        print(f"Exported to Google Sheets: {sh.url}")
    except Exception as e:
        print(f"ERROR exporting to Google Sheets: {e}")


if __name__ == '__main__':
    main() 