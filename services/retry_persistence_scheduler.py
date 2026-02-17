"""
Retry and Persistence Scheduler
Handles 2-hour retries for NO responses and 10-minute persistence mode for no responses
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import List

from database.enhanced_models import Contact, SMSConversation, ConversationState
from services.sms_service import SMSService

logger = logging.getLogger(__name__)


class RetryPersistenceScheduler:
    """Manages retry and persistence follow-ups for unanswered contacts"""
    
    def __init__(self, sms_service: SMSService):
        self.sms_service = sms_service
    
    def process_retries_and_persistence(self, db: Session) -> dict:
        """
        Process both 2-hour retries (after NO response) and 10-minute persistence (after no response)
        
        Returns:
            Dictionary with counts of retries and persistence messages sent
        """
        retries_sent = self._process_two_hour_retries(db)
        persistence_sent = self._process_persistence_mode(db)
        
        return {
            'retries_sent': retries_sent,
            'persistence_sent': persistence_sent
        }
    
    def _process_two_hour_retries(self, db: Session) -> int:
        """
        Process 2-hour retries for contacts who responded NO
        
        Returns:
            Number of retry messages sent
        """
        logger.info("Checking for contacts needing 2-hour retry...")
        
        # Find contacts that:
        # 1. Responded NO (have last_retry_at set)
        # 2. Last retry was 2+ hours ago
        # 3. Still in AWAITING_CONTACT_CONFIRMATION state
        
        two_hours_ago = datetime.utcnow() - timedelta(hours=2)
        
        contacts = db.query(Contact).join(SMSConversation).filter(
            Contact.last_retry_at.isnot(None),
            Contact.last_retry_at <= two_hours_ago,
            SMSConversation.state == ConversationState.AWAITING_CONTACT_CONFIRMATION,
            SMSConversation.completed_at.is_(None)
        ).all()
        
        logger.info(f"Found {len(contacts)} contacts needing 2-hour retry")
        
        retries_sent = 0
        for contact in contacts:
            try:
                # Get active conversation
                conversation = db.query(SMSConversation).filter(
                    SMSConversation.contact_id == contact.id,
                    SMSConversation.state == ConversationState.AWAITING_CONTACT_CONFIRMATION,
                    SMSConversation.completed_at.is_(None)
                ).first()
                
                if not conversation:
                    logger.warning(f"No active conversation found for contact {contact.id}")
                    continue
                
                # Send retry message
                contact_name = contact.full_name or "the contact"
                message = f"Hi Rudy, checking in again - were you able to make contact with {contact_name}? Reply YES or NO."
                
                success = self.sms_service.send_sms(
                    to_number=conversation.technician_phone,
                    message=message,
                    contact_id=contact.id,
                    conversation_id=conversation.id,
                    db=db
                )
                
                if success:
                    # Update retry tracking
                    contact.last_retry_at = datetime.utcnow()
                    db.commit()
                    retries_sent += 1
                    logger.info(f"✓ Sent 2-hour retry for {contact.full_name}")
                
            except Exception as e:
                logger.error(f"Error sending retry for contact {contact.id}: {e}")
                continue
        
        return retries_sent
    
    def _process_persistence_mode(self, db: Session) -> int:
        """
        Process 10-minute persistence follow-ups for contacts with no response
        
        Returns:
            Number of persistence messages sent
        """
        logger.info("Checking for contacts needing persistence follow-up...")
        
        # Find conversations that:
        # 1. Are in AWAITING_CONTACT_CONFIRMATION state
        # 2. Last message was 10+ minutes ago (initial or persistence)
        # 3. Have NOT received a response from technician
        
        ten_minutes_ago = datetime.utcnow() - timedelta(minutes=10)
        
        # Get conversations where last message was from us (system), not technician
        conversations = db.query(SMSConversation).join(Contact).filter(
            SMSConversation.state == ConversationState.AWAITING_CONTACT_CONFIRMATION,
            SMSConversation.last_message_at <= ten_minutes_ago,
            SMSConversation.completed_at.is_(None),
            # Only enter persistence if they haven't responded NO (no last_retry_at)
            # OR if they responded NO but we already sent the 2-hour retry
            # We check this by seeing if persistence_mode is True OR if enough time has passed since initial send
        ).all()
        
        persistence_sent = 0
        for conversation in conversations:
            try:
                contact = conversation.contact
                
                # Check if we should enter persistence mode
                # Enter persistence if:
                # 1. Already in persistence mode, OR
                # 2. Initial message was sent 10+ minutes ago and no response
                
                should_send_persistence = False
                
                if contact.persistence_mode:
                    # Already in persistence mode, continue sending
                    should_send_persistence = True
                else:
                    # Check if we should START persistence mode
                    # Only if they haven't responded NO (which would trigger 2-hour retry)
                    if not contact.last_retry_at:
                        # No NO response, so they just haven't responded at all
                        # Enter persistence mode
                        contact.persistence_mode = True
                        should_send_persistence = True
                
                if not should_send_persistence:
                    continue
                
                # Send persistence message
                contact_name = contact.full_name or "the contact"
                
                if contact.persistence_count == 0:
                    # First persistence message
                    message = (
                        f"⚠️ PERSISTENCE MODE ACTIVATED ⚠️\\n\\n"
                        f"Hi Rudy, I still need to know: were you able to make contact with {contact_name}? "
                        f"Reply YES or NO.\\n\\n"
                        f"(You'll receive this message every 10 minutes until you respond)"
                    )
                else:
                    # Subsequent persistence messages
                    message = (
                        f"Reminder #{contact.persistence_count + 1}: Were you able to make contact with {contact_name}? "
                        f"Reply YES or NO."
                    )
                
                success = self.sms_service.send_sms(
                    to_number=conversation.technician_phone,
                    message=message,
                    contact_id=contact.id,
                    conversation_id=conversation.id,
                    db=db
                )
                
                if success:
                    # Update persistence tracking
                    contact.persistence_count = (contact.persistence_count or 0) + 1
                    contact.last_persistence_at = datetime.utcnow()
                    conversation.last_message_at = datetime.utcnow()
                    db.commit()
                    persistence_sent += 1
                    logger.info(f"✓ Sent persistence message #{contact.persistence_count} for {contact.full_name}")
                
            except Exception as e:
                logger.error(f"Error sending persistence for conversation {conversation.id}: {e}")
                continue
        
        return persistence_sent
