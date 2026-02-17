"""
Enhanced Database Models for Contact Tracking and SMS Conversations
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from database.models import Base


class ContactStatus(str, enum.Enum):
    """Status of contact in our tracking system"""
    NEW = "new"
    FOLLOW_UP_SCHEDULED = "follow_up_scheduled"
    FOLLOW_UP_SENT = "follow_up_sent"
    AWAITING_RESPONSE = "awaiting_response"
    CONTACT_MADE = "contact_made"
    NO_CONTACT = "no_contact"
    COMPLETED = "completed"


class ContactOutcome(str, enum.Enum):
    """Outcome of contact follow-up"""
    APPOINTMENT_SET = "appointment_set"
    LOOKING_FOR_QUOTES = "looking_for_quotes"
    WASTE_OF_TIME = "waste_of_time"
    SOMETHING_ELSE = "something_else"
    PENDING = "pending"


class ConversationState(str, enum.Enum):
    """Current state in SMS conversation flow"""
    INITIAL = "initial"
    AWAITING_CONTACT_CONFIRMATION = "awaiting_contact_confirmation"
    AWAITING_OUTCOME = "awaiting_outcome"
    AWAITING_PROJECT_TYPE = "awaiting_project_type"
    AWAITING_PROPERTY_TYPE = "awaiting_property_type"
    AWAITING_RESIDENTIAL_SUBTYPE = "awaiting_residential_subtype"
    AWAITING_INSURANCE = "awaiting_insurance"
    AWAITING_INSURANCE_COMPANY = "awaiting_insurance_company"
    AWAITING_APPOINTMENT_DATETIME = "awaiting_appointment_datetime"
    AWAITING_APPOINTMENT_CONFLICT_CONFIRMATION = "awaiting_appointment_conflict_confirmation"
    AWAITING_REFERRAL_SOURCE = "awaiting_referral_source"
    COMPLETED = "completed"


class Contact(Base):
    """
    Tracks contacts from Albiware for follow-up automation
    """
    __tablename__ = "contacts"
    
    id = Column(Integer, primary_key=True, index=True)
    albiware_contact_id = Column(Integer, unique=True, index=True, nullable=False)
    
    # Contact Information
    first_name = Column(String(100))
    last_name = Column(String(100))
    full_name = Column(String(200))
    email = Column(String(200))
    phone_number = Column(String(50))
    address = Column(Text)
    
    # Tracking Information
    status = Column(String(50), default=ContactStatus.NEW)
    outcome = Column(String(50), default=ContactOutcome.PENDING)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    albiware_created_at = Column(DateTime)
    follow_up_scheduled_at = Column(DateTime)
    follow_up_sent_at = Column(DateTime)
    contact_made_at = Column(DateTime)
    outcome_received_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Project Creation
    project_creation_needed = Column(Boolean, default=False)
    project_created = Column(Boolean, default=False)
    albiware_project_id = Column(Integer, nullable=True)
    project_created_at = Column(DateTime, nullable=True)
    
    # Project Details (collected from SMS)
    project_type = Column(String(100), nullable=True)  # Water, Fire, Mold, Other
    property_type = Column(String(50), nullable=True)  # Residential, Commercial
    residential_subtype = Column(String(50), nullable=True)  # Single Family, Multi-Family, Manufactured
    has_insurance = Column(Boolean, nullable=True)
    insurance_company = Column(String(200), nullable=True)
    referral_source = Column(String(100), nullable=True)  # Google, Yelp, Referral, Other
    
    # Asbestos Testing (for pre-1988 properties)
    asbestos_testing_required = Column(Boolean, default=False)
    asbestos_notification_sent_at = Column(DateTime, nullable=True)
    
    # Appointment Scheduling
    appointment_datetime = Column(DateTime, nullable=True)  # Scheduled appointment date/time
    appointment_created_in_calendar = Column(Boolean, default=False)  # Whether calendar event was created
    calendar_event_id = Column(String(200), nullable=True)  # Google Calendar event ID
    
    # Follow-up Retry & Persistence Mode
    retry_count = Column(Integer, default=0)  # Number of times we've retried after NO response
    last_retry_at = Column(DateTime, nullable=True)  # When we last sent a retry
    persistence_mode = Column(Boolean, default=False)  # Whether we're in 10-min persistence mode
    persistence_count = Column(Integer, default=0)  # Number of persistence follow-ups sent
    last_persistence_at = Column(DateTime, nullable=True)  # When we last sent a persistence message
    
    # Relationships
    conversations = relationship("SMSConversation", back_populates="contact")
    messages = relationship("SMSMessage", back_populates="contact")
    
    def __repr__(self):
        return f"<Contact {self.full_name} ({self.albiware_contact_id})>"


class SMSConversation(Base):
    """
    Tracks SMS conversation threads for each contact follow-up
    """
    __tablename__ = "sms_conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    
    # Conversation State
    state = Column(String(50), default=ConversationState.INITIAL)
    technician_phone = Column(String(50))
    
    # Conversation Data
    contact_confirmed = Column(Boolean, default=False)
    outcome = Column(String(50), nullable=True)
    outcome_details = Column(Text, nullable=True)
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    last_message_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    contact = relationship("Contact", back_populates="conversations")
    messages = relationship("SMSMessage", back_populates="conversation")
    
    def __repr__(self):
        return f"<SMSConversation {self.id} - {self.state}>"


class SMSMessage(Base):
    """
    Tracks individual SMS messages in conversations
    """
    __tablename__ = "sms_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("sms_conversations.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    
    # Message Details
    direction = Column(String(20))  # 'outbound' or 'inbound'
    from_number = Column(String(50))
    to_number = Column(String(50))
    message_body = Column(Text)
    
    # Twilio Details
    twilio_sid = Column(String(100), unique=True, nullable=True)
    twilio_status = Column(String(50), nullable=True)
    
    # Timestamps
    sent_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime, nullable=True)
    
    # Relationships
    conversation = relationship("SMSConversation", back_populates="messages")
    contact = relationship("Contact", back_populates="messages")
    
    def __repr__(self):
        return f"<SMSMessage {self.direction} - {self.sent_at}>"


class ProjectCreationLog(Base):
    """
    Logs automated project creation attempts
    """
    __tablename__ = "project_creation_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    
    # Attempt Details
    attempt_number = Column(Integer, default=1)
    status = Column(String(50))  # 'pending', 'in_progress', 'success', 'failed'
    
    # Browser Automation Details
    browser_session_id = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    screenshot_path = Column(String(500), nullable=True)
    
    # Result
    albiware_project_id = Column(Integer, nullable=True)
    albiware_project_name = Column(String(200), nullable=True)
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<ProjectCreationLog {self.id} - {self.status}>"
