"""
SMS Conversation Handler
Manages two-way SMS conversations with technicians
"""

import logging
import re
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from database.enhanced_models import (
    Contact, ContactStatus, ContactOutcome,
    SMSConversation, ConversationState, SMSMessage
)
from services.sms_service import SMSService

logger = logging.getLogger(__name__)


class ConversationHandler:
    """Handles incoming SMS responses and manages conversation flow"""
    
    def __init__(self, sms_service: SMSService):
        self.sms_service = sms_service
    
    def handle_incoming_sms(self, db: Session, from_number: str, message_body: str, twilio_sid: str) -> bool:
        """
        Process incoming SMS from technician
        
        Args:
            db: Database session
            from_number: Phone number that sent the message
            message_body: Content of the SMS
            twilio_sid: Twilio message SID
            
        Returns:
            True if message was processed successfully
        """
        try:
            logger.info(f"Incoming SMS from {from_number}: {message_body}")
            
            # Find active conversation for this phone number
            conversation = db.query(SMSConversation).filter(
                SMSConversation.technician_phone == from_number,
                SMSConversation.state != ConversationState.COMPLETED
            ).order_by(SMSConversation.last_message_at.desc()).first()
            
            if not conversation:
                logger.warning(f"No active conversation found for {from_number}")
                # Send help message
                self.sms_service.send_sms(
                    to_number=from_number,
                    message="No active conversation found. Please wait for a follow-up question.",
                    contact_id=None,
                    conversation_id=None,
                    db=db
                )
                return False
            
            # Log the incoming message
            self._log_incoming_message(db, conversation, from_number, message_body, twilio_sid)
            
            # Process based on conversation state
            if conversation.state == ConversationState.AWAITING_CONTACT_CONFIRMATION:
                return self._handle_contact_confirmation(db, conversation, message_body)
            
            elif conversation.state == ConversationState.AWAITING_OUTCOME:
                return self._handle_outcome_response(db, conversation, message_body)
            
            elif conversation.state == ConversationState.AWAITING_PROJECT_TYPE:
                return self._handle_project_type(db, conversation, message_body)
            
            elif conversation.state == ConversationState.AWAITING_PROPERTY_TYPE:
                return self._handle_property_type(db, conversation, message_body)
            
            elif conversation.state == ConversationState.AWAITING_RESIDENTIAL_SUBTYPE:
                return self._handle_residential_subtype(db, conversation, message_body)
            
            elif conversation.state == ConversationState.AWAITING_INSURANCE:
                return self._handle_insurance(db, conversation, message_body)
            
            elif conversation.state == ConversationState.AWAITING_INSURANCE_COMPANY:
                return self._handle_insurance_company(db, conversation, message_body)
            
            elif conversation.state == ConversationState.AWAITING_REFERRAL_SOURCE:
                return self._handle_referral_source(db, conversation, message_body)
            
            else:
                logger.warning(f"Unknown conversation state: {conversation.state}")
                return False
                
        except Exception as e:
            logger.error(f"Error handling incoming SMS: {e}")
            return False
    
    def _handle_contact_confirmation(self, db: Session, conversation: SMSConversation, message_body: str) -> bool:
        """Handle YES/NO response to contact confirmation"""
        
        contact = conversation.contact
        response_lower = message_body.lower().strip()
        
        # Check for YES
        if self._is_yes_response(response_lower):
            logger.info(f"Technician confirmed contact made with {contact.full_name}")
            
            conversation.contact_confirmed = True
            conversation.state = ConversationState.AWAITING_OUTCOME
            contact.status = ContactStatus.CONTACT_MADE
            contact.contact_made_at = datetime.utcnow()
            
            # Exit persistence mode if active
            if contact.persistence_mode:
                logger.info(f"Exiting persistence mode for {contact.full_name}")
                contact.persistence_mode = False
            
            # Ask for outcome
            outcome_message = (
                f"Great! What was the outcome with {contact.full_name}?\n\n"
                "Reply with:\n"
                "1 - Appointment set\n"
                "2 - Looking for quotes\n"
                "3 - Waste of time\n"
                "4 - Something else"
            )
            
            self.sms_service.send_sms(
                to_number=conversation.technician_phone,
                message=outcome_message,
                contact_id=contact.id,
                conversation_id=conversation.id,
                db=db
            )
            
        # Check for NO
        elif self._is_no_response(response_lower):
            logger.info(f"Technician has not made contact with {contact.full_name} - scheduling 2-hour retry")
            
            conversation.contact_confirmed = False
            # Keep conversation in AWAITING_CONTACT_CONFIRMATION state for retry
            # DO NOT complete the conversation
            
            # Track retry
            contact.retry_count = (contact.retry_count or 0) + 1
            contact.last_retry_at = datetime.utcnow()
            
            # Send acknowledgment with retry notice
            self.sms_service.send_sms(
                to_number=conversation.technician_phone,
                message=f"Got it. I'll check back with you in 2 hours about {contact.full_name}.",
                contact_id=contact.id,
                conversation_id=conversation.id,
                db=db
            )
            
        else:
            # Invalid response
            logger.warning(f"Invalid YES/NO response: {message_body}")
            
            self.sms_service.send_sms(
                to_number=conversation.technician_phone,
                message=f"Please reply YES or NO. Were you able to make contact with {contact.full_name}?",
                contact_id=contact.id,
                conversation_id=conversation.id,
                db=db
            )
            return False
        
        conversation.last_message_at = datetime.utcnow()
        db.commit()
        return True
    
    def _handle_outcome_response(self, db: Session, conversation: SMSConversation, message_body: str) -> bool:
        """Handle outcome response (appointment set, quotes, waste of time, etc.)"""
        
        contact = conversation.contact
        response_lower = message_body.lower().strip()
        
        # Parse outcome
        outcome, outcome_text = self._parse_outcome(response_lower)
        
        if outcome:
            logger.info(f"Outcome for {contact.full_name}: {outcome_text}")
            
            conversation.outcome = outcome
            conversation.outcome_details = message_body
            
            contact.outcome = outcome
            contact.outcome_received_at = datetime.utcnow()
            
            # Check if project creation is needed
            if outcome == ContactOutcome.APPOINTMENT_SET:
                contact.project_creation_needed = True
                logger.info(f"Project creation needed for {contact.full_name}")
                
                # Start collecting project details
                conversation.state = ConversationState.AWAITING_PROJECT_TYPE
                conversation.completed_at = None  # Reset completion
                contact.status = ContactStatus.AWAITING_RESPONSE
                
                # Ask for project type
                self.sms_service.send_sms(
                    to_number=conversation.technician_phone,
                    message=(
                        f"Great! I need a few details to create the project for {contact.full_name}.\n\n"
                        "What type of project?\n"
                        "1 - Emergency Mitigation Services\n"
                        "2 - Mold\n"
                        "3 - Reconstruction\n"
                        "4 - Sewage\n"
                        "5 - Biohazard\n"
                        "6 - Contents\n"
                        "7 - Vandalism"
                    ),
                    contact_id=contact.id,
                    conversation_id=conversation.id,
                    db=db
                )
            else:
                # Complete conversation for non-appointment outcomes
                conversation.state = ConversationState.COMPLETED
                conversation.completed_at = datetime.utcnow()
                contact.status = ContactStatus.COMPLETED
                contact.completed_at = datetime.utcnow()
                
                # Send acknowledgment
                self.sms_service.send_sms(
                    to_number=conversation.technician_phone,
                    message=f"Got it, thanks for the update on {contact.full_name}!",
                    contact_id=contact.id,
                    conversation_id=conversation.id,
                    db=db
                )
            
            conversation.last_message_at = datetime.utcnow()
            db.commit()
            return True
            
        else:
            # Invalid outcome response
            logger.warning(f"Invalid outcome response: {message_body}")
            
            self.sms_service.send_sms(
                to_number=conversation.technician_phone,
                message=(
                    "Please reply with:\n"
                    "1 - Appointment set\n"
                    "2 - Looking for quotes\n"
                    "3 - Waste of time\n"
                    "4 - Something else"
                ),
                contact_id=contact.id,
                conversation_id=conversation.id,
                db=db
            )
            return False
    
    def _parse_outcome(self, response: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse outcome from technician response
        
        Returns:
            Tuple of (outcome_enum, outcome_text)
        """
        # Appointment set variations
        if any(word in response for word in ['1', 'appointment', 'appt', 'set', 'scheduled']):
            return ContactOutcome.APPOINTMENT_SET, "Appointment Set"
        
        # Looking for quotes variations
        if any(word in response for word in ['2', 'quote', 'quotes', 'estimate', 'pricing']):
            return ContactOutcome.LOOKING_FOR_QUOTES, "Looking for Quotes"
        
        # Waste of time variations
        if any(word in response for word in ['3', 'waste', 'no interest', 'not interested']):
            return ContactOutcome.WASTE_OF_TIME, "Waste of Time"
        
        # Something else variations
        if any(word in response for word in ['4', 'else', 'other', 'different']):
            return ContactOutcome.SOMETHING_ELSE, "Something Else"
        
        return None, None
    
    def _is_yes_response(self, response: str) -> bool:
        """Check if response is a YES"""
        yes_patterns = ['yes', 'y', 'yeah', 'yep', 'yup', 'sure', 'correct', 'affirmative']
        return any(pattern in response for pattern in yes_patterns)
    
    def _is_no_response(self, response: str) -> bool:
        """Check if response is a NO"""
        no_patterns = ['no', 'n', 'nope', 'nah', 'not yet', 'negative']
        return any(pattern in response for pattern in no_patterns)
    
    def _log_incoming_message(self, db: Session, conversation: SMSConversation, 
                             from_number: str, message_body: str, twilio_sid: str):
        """Log incoming SMS message to database"""
        
        message = SMSMessage(
            conversation_id=conversation.id,
            contact_id=conversation.contact_id,
            direction='inbound',
            from_number=from_number,
            to_number=self.sms_service.twilio_phone,
            message_body=message_body,
            twilio_sid=twilio_sid,
            sent_at=datetime.utcnow()
        )
        
        db.add(message)
        db.flush()

    def _handle_project_type(self, db: Session, conversation: SMSConversation, message_body: str) -> bool:
        """Handle project type response"""
        contact = conversation.contact
        response = message_body.strip().lower()
        
        # Map response to project type (matching Albiware options)
        project_type_map = {
            '1': 'Emergency Mitigation Services',
            '2': 'Mold',
            '3': 'Reconstruction',
            '4': 'Sewage',
            '5': 'Biohazard',
            '6': 'Contents',
            '7': 'Vandalism'
        }
        
        # Check for valid response
        keywords = ['emergency', 'mitigation', 'ems', 'mold', 'reconstruction', 'sewage', 'biohazard', 'contents', 'vandalism']
        if response in project_type_map or any(keyword in response for keyword in keywords):
            if response in project_type_map:
                project_type = project_type_map[response]
            elif 'emergency' in response or 'mitigation' in response or 'ems' in response:
                project_type = 'Emergency Mitigation Services'
            elif 'mold' in response:
                project_type = 'Mold'
            elif 'reconstruction' in response or 'recon' in response:
                project_type = 'Reconstruction'
            elif 'sewage' in response:
                project_type = 'Sewage'
            elif 'biohazard' in response or 'bio' in response:
                project_type = 'Biohazard'
            elif 'contents' in response or 'content' in response:
                project_type = 'Contents'
            elif 'vandalism' in response:
                project_type = 'Vandalism'
            else:
                project_type = 'Emergency Mitigation Services'  # Default
            
            contact.project_type = project_type
            conversation.state = ConversationState.AWAITING_PROPERTY_TYPE
            
            # Ask for property type
            self.sms_service.send_sms(
                to_number=conversation.technician_phone,
                message=(
                    "What type of property?\n"
                    "1 - Residential\n"
                    "2 - Commercial"
                ),
                contact_id=contact.id,
                conversation_id=conversation.id,
                db=db
            )
            
            conversation.last_message_at = datetime.utcnow()
            db.commit()
            return True
        else:
            # Invalid response
            self.sms_service.send_sms(
                to_number=conversation.technician_phone,
                message=(
                    "Please reply with:\n"
                    "1 - Emergency Mitigation Services\n"
                    "2 - Mold\n"
                    "3 - Reconstruction\n"
                    "4 - Sewage\n"
                    "5 - Biohazard\n"
                    "6 - Contents\n"
                    "7 - Vandalism"
                ),
                contact_id=contact.id,
                conversation_id=conversation.id,
                db=db
            )
            return False
    
    def _handle_property_type(self, db: Session, conversation: SMSConversation, message_body: str) -> bool:
        """Handle property type response"""
        contact = conversation.contact
        response = message_body.strip().lower()
        
        # Map response to property type
        if response == '1' or 'residential' in response or 'home' in response or 'house' in response:
            property_type = 'Residential'
        elif response == '2' or 'commercial' in response or 'business' in response:
            property_type = 'Commercial'
        else:
            # Invalid response
            self.sms_service.send_sms(
                to_number=conversation.technician_phone,
                message=(
                    "Please reply with:\n"
                    "1 - Residential\n"
                    "2 - Commercial"
                ),
                contact_id=contact.id,
                conversation_id=conversation.id,
                db=db
            )
            return False
        
        contact.property_type = property_type
        
        # If Residential, ask for subtype; if Commercial, skip to insurance
        if property_type == 'Residential':
            conversation.state = ConversationState.AWAITING_RESIDENTIAL_SUBTYPE
            
            # Ask for residential subtype
            self.sms_service.send_sms(
                to_number=conversation.technician_phone,
                message=(
                    "What type of residential property?\n"
                    "1 - Single Family Home\n"
                    "2 - Multi-Family Home\n"
                    "3 - Manufactured Home"
                ),
                contact_id=contact.id,
                conversation_id=conversation.id,
                db=db
            )
        else:
            # Commercial - skip to insurance
            conversation.state = ConversationState.AWAITING_INSURANCE
            
            # Ask about insurance
            self.sms_service.send_sms(
                to_number=conversation.technician_phone,
                message="Do they have insurance? Reply YES or NO",
                contact_id=contact.id,
                conversation_id=conversation.id,
                db=db
            )
        
        conversation.last_message_at = datetime.utcnow()
        db.commit()
        return True
    
    def _handle_residential_subtype(self, db: Session, conversation: SMSConversation, message_body: str) -> bool:
        """Handle residential subtype response"""
        contact = conversation.contact
        response = message_body.strip().lower()
        
        # Map response to residential subtype
        if response == '1' or 'single' in response or 'single family' in response:
            residential_subtype = 'Single Family Home'
        elif response == '2' or 'multi' in response or 'multi-family' in response:
            residential_subtype = 'Multi-Family Home'
        elif response == '3' or 'manufactured' in response or 'mobile' in response or 'trailer' in response:
            residential_subtype = 'Manufactured Home'
        else:
            # Invalid response
            self.sms_service.send_sms(
                to_number=conversation.technician_phone,
                message=(
                    "Please reply with:\n"
                    "1 - Single Family Home\n"
                    "2 - Multi-Family Home\n"
                    "3 - Manufactured Home"
                ),
                contact_id=contact.id,
                conversation_id=conversation.id,
                db=db
            )
            return False
        
        contact.residential_subtype = residential_subtype
        conversation.state = ConversationState.AWAITING_INSURANCE
        
        # Ask about insurance
        self.sms_service.send_sms(
            to_number=conversation.technician_phone,
            message="Do they have insurance? Reply YES or NO",
            contact_id=contact.id,
            conversation_id=conversation.id,
            db=db
        )
        
        conversation.last_message_at = datetime.utcnow()
        db.commit()
        return True
    
    def _handle_insurance(self, db: Session, conversation: SMSConversation, message_body: str) -> bool:
        """Handle insurance response"""
        contact = conversation.contact
        response = message_body.strip().lower()
        
        if self._is_yes_response(response):
            contact.has_insurance = True
            conversation.state = ConversationState.AWAITING_INSURANCE_COMPANY
            
            # Ask for insurance company
            self.sms_service.send_sms(
                to_number=conversation.technician_phone,
                message="What insurance company?",
                contact_id=contact.id,
                conversation_id=conversation.id,
                db=db
            )
            
        elif self._is_no_response(response):
            contact.has_insurance = False
            conversation.state = ConversationState.AWAITING_REFERRAL_SOURCE
            
            # Ask for referral source
            self.sms_service.send_sms(
                to_number=conversation.technician_phone,
                message=(
                    "How did they hear about us?\n"
                    "1 - Customer Referral\n"
                    "2 - Industry Partner\n"
                    "3 - Insurance Referral\n"
                    "4 - Lead Gen\n"
                    "5 - Online Marketing\n"
                    "6 - Plumber"
                ),
                contact_id=contact.id,
                conversation_id=conversation.id,
                db=db
            )
        else:
            # Invalid response
            self.sms_service.send_sms(
                to_number=conversation.technician_phone,
                message="Please reply YES or NO. Do they have insurance?",
                contact_id=contact.id,
                conversation_id=conversation.id,
                db=db
            )
            return False
        
        conversation.last_message_at = datetime.utcnow()
        db.commit()
        return True
    
    def _handle_insurance_company(self, db: Session, conversation: SMSConversation, message_body: str) -> bool:
        """Handle insurance company response"""
        contact = conversation.contact
        
        # Store insurance company name
        contact.insurance_company = message_body.strip()
        conversation.state = ConversationState.AWAITING_REFERRAL_SOURCE
        
        # Ask for referral source
        self.sms_service.send_sms(
            to_number=conversation.technician_phone,
            message=(
                "How did they hear about us?\n"
                "1 - Customer Referral\n"
                "2 - Industry Partner\n"
                "3 - Insurance Referral\n"
                "4 - Lead Gen\n"
                "5 - Online Marketing\n"
                "6 - Plumber"
            ),
            contact_id=contact.id,
            conversation_id=conversation.id,
            db=db
        )
        
        conversation.last_message_at = datetime.utcnow()
        db.commit()
        return True
    
    def _handle_referral_source(self, db: Session, conversation: SMSConversation, message_body: str) -> bool:
        """Handle referral source response"""
        contact = conversation.contact
        response = message_body.strip().lower()
        
        # Map response to referral source (Albiware values)
        referral_map = {
            '1': 'Customer Referral',
            '2': 'Industry Partner',
            '3': 'Insurance Referral',
            '4': 'Lead Gen',
            '5': 'Online Marketing',
            '6': 'Plumber'
        }
        
        keywords = ['lead', 'customer', 'insurance', 'online', 'industry', 'plumber']
        
        if response in referral_map or any(keyword in response for keyword in keywords):
            if response in referral_map:
                referral_source = referral_map[response]
            elif 'customer' in response or 'referral' in response:
                referral_source = 'Customer Referral'
            elif 'industry' in response or 'partner' in response:
                referral_source = 'Industry Partner'
            elif 'insurance' in response:
                referral_source = 'Insurance Referral'
            elif 'lead' in response:
                referral_source = 'Lead Gen'
            elif 'online' in response or 'marketing' in response:
                referral_source = 'Online Marketing'
            elif 'plumber' in response:
                referral_source = 'Plumber'
            else:
                referral_source = 'Customer Referral'  # Default
            
            contact.referral_source = referral_source
            
            # Mark conversation as completed
            conversation.state = ConversationState.COMPLETED
            conversation.completed_at = datetime.utcnow()
            contact.status = ContactStatus.COMPLETED
            contact.completed_at = datetime.utcnow()
            
            # Send confirmation
            self.sms_service.send_sms(
                to_number=conversation.technician_phone,
                message=(
                    f"Perfect! I have all the details for {contact.full_name}:\n"
                    f"• Project: {contact.project_type}\n"
                    f"• Property: {contact.property_type}\n"
                    f"• Insurance: {'Yes - ' + contact.insurance_company if contact.has_insurance else 'No'}\n"
                    f"• Source: {contact.referral_source}\n\n"
                    "I'll create the project in Albiware now. You'll get a confirmation once it's done!"
                ),
                contact_id=contact.id,
                conversation_id=conversation.id,
                db=db
            )
            
            conversation.last_message_at = datetime.utcnow()
            db.commit()
            return True
        else:
            # Invalid response
            self.sms_service.send_sms(
                to_number=conversation.technician_phone,
                message=(
                    "Please reply with:\n"
                    "1 - Customer Referral\n"
                    "2 - Industry Partner\n"
                    "3 - Insurance Referral\n"
                    "4 - Lead Gen\n"
                    "5 - Online Marketing\n"
                    "6 - Plumber"
                ),
                contact_id=contact.id,
                conversation_id=conversation.id,
                db=db
            )
            return False
