"""
Twilio SMS Service
Handles sending SMS notifications via Twilio API.
"""

from twilio.rest import Client
from typing import Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SMSService:
    """Service for sending SMS messages via Twilio."""
    
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        """
        Initialize the SMS service.
        
        Args:
            account_sid: Twilio Account SID
            auth_token: Twilio Auth Token
            from_number: Twilio phone number to send from (E.164 format)
        """
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number
    
    def send_task_reminder(
        self,
        to_number: str,
        task_name: str,
        project_name: str,
        due_date: datetime,
        task_id: int
    ) -> Optional[str]:
        """
        Send a task reminder SMS.
        
        Args:
            to_number: Recipient phone number (E.164 format)
            task_name: Name of the task
            project_name: Name of the project
            due_date: Task due date
            task_id: Task ID in Albiware
            
        Returns:
            Message SID if successful, None otherwise
        """
        # Format date according to SMS Date and Time Output Format: MM/DD/YYYY 12hr a.m./p.m.
        formatted_date = due_date.strftime("%m/%d/%Y %I:%M %p").replace(" 0", " ").lower()
        
        message_body = (
            f"Lifeline Restoration Task Reminder:\n\n"
            f"Task: {task_name}\n"
            f"Project: {project_name}\n"
            f"Due: {formatted_date}\n"
            f"Task ID: {task_id}\n\n"
            f"Please complete this task on time."
        )
        
        try:
            message = self.client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=to_number
            )
            logger.info(f"SMS sent successfully. SID: {message.sid}, To: {to_number}")
            return message.sid
        except Exception as e:
            logger.error(f"Error sending SMS to {to_number}: {e}")
            return None
    
    def send_task_completion_reminder(
        self,
        to_number: str,
        task_name: str,
        project_name: str,
        days_overdue: int,
        task_id: int
    ) -> Optional[str]:
        """
        Send a task completion reminder for overdue tasks.
        
        Args:
            to_number: Recipient phone number (E.164 format)
            task_name: Name of the task
            project_name: Name of the project
            days_overdue: Number of days the task is overdue
            task_id: Task ID in Albiware
            
        Returns:
            Message SID if successful, None otherwise
        """
        message_body = (
            f"Lifeline Restoration URGENT:\n\n"
            f"Task: {task_name}\n"
            f"Project: {project_name}\n"
            f"Status: {days_overdue} days OVERDUE\n"
            f"Task ID: {task_id}\n\n"
            f"Please complete this task immediately."
        )
        
        try:
            message = self.client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=to_number
            )
            logger.info(f"Overdue SMS sent successfully. SID: {message.sid}, To: {to_number}")
            return message.sid
        except Exception as e:
            logger.error(f"Error sending overdue SMS to {to_number}: {e}")
            return None
    
    def send_custom_message(self, to_number: str, message_body: str) -> Optional[str]:
        """
        Send a custom SMS message.
        
        Args:
            to_number: Recipient phone number (E.164 format)
            message_body: The message content
            
        Returns:
            Message SID if successful, None otherwise
        """
        try:
            message = self.client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=to_number
            )
            logger.info(f"Custom SMS sent successfully. SID: {message.sid}, To: {to_number}")
            return message.sid
        except Exception as e:
            logger.error(f"Error sending custom SMS to {to_number}: {e}")
            return None
    
    def get_message_status(self, message_sid: str) -> Optional[str]:
        """
        Get the delivery status of a sent message.
        
        Args:
            message_sid: The Twilio message SID
            
        Returns:
            Message status string or None if error
        """
        try:
            message = self.client.messages(message_sid).fetch()
            return message.status
        except Exception as e:
            logger.error(f"Error fetching message status for {message_sid}: {e}")
            return None
