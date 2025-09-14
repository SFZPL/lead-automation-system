import os
import gspread
from google.auth.exceptions import GoogleAuthError
from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime
from config import Config
import logging

logger = logging.getLogger(__name__)

class GoogleSheetsClient:
    """Client for managing Google Sheets operations"""
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.client = None
        self.spreadsheet = None
        self.worksheet = None
        
    def connect(self) -> bool:
        """Connect to Google Sheets API"""
        try:
            if not os.path.exists(self.config.GOOGLE_SERVICE_ACCOUNT_FILE):
                logger.error(f"Service account file not found: {self.config.GOOGLE_SERVICE_ACCOUNT_FILE}")
                return False
            
            self.client = gspread.service_account(filename=self.config.GOOGLE_SERVICE_ACCOUNT_FILE)
            logger.info("Successfully connected to Google Sheets API")
            return True
            
        except GoogleAuthError as e:
            logger.error(f"Google authentication failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            return False
    
    def get_or_create_spreadsheet(self) -> bool:
        """Get existing spreadsheet or create new one"""
        try:
            if not self.client:
                raise RuntimeError("Not connected. Call connect() first.")
            
            # Try to open by ID first
            if self.config.GSHEET_SPREADSHEET_ID:
                try:
                    self.spreadsheet = self.client.open_by_key(self.config.GSHEET_SPREADSHEET_ID)
                    logger.info(f"Opened spreadsheet by ID: {self.config.GSHEET_SPREADSHEET_ID}")
                    return True
                except gspread.SpreadsheetNotFound:
                    logger.warning("Spreadsheet ID not found, will try by title or create new")
            
            # Try to open by title
            try:
                self.spreadsheet = self.client.open(self.config.GSHEET_SPREADSHEET_TITLE)
                logger.info(f"Opened spreadsheet by title: {self.config.GSHEET_SPREADSHEET_TITLE}")
                return True
            except gspread.SpreadsheetNotFound:
                pass
            
            # Create new spreadsheet
            spreadsheet_name = self.config.GSHEET_SPREADSHEET_TITLE or f"Lead Automation System {datetime.now().strftime('%Y-%m-%d')}"
            self.spreadsheet = self.client.create(spreadsheet_name)
            
            # Share with specified email if provided
            if self.config.GSHEET_SHARE_WITH:
                try:
                    self.spreadsheet.share(self.config.GSHEET_SHARE_WITH, perm_type='user', role='writer', notify=False)
                    logger.info(f"Shared spreadsheet with {self.config.GSHEET_SHARE_WITH}")
                except Exception as e:
                    logger.warning(f"Could not share spreadsheet: {e}")
            
            logger.info(f"Created new spreadsheet: {self.spreadsheet.url}")
            return True
            
        except Exception as e:
            logger.error(f"Error getting/creating spreadsheet: {e}")
            return False
    
    def get_or_create_worksheet(self) -> bool:
        """Get existing worksheet or create new one"""
        try:
            if not self.spreadsheet:
                raise RuntimeError("No spreadsheet available. Call get_or_create_spreadsheet() first.")
            
            # Try to get existing worksheet
            try:
                self.worksheet = self.spreadsheet.worksheet(self.config.GSHEET_WORKSHEET_TITLE)
                logger.info(f"Using existing worksheet: {self.config.GSHEET_WORKSHEET_TITLE}")
                return True
            except gspread.WorksheetNotFound:
                pass
            
            # Create new worksheet
            self.worksheet = self.spreadsheet.add_worksheet(
                title=self.config.GSHEET_WORKSHEET_TITLE,
                rows=1000,
                cols=len(self.config.SHEET_HEADERS) + 5
            )
            logger.info(f"Created new worksheet: {self.config.GSHEET_WORKSHEET_TITLE}")
            return True
            
        except Exception as e:
            logger.error(f"Error getting/creating worksheet: {e}")
            return False
    
    def initialize_sheet(self) -> bool:
        """Initialize sheet with headers and formatting"""
        try:
            if not self.worksheet:
                raise RuntimeError("No worksheet available.")
            
            # Clear existing content
            self.worksheet.clear()
            
            # Set headers
            self.worksheet.update('A1', [self.config.SHEET_HEADERS], value_input_option='RAW')
            
            # Format headers
            self.worksheet.format('A1:L1', {
                'backgroundColor': {'red': 0.2, 'green': 0.6, 'blue': 0.9},
                'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
                'horizontalAlignment': 'CENTER'
            })
            
            # Set column widths
            column_widths = [
                ('A', 200),  # Full Name
                ('B', 200),  # Company Name
                ('C', 300),  # LinkedIn Link
                ('D', 150),  # Company Size
                ('E', 150),  # Industry
                ('F', 180),  # Company Revenue
                ('G', 150),  # Job Role
                ('H', 120),  # Company year EST
                ('I', 120),  # Phone
                ('J', 120),  # Salesperson
                ('K', 100),  # Quality
                ('L', 80),   # Enriched
            ]
            
            for col, width in column_widths:
                self.worksheet.update_dimension_pixels(col, width)
            
            # Add data validation for Quality column (1-5 stars)
            try:
                self._add_quality_validation()
            except Exception as e:
                logger.warning(f"Could not add validation: {e}")
            
            logger.info("Sheet initialized with headers and formatting")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing sheet: {e}")
            return False
    
    def add_leads_to_sheet(self, leads: List[Dict[str, Any]]) -> bool:
        """Add leads to the sheet"""
        try:
            if not self.worksheet:
                raise RuntimeError("No worksheet available.")
            
            if not leads:
                logger.warning("No leads to add")
                return True
            
            # Prepare data rows
            rows = []
            for lead in leads:
                row = []
                for header in self.config.SHEET_HEADERS:
                    value = lead.get(header, '')
                    # Clean and format values
                    if isinstance(value, str):
                        value = value.strip()
                    row.append(str(value) if value else '')
                rows.append(row)
            
            # Find next empty row
            existing_data = self.worksheet.get_all_values()
            next_row = len(existing_data) + 1
            
            # Update sheet with new data
            if rows:
                end_col = chr(ord('A') + len(self.config.SHEET_HEADERS) - 1)
                range_name = f'A{next_row}:{end_col}{next_row + len(rows) - 1}'
                self.worksheet.update(range_name, rows, value_input_option='RAW')
                
                # Format phone numbers as text
                phone_col = chr(ord('A') + self.config.SHEET_HEADERS.index('Phone'))
                phone_range = f'{phone_col}{next_row}:{phone_col}{next_row + len(rows) - 1}'
                self.worksheet.format(phone_range, {'numberFormat': {'type': 'TEXT'}})
                
                logger.info(f"Added {len(rows)} leads to sheet")
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding leads to sheet: {e}")
            return False
    
    def get_leads_from_sheet(self, enriched_only: bool = False) -> List[Dict[str, Any]]:
        """Get leads from the sheet"""
        try:
            if not self.worksheet:
                raise RuntimeError("No worksheet available.")
            
            # Get all data
            data = self.worksheet.get_all_records()
            
            # Filter if needed
            if enriched_only:
                data = [row for row in data if row.get('Enriched', '').lower() in ['yes', 'true', '1']]
            
            logger.info(f"Retrieved {len(data)} leads from sheet")
            return data
            
        except Exception as e:
            logger.error(f"Error getting leads from sheet: {e}")
            return []
    
    def update_lead_in_sheet(self, row_number: int, updates: Dict[str, Any]) -> bool:
        """Update a specific lead in the sheet"""
        try:
            if not self.worksheet:
                raise RuntimeError("No worksheet available.")
            
            # Get headers to map column names to positions
            headers = self.worksheet.row_values(1)
            
            # Update each field
            for field, value in updates.items():
                if field in headers:
                    col_index = headers.index(field) + 1  # 1-based
                    col_letter = chr(ord('A') + col_index - 1)
                    cell_address = f"{col_letter}{row_number}"
                    self.worksheet.update(cell_address, str(value), value_input_option='RAW')
            
            logger.debug(f"Updated row {row_number} in sheet")
            return True
            
        except Exception as e:
            logger.error(f"Error updating row {row_number}: {e}")
            return False
    
    def mark_as_enriched(self, row_number: int) -> bool:
        """Mark a lead as enriched"""
        return self.update_lead_in_sheet(row_number, {'Enriched': 'Yes'})
    
    def _add_quality_validation(self):
        """Add data validation for Quality column"""
        try:
            headers = self.config.SHEET_HEADERS
            quality_col_index = headers.index('Quality (Out of 5)')
            enriched_col_index = headers.index('Enriched')
            
            sheet_id = self.worksheet.id
            
            # Add validation for Quality column (1-5)
            quality_validation = {
                'setDataValidation': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': 1,
                        'endRowIndex': 1000,
                        'startColumnIndex': quality_col_index,
                        'endColumnIndex': quality_col_index + 1,
                    },
                    'rule': {
                        'condition': {
                            'type': 'ONE_OF_LIST',
                            'values': [{'userEnteredValue': str(i)} for i in range(1, 6)],
                        },
                        'showCustomUi': True,
                        'strict': False,
                    },
                }
            }
            
            # Add validation for Enriched column
            enriched_validation = {
                'setDataValidation': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': 1,
                        'endRowIndex': 1000,
                        'startColumnIndex': enriched_col_index,
                        'endColumnIndex': enriched_col_index + 1,
                    },
                    'rule': {
                        'condition': {
                            'type': 'ONE_OF_LIST',
                            'values': [{'userEnteredValue': 'Yes'}, {'userEnteredValue': 'No'}],
                        },
                        'showCustomUi': True,
                        'strict': False,
                    },
                }
            }
            
            # Apply validations
            self.spreadsheet.batch_update({
                'requests': [quality_validation, enriched_validation]
            })
            
        except Exception as e:
            logger.error(f"Error adding validations: {e}")
    
    def export_to_csv(self, filepath: str) -> bool:
        """Export sheet data to CSV"""
        try:
            if not self.worksheet:
                raise RuntimeError("No worksheet available.")
            
            # Get all data
            data = self.worksheet.get_all_records()
            
            # Create DataFrame and export
            df = pd.DataFrame(data)
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
            
            logger.info(f"Exported {len(data)} rows to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return False
    
    @property
    def spreadsheet_url(self) -> str:
        """Get the spreadsheet URL"""
        return self.spreadsheet.url if self.spreadsheet else ""