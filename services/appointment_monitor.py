"""
Appointment Monitor Service
Monitors Google Calendar appointments and triggers post-appointment follow-ups
"""

import logging
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session
from database.enhanced_models import Contact, SMSConversation, ConversationState
from services.google_calendar_service import GoogleCalendarService
from services.sms_service import SMSService

logger = logging.getLogger(__name__)


class AppointmentMonitor:
    """Monitors appointments and triggers post-appointment follow-ups"""
    
    def __init__(self, sms_service: SMSService):
        """
        Initialize appointment monitor
        
        Args:
            sms_service: SMS service for sending follow-up messages
        """
        self.sms_service = sms_service
        self.calendar_service = None
        
        try:
            self.calendar_service = GoogleCalendarService()
            logger.info("Appointment monitor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Calendar service: {e}")
    
    def check_completed_appointments(self, db: Session) -> int:
        """
        Check for appointments that have completed and need follow-up
        
        Args:
            db: Database session
            
        Returns:
            Number of follow-ups sent
        """
        if not self.calendar_service:
            logger.warning("Calendar service not available, skipping appointment check")
            return 0
        
        try:
            # Get current time
            now = datetime.utcnow()
            
            # Find contacts with appointments that:
            # 1. Have a calendar event created
            # 2. Have an appointment datetime in the past (>= 2 hours ago)
            # 3. Haven't been marked as completed
            # 4. Haven't had follow-up sent yet
            two_hours_ago = now - timedelta(hours=2)
            
            contacts_to_follow_up = db.query(Contact).filter(
                Contact.appointment_created_in_calendar == True,
                Contact.appointment_datetime.isnot(None),
                Contact.appointment_datetime <= two_hours_ago,
                Contact.appointment_completed == False,
                Contact.appointment_follow_up_sent == False
            ).all()
            
            logger.info(f"Found {len(contacts_to_follow_up)} appointments needing follow-up")
            
            follow_ups_sent = 0
            
            for contact in contacts_to_follow_up:
                try:
                    # Send post-appointment follow-up
                    success = self._send_appointment_follow_up(db, contact)
                    
                    if success:
                        follow_ups_sent += 1
                        
                        # Mark appointment as completed and follow-up sent
                        contact.appointment_completed = True
                        contact.appointment_follow_up_sent = True
                        contact.appointment_follow_up_sent_at = now
                        
                        logger.info(f"✓ Sent post-appointment follow-up for {contact.full_name}")
                    
                except Exception as e:
                    logger.error(f"Error sending follow-up for contact {contact.id}: {e}")
                    continue
            
            db.commit()
            
            logger.info(f"Sent {follow_ups_sent} post-appointment follow-ups")
            return follow_ups_sent
            
        except Exception as e:
            logger.error(f"Error checking completed appointments: {e}")
            return 0
    
    def _send_appointment_follow_up(self, db: Session, contact: Contact) -> bool:
        """
        Send post-appointment follow-up SMS to technician
        
        Args:
            db: Database session
            contact: Contact with completed appointment
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get or create active conversation
            conversation = db.query(SMSConversation).filter(
                SMSConversation.contact_id == contact.id,
                SMSConversation.completed == False
            ).first()
            
            if not conversation:
                # Create new conversation for post-appointment follow-up
                # Use the technician phone from the most recent completed conversation
                last_conversation = db.query(SMSConversation).filter(
                    SMSConversation.contact_id == contact.id
                ).order_by(SMSConversation.created_at.desc()).first()
                
                if not last_conversation:
                    logger.warning(f"No previous conversation found for contact {contact.id}")
                    return False
                
                conversation = SMSConversation(
                    contact_id=contact.id,
                    technician_phone=last_conversation.technician_phone,
                    state=ConversationState.AWAITING_APPOINTMENT_RESULT,
                    started_at=datetime.utcnow(),
                    last_message_at=datetime.utcnow()
                )
                db.add(conversation)
                db.flush()
            else:
                # Update existing conversation state
                conversation.state = ConversationState.AWAITING_APPOINTMENT_RESULT
                conversation.last_message_at = datetime.utcnow()
            
            # Send follow-up SMS
            self.sms_service.send_sms(
                to_number=conversation.technician_phone,
                message=(
                    f"Hi! The appointment with {contact.full_name} should be completed now.\\n\\n"
                    f"What was the result of the appointment?\\n"
                    f"1 - Work started\\n"
                    f"2 - Scheduled work start date\\n"
                    f"3 - Scheduled another appointment\\n"
                    f"4 - Undetermined"
                ),
                contact_id=contact.id,
                conversation_id=conversation.id,
                db=db
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending appointment follow-up: {e}")
            return False
    
    @staticmethod
    def process_pending_follow_ups(db: Session, sms_service: SMSService) -> int:
        """
        Static method to process pending appointment follow-ups
        Can be called from scheduled jobs
        
        Args:
            db: Database session
            sms_service: SMS service instance
            
        Returns:
            Number of follow-ups sent
        """
        monitor = AppointmentMonitor(sms_service)
        return monitor.check_completed_appointments(db)
