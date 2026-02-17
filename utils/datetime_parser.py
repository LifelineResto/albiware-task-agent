"""
DateTime Parser Utility
Parses natural language date/time strings from SMS messages
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Optional
from dateutil import parser as dateutil_parser

logger = logging.getLogger(__name__)


class DateTimeParser:
    """Parse natural language date/time strings"""
    
    @staticmethod
    def parse_appointment_datetime(text: str) -> Optional[datetime]:
        """
        Parse appointment date/time from text
        
        Supports formats like:
        - "02/20/2026 2:00 PM"
        - "tomorrow at 10am"
        - "next Tuesday 3pm"
        - "2/20 at 2pm"
        - "Feb 20 at 2:00 PM"
        
        Args:
            text: Natural language date/time string
            
        Returns:
            datetime object if successfully parsed, None otherwise
        """
        try:
            text = text.strip().lower()
            now = datetime.now()
            
            # Handle relative dates
            if 'tomorrow' in text:
                base_date = now + timedelta(days=1)
                time_str = re.sub(r'tomorrow\s*(at)?\s*', '', text, flags=re.IGNORECASE)
                return DateTimeParser._parse_time_on_date(base_date, time_str)
            
            elif 'today' in text:
                base_date = now
                time_str = re.sub(r'today\s*(at)?\s*', '', text, flags=re.IGNORECASE)
                return DateTimeParser._parse_time_on_date(base_date, time_str)
            
            elif 'next' in text:
                # Handle "next Monday", "next week", etc.
                return DateTimeParser._parse_next_relative(text, now)
            
            # Try standard date/time parsing
            try:
                # Use dateutil parser for flexible parsing
                parsed = dateutil_parser.parse(text, fuzzy=True)
                
                # If no year specified and date is in the past, assume next year
                if parsed.year == now.year and parsed < now:
                    parsed = parsed.replace(year=now.year + 1)
                
                return parsed
                
            except Exception as e:
                logger.warning(f"Failed to parse datetime '{text}': {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing datetime '{text}': {e}")
            return None
    
    @staticmethod
    def _parse_time_on_date(base_date: datetime, time_str: str) -> Optional[datetime]:
        """Parse time string and apply to base date"""
        try:
            # Clean up time string
            time_str = time_str.strip()
            
            # Extract hour and am/pm
            hour_match = re.search(r'(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)?', time_str, re.IGNORECASE)
            if not hour_match:
                # Default to 9 AM if no time specified
                return base_date.replace(hour=9, minute=0, second=0, microsecond=0)
            
            hour = int(hour_match.group(1))
            am_pm = hour_match.group(2)
            
            # Extract minutes if present
            minute_match = re.search(r':(\d{2})', time_str)
            minute = int(minute_match.group(1)) if minute_match else 0
            
            # Convert to 24-hour format
            if am_pm and 'pm' in am_pm.lower() and hour != 12:
                hour += 12
            elif am_pm and 'am' in am_pm.lower() and hour == 12:
                hour = 0
            
            return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
        except Exception as e:
            logger.error(f"Error parsing time '{time_str}': {e}")
            return None
    
    @staticmethod
    def _parse_next_relative(text: str, now: datetime) -> Optional[datetime]:
        """Parse 'next Monday', 'next week', etc."""
        try:
            # Days of week
            days = {
                'monday': 0, 'mon': 0,
                'tuesday': 1, 'tue': 1, 'tues': 1,
                'wednesday': 2, 'wed': 2,
                'thursday': 3, 'thu': 3, 'thur': 3, 'thurs': 3,
                'friday': 4, 'fri': 4,
                'saturday': 5, 'sat': 5,
                'sunday': 6, 'sun': 6
            }
            
            for day_name, day_num in days.items():
                if day_name in text:
                    # Calculate days until next occurrence
                    current_day = now.weekday()
                    days_ahead = day_num - current_day
                    if days_ahead <= 0:  # Target day already happened this week
                        days_ahead += 7
                    
                    base_date = now + timedelta(days=days_ahead)
                    
                    # Extract time if present
                    time_str = re.sub(r'next\s+\w+\s*(at)?\s*', '', text, flags=re.IGNORECASE)
                    return DateTimeParser._parse_time_on_date(base_date, time_str)
            
            # Handle "next week"
            if 'week' in text:
                base_date = now + timedelta(weeks=1)
                time_str = re.sub(r'next\s+week\s*(at)?\s*', '', text, flags=re.IGNORECASE)
                return DateTimeParser._parse_time_on_date(base_date, time_str)
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing next relative '{text}': {e}")
            return None
    
    @staticmethod
    def format_datetime_for_sms(dt: datetime) -> str:
        """
        Format datetime for SMS display
        
        Args:
            dt: datetime object
            
        Returns:
            Formatted string like "02/20/2026 2:00 PM"
        """
        return dt.strftime("%m/%d/%Y %I:%M %p")
