"""
Google Calendar Service
Handles appointment creation and management in Google Calendar
"""

import logging
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class GoogleCalendarService:
    """Manages Google Calendar appointments"""
    
    def __init__(self):
        """Initialize Google Calendar API client"""
        try:
            # Get credentials from environment variable
            creds_json = os.getenv('GOOGLE_CALENDAR_CREDENTIALS')
            if not creds_json:
                raise ValueError("GOOGLE_CALENDAR_CREDENTIALS environment variable not set")
            
            # Parse credentials
            creds_dict = json.loads(creds_json)
            
            # Create credentials object
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=['https://www.googleapis.com/auth/calendar']
            )
            
            # Build calendar service
            self.service = build('calendar', 'v3', credentials=credentials)
            
            # Get calendar ID from environment
            self.calendar_id = os.getenv('GOOGLE_CALENDAR_ID')
            if not self.calendar_id:
                raise ValueError("GOOGLE_CALENDAR_ID environment variable not set")
            
            logger.info("Google Calendar service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Calendar service: {e}")
            raise
    
    def create_appointment(
        self,
        customer_name: str,
        customer_address: str,
        appointment_datetime: datetime,
        duration_hours: int = 2,
        description: str = ""
    ) -> Optional[str]:
        """
        Create an appointment in Google Calendar
        
        Args:
            customer_name: Name of the customer
            customer_address: Customer's address
            appointment_datetime: Start date/time of appointment
            duration_hours: Duration in hours (default 2)
            description: Additional description
            
        Returns:
            Event ID if successful, None otherwise
        """
        try:
            # Calculate end time
            end_datetime = appointment_datetime + timedelta(hours=duration_hours)
            
            # Create event
            event = {
                'summary': f'Appointment: {customer_name}',
                'location': customer_address,
                'description': description or f'Appointment with {customer_name}',
                'start': {
                    'dateTime': appointment_datetime.isoformat(),
                    'timeZone': 'America/Los_Angeles',  # PST/PDT
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'America/Los_Angeles',
                },
                'attendees': [
                    {'email': 'alan@lifelineresto.com', 'displayName': 'Alan Potter'},
                    {'email': 'rodolfo@lifelineresto.com', 'displayName': 'Rodolfo Arceo'},
                ],
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                        {'method': 'popup', 'minutes': 60},  # 1 hour before
                    ],
                },
            }
            
            # Insert event
            created_event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event
            ).execute()
            
            event_id = created_event.get('id')
            logger.info(f"✓ Created calendar appointment for {customer_name}: {event_id}")
            
            return event_id
            
        except HttpError as e:
            logger.error(f"HTTP error creating appointment: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creating appointment: {e}")
            return None
    
    def check_duplicate_appointment(
        self,
        customer_name: str,
        customer_address: str,
        appointment_datetime: datetime,
        tolerance_hours: int = 24
    ) -> Optional[Dict]:
        """
        Check if an appointment already exists for this customer
        
        Args:
            customer_name: Name of the customer
            customer_address: Customer's address
            appointment_datetime: Appointment date/time to check
            tolerance_hours: How many hours before/after to search (default 24)
            
        Returns:
            Existing event dict if found, None otherwise
        """
        try:
            # Search window
            time_min = (appointment_datetime - timedelta(hours=tolerance_hours)).isoformat() + 'Z'
            time_max = (appointment_datetime + timedelta(hours=tolerance_hours)).isoformat() + 'Z'
            
            # Query events
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Check for matching customer name or address
            for event in events:
                summary = event.get('summary', '').lower()
                location = event.get('location', '').lower()
                
                if (customer_name.lower() in summary or 
                    customer_address.lower() in location):
                    logger.info(f"Found duplicate appointment for {customer_name}: {event.get('id')}")
                    return event
            
            return None
            
        except HttpError as e:
            logger.error(f"HTTP error checking duplicates: {e}")
            return None
        except Exception as e:
            logger.error(f"Error checking duplicates: {e}")
            return None
    
    def check_time_slot_conflict(
        self,
        appointment_datetime: datetime,
        duration_hours: int = 2
    ) -> Optional[Dict]:
        """
        Check if ANY appointment exists in the requested time slot
        
        Args:
            appointment_datetime: Start date/time of requested appointment
            duration_hours: Duration of appointment in hours (default 2)
            
        Returns:
            Conflicting event dict if found, None if slot is free
        """
        try:
            # Calculate time window for the appointment
            end_datetime = appointment_datetime + timedelta(hours=duration_hours)
            
            # Query events in this time range
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=appointment_datetime.isoformat() + 'Z',
                timeMax=end_datetime.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            if events:
                # Return the first conflicting event
                conflicting_event = events[0]
                logger.info(f"Found time slot conflict: {conflicting_event.get('summary')} at {conflicting_event.get('start')}")
                return conflicting_event
            
            return None
            
        except HttpError as e:
            logger.error(f"HTTP error checking time slot: {e}")
            return None
        except Exception as e:
            logger.error(f"Error checking time slot: {e}")
            return None
    
    def get_appointment(self, event_id: str) -> Optional[Dict]:
        """
        Get appointment details by event ID
        
        Args:
            event_id: Google Calendar event ID
            
        Returns:
            Event dict if found, None otherwise
        """
        try:
            event = self.service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            return event
            
        except HttpError as e:
            logger.error(f"HTTP error getting appointment: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting appointment: {e}")
            return None
    
    def update_appointment(
        self,
        event_id: str,
        customer_name: Optional[str] = None,
        customer_address: Optional[str] = None,
        appointment_datetime: Optional[datetime] = None,
        duration_hours: Optional[int] = None
    ) -> bool:
        """
        Update an existing appointment
        
        Args:
            event_id: Google Calendar event ID
            customer_name: New customer name (optional)
            customer_address: New address (optional)
            appointment_datetime: New start time (optional)
            duration_hours: New duration (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get existing event
            event = self.get_appointment(event_id)
            if not event:
                return False
            
            # Update fields
            if customer_name:
                event['summary'] = f'Appointment: {customer_name}'
            
            if customer_address:
                event['location'] = customer_address
            
            if appointment_datetime:
                duration = duration_hours or 2
                end_datetime = appointment_datetime + timedelta(hours=duration)
                
                event['start'] = {
                    'dateTime': appointment_datetime.isoformat(),
                    'timeZone': 'America/Los_Angeles',
                }
                event['end'] = {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'America/Los_Angeles',
                }
            
            # Update event
            self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            logger.info(f"✓ Updated calendar appointment: {event_id}")
            return True
            
        except HttpError as e:
            logger.error(f"HTTP error updating appointment: {e}")
            return False
        except Exception as e:
            logger.error(f"Error updating appointment: {e}")
            return False
    
    def delete_appointment(self, event_id: str) -> bool:
        """
        Delete an appointment
        
        Args:
            event_id: Google Calendar event ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            logger.info(f"✓ Deleted calendar appointment: {event_id}")
            return True
            
        except HttpError as e:
            logger.error(f"HTTP error deleting appointment: {e}")
            return False
        except Exception as e:
            logger.error(f"Error deleting appointment: {e}")
            return False
