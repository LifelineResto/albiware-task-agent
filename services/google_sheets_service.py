"""
Google Sheets Service
Handles logging equipment data to Google Sheets
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class GoogleSheetsService:
    """Service for logging equipment data to Google Sheets"""
    
    # Scopes required for Google Sheets API
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    def __init__(self):
        """Initialize Google Sheets service"""
        self.service = None
        self.sheet_id = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Sheets API service"""
        try:
            # Get credentials from environment variable
            creds_json = os.getenv('GOOGLE_CALENDAR_CREDENTIALS')
            if not creds_json:
                logger.error("GOOGLE_CALENDAR_CREDENTIALS not found in environment")
                return
            
            # Parse credentials
            creds_dict = json.loads(creds_json)
            
            # Create credentials
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=self.SCOPES
            )
            
            # Build service
            self.service = build('sheets', 'v4', credentials=credentials)
            
            # Get or create equipment tracking sheet
            self.sheet_id = self._get_or_create_sheet()
            
            logger.info("Google Sheets service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets service: {e}")
            self.service = None
    
    def _get_or_create_sheet(self) -> Optional[str]:
        """
        Get existing equipment tracking sheet or create new one
        
        Returns:
            Sheet ID if successful, None otherwise
        """
        try:
            # Check if sheet ID is stored in environment
            existing_sheet_id = os.getenv('EQUIPMENT_SHEET_ID')
            if existing_sheet_id:
                # Verify sheet exists
                try:
                    self.service.spreadsheets().get(spreadsheetId=existing_sheet_id).execute()
                    logger.info(f"Using existing equipment sheet: {existing_sheet_id}")
                    return existing_sheet_id
                except HttpError:
                    logger.warning(f"Stored sheet ID {existing_sheet_id} not accessible, creating new sheet")
            
            # Create new spreadsheet
            spreadsheet = {
                'properties': {
                    'title': 'Equipment Tracking - Lifeline Restoration'
                },
                'sheets': [{
                    'properties': {
                        'title': 'Equipment Log',
                        'gridProperties': {
                            'frozenRowCount': 1
                        }
                    }
                }]
            }
            
            result = self.service.spreadsheets().create(body=spreadsheet).execute()
            sheet_id = result['spreadsheetId']
            
            # Add headers
            headers = [['Customer Name', 'Address', 'Date', 'Equipment List']]
            self.service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range='Equipment Log!A1:D1',
                valueInputOption='RAW',
                body={'values': headers}
            ).execute()
            
            # Format headers (bold)
            requests = [{
                'repeatCell': {
                    'range': {
                        'sheetId': 0,
                        'startRowIndex': 0,
                        'endRowIndex': 1
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'textFormat': {
                                'bold': True
                            }
                        }
                    },
                    'fields': 'userEnteredFormat.textFormat.bold'
                }
            }]
            
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body={'requests': requests}
            ).execute()
            
            logger.info(f"Created new equipment tracking sheet: {sheet_id}")
            logger.info(f"View at: https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
            
            return sheet_id
            
        except Exception as e:
            logger.error(f"Failed to get or create sheet: {e}")
            return None
    
    def log_equipment(self, customer_name: str, address: str, date: datetime, equipment_list: str) -> bool:
        """
        Log equipment data to Google Sheets
        
        Args:
            customer_name: Customer name
            address: Customer address
            date: Date equipment was left
            equipment_list: List of equipment (e.g., "1 dehumidifier, 4 air movers")
            
        Returns:
            True if successful, False otherwise
        """
        if not self.service or not self.sheet_id:
            logger.error("Google Sheets service not initialized")
            return False
        
        try:
            # Format date as MM/DD/YYYY
            formatted_date = date.strftime('%m/%d/%Y')
            
            # Prepare row data
            row = [[customer_name, address, formatted_date, equipment_list]]
            
            # Append to sheet
            self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range='Equipment Log!A:D',
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body={'values': row}
            ).execute()
            
            logger.info(f"Logged equipment for {customer_name} to Google Sheets")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log equipment to Google Sheets: {e}")
            return False
    
    def get_sheet_url(self) -> Optional[str]:
        """
        Get the URL of the equipment tracking sheet
        
        Returns:
            Sheet URL if available, None otherwise
        """
        if self.sheet_id:
            return f"https://docs.google.com/spreadsheets/d/{self.sheet_id}/edit"
        return None
