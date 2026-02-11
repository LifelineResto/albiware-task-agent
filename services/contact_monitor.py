"""
Contact Monitoring Service
Tracks new contacts from Albiware and schedules follow-up SMS
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy.orm import Session

from database.enhanced_models import Contact, ContactStatus, SMSConversation, ConversationState
from services.albiware_client import AlbiwareClient
from services.sms_service import SMSService

logger = logging.getLogger(__name__)


class ContactMonitor:
    """Monitors Albiware for new contacts and schedules follow-ups"""
    
    def __init__(self, albiware_client: AlbiwareClient, sms_service: SMSService):
        self.albiware_client = albiware_client
        self.sms_service = sms_service
    
    def sync_contacts(self, db: Session) -> int:
        """
        Sync contacts from Albiware and identify new ones
        
        Returns:
            Number of new contacts found
        """
        try:
            logger.info("Starting contact sync from Albiware...")
            
            # Get all contacts from Albiware
            contacts_data = self.albiware_client.get_all_contacts()
            
            if not contacts_data:
                logger.warning("No contacts retrieved from Albiware")
                return 0
            
            new_contacts_count = 0
            
            for contact_data in contacts_data:
                contact_id = contact_data.get('id')
                
                # Check if contact already exists in our database
                existing_contact = db.query(Contact).filter(
                    Contact.albiware_contact_id == contact_id
                ).first()
                
                if not existing_contact:
                    # New contact found!
                    new_contact = self._create_contact_record(db, contact_data)
                    new_contacts_count += 1
                    logger.info(f"New contact found: {new_contact.full_name} (ID: {contact_id})")
                    
                    # Schedule 24-hour follow-up
                    self._schedule_follow_up(db, new_contact)
            
            db.commit()
            logger.info(f"Contact sync complete. Found {new_contacts_count} new contacts.")
            return new_contacts_count
            
        except Exception as e:
            logger.error(f"Error syncing contacts: {e}")
            db.rollback()
            return 0
    
    def _create_contact_record(self, db: Session, contact_data: Dict) -> Contact:
        """Create a new contact record in database"""
        
        first_name = contact_data.get('firstName', '')
        last_name = contact_data.get('lastName', '')
        full_name = f"{first_name} {last_name}".strip()
        
        # Parse address
        address_parts = []
        if contact_data.get('address1'):
            address_parts.append(contact_data['address1'])
        if contact_data.get('city'):
            address_parts.append(contact_data['city'])
        if contact_data.get('state'):
            address_parts.append(contact_data['state'])
        if contact_data.get('zipCode'):
            address_parts.append(contact_data['zipCode'])
        
        address = ', '.join(address_parts) if address_parts else None
        
        contact = Contact(
            albiware_contact_id=contact_data.get('id'),
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            email=contact_data.get('email'),
            phone_number=contact_data.get('phoneNumber'),
            address=address,
            status=ContactStatus.NEW,
            albiware_created_at=self._parse_datetime(contact_data.get('createdAt'))
        )
        
        db.add(contact)
        db.flush()  # Get the ID without committing
        
        return contact
    
    def _schedule_follow_up(self, db: Session, contact: Contact):
        """Schedule a 24-hour follow-up for the contact"""
        
        # Set follow-up time to 24 hours from now
        follow_up_time = datetime.utcnow() + timedelta(hours=24)
        
        contact.follow_up_scheduled_at = follow_up_time
        contact.status = ContactStatus.FOLLOW_UP_SCHEDULED
        
        logger.info(f"Scheduled follow-up for {contact.full_name} at {follow_up_time}")
    
    def process_scheduled_follow_ups(self, db: Session, technician_phone: str) -> int:
        """
        Process contacts that are due for follow-up SMS
        
        Args:
            db: Database session
            technician_phone: Phone number to send follow-ups to
            
        Returns:
            Number of follow-ups sent
        """
        try:
            # Find contacts that need follow-up
            now = datetime.utcnow()
            
            contacts_due = db.query(Contact).filter(
                Contact.status == ContactStatus.FOLLOW_UP_SCHEDULED,
                Contact.follow_up_scheduled_at <= now
            ).all()
            
            if not contacts_due:
                logger.info("No follow-ups due at this time")
                return 0
            
            follow_ups_sent = 0
            
            for contact in contacts_due:
                try:
                    # Send follow-up SMS
                    success = self._send_follow_up_sms(db, contact, technician_phone)
                    
                    if success:
                        follow_ups_sent += 1
                        contact.status = ContactStatus.FOLLOW_UP_SENT
                        contact.follow_up_sent_at = datetime.utcnow()
                        logger.info(f"Follow-up sent for {contact.full_name}")
                    
                except Exception as e:
                    logger.error(f"Error sending follow-up for contact {contact.id}: {e}")
                    continue
            
            db.commit()
            logger.info(f"Processed {follow_ups_sent} follow-ups")
            return follow_ups_sent
            
        except Exception as e:
            logger.error(f"Error processing follow-ups: {e}")
            db.rollback()
            return 0
    
    def _send_follow_up_sms(self, db: Session, contact: Contact, technician_phone: str) -> bool:
        """Send the initial follow-up SMS to technician"""
        
        # Create conversation record
        conversation = SMSConversation(
            contact_id=contact.id,
            state=ConversationState.AWAITING_CONTACT_CONFIRMATION,
            technician_phone=technician_phone,
            started_at=datetime.utcnow()
        )
        db.add(conversation)
        db.flush()
        
        # Construct message
        contact_name = contact.full_name or "the new contact"
        message = f"Hi Rudy, were you able to make contact with {contact_name} yet? Reply YES or NO."
        
        # Send SMS
        success = self.sms_service.send_sms(
            to_number=technician_phone,
            message=message,
            contact_id=contact.id,
            conversation_id=conversation.id,
            db=db
        )
        
        if success:
            contact.status = ContactStatus.AWAITING_RESPONSE
            conversation.last_message_at = datetime.utcnow()
        
        return success
    
    def _parse_datetime(self, date_string: str) -> datetime:
        """Parse datetime string from Albiware API"""
        if not date_string:
            return None
        
        try:
            # Try ISO format
            return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except:
            try:
                # Try common format
                return datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%S')
            except:
                return None
