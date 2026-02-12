"""
Database Reset Script
Clears all existing contact records to prevent SMS spam to historical contacts
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.connection import SessionLocal
from database.enhanced_models import Contact, SMSConversation, SMSMessage, ProjectCreationAttempt
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def reset_database():
    """Clear all contact-related records from the database"""
    
    db = SessionLocal()
    
    try:
        # Count existing records
        contact_count = db.query(Contact).count()
        conversation_count = db.query(SMSConversation).count()
        message_count = db.query(SMSMessage).count()
        project_attempt_count = db.query(ProjectCreationAttempt).count()
        
        logger.info(f"Found {contact_count} contacts, {conversation_count} conversations, "
                   f"{message_count} messages, {project_attempt_count} project attempts")
        
        # Delete all records (in correct order due to foreign keys)
        db.query(ProjectCreationAttempt).delete()
        db.query(SMSMessage).delete()
        db.query(SMSConversation).delete()
        db.query(Contact).delete()
        
        db.commit()
        
        logger.info("✅ Database reset complete! All contact records cleared.")
        logger.info("The system will now only track contacts created after Feb 11, 2026")
        
    except Exception as e:
        logger.error(f"Error resetting database: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("\n⚠️  WARNING: This will delete ALL contact records from the database!")
    print("This is necessary to stop SMS spam to historical contacts.")
    print("After this, only contacts created after Feb 11, 2026 will be tracked.\n")
    
    response = input("Are you sure you want to continue? (yes/no): ")
    
    if response.lower() == 'yes':
        reset_database()
    else:
        print("Database reset cancelled.")
