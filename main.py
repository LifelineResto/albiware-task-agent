"""
Enhanced Main Application for Albiware Task & Contact Agent
Includes task tracking, contact monitoring, SMS conversations, and automated project creation
"""

from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging
import sys

from config.settings import settings
from database.database import Database
from database.models import Task, Notification, TaskCompletionLog, SystemLog
from database.enhanced_models import Contact, SMSConversation, SMSMessage, ProjectCreationLog, ContactStatus, ConversationState
from services.albiware_client import AlbiwareClient
from services.sms_service import SMSService
from services.notification_engine import NotificationEngine
from services.contact_monitor import ContactMonitor
from services.conversation_handler import ConversationHandler
from services.project_creator import AlbiwareProjectCreator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Albiware Task & Contact Agent",
    description="AI agent for tracking Albiware tasks, contacts, and automating SMS follow-ups",
    version="2.0.0"
)

# Initialize services
database = Database(settings.database_url)
albiware_client = AlbiwareClient(settings.albiware_api_key, settings.albiware_base_url)
sms_service = SMSService(
    settings.twilio_account_sid,
    settings.twilio_auth_token,
    settings.twilio_from_number
)
notification_engine = NotificationEngine(
    albiware_client,
    sms_service,
    settings.reminder_hours_before_due,
    settings.max_reminders_per_task
)

# Initialize contact monitoring services
contact_monitor = ContactMonitor(albiware_client, sms_service)
conversation_handler = ConversationHandler(sms_service)

# Initialize project creator (with Albiware credentials)
project_creator = AlbiwareProjectCreator(
    albiware_email=settings.albiware_email,
    albiware_password=settings.albiware_password
)

# Initialize scheduler
scheduler = BackgroundScheduler()


def get_db():
    """Dependency for getting database session."""
    db_gen = database.get_session()
    db = next(db_gen)
    try:
        yield db
    finally:
        db.close()


def scheduled_task_sync():
    """Scheduled task to sync tasks from Albiware and send notifications."""
    logger.info("Starting scheduled task sync...")
    
    db_gen = database.get_session()
    db = next(db_gen)
    
    try:
        # Sync tasks from Albiware
        tasks_synced = notification_engine.sync_tasks_from_albiware(db)
        logger.info(f"Synced {tasks_synced} tasks")
        
        # Process task notifications
        staff_phones = [
            phone.strip() 
            for phone in settings.staff_phone_numbers.split(',') 
            if phone.strip()
        ]
        
        if staff_phones:
            notifications_sent = notification_engine.process_task_notifications(db, staff_phones)
            logger.info(f"Sent {notifications_sent} task notifications")
        else:
            logger.warning("No staff phone numbers configured")
        
    except Exception as e:
        logger.error(f"Error in scheduled task sync: {e}")
    finally:
        db.close()


def scheduled_contact_sync():
    """Scheduled task to sync contacts and process follow-ups."""
    logger.info("Starting scheduled contact sync...")
    
    db_gen = database.get_session()
    db = next(db_gen)
    
    try:
        # Sync new contacts from Albiware
        new_contacts = contact_monitor.sync_contacts(db)
        logger.info(f"Found {new_contacts} new contacts")
        
        # Process scheduled follow-ups
        technician_phone = settings.technician_phone_number
        if technician_phone:
            follow_ups_sent = contact_monitor.process_scheduled_follow_ups(db, technician_phone)
            logger.info(f"Sent {follow_ups_sent} follow-up messages")
        else:
            logger.warning("No technician phone number configured")
        
    except Exception as e:
        logger.error(f"Error in scheduled contact sync: {e}")
    finally:
        db.close()


def scheduled_project_creation():
    """Scheduled task to create projects for contacts with appointments set."""
    logger.info("Starting scheduled project creation...")
    
    db_gen = database.get_session()
    db = next(db_gen)
    
    try:
        projects_created = project_creator.process_pending_projects(db)
        logger.info(f"Created {projects_created} projects")
        
    except Exception as e:
        logger.error(f"Error in scheduled project creation: {e}")
    finally:
        db.close()


@app.on_event("startup")
async def startup_event():
    """Initialize database and start scheduler on application startup."""
    logger.info("Starting Enhanced Albiware Task & Contact Agent...")
    
    # Create database tables
    database.create_tables()
    logger.info("Database initialized")
    
    # Start task sync scheduler (every 15 minutes)
    scheduler.add_job(
        scheduled_task_sync,
        trigger=IntervalTrigger(minutes=settings.polling_interval_minutes),
        id='task_sync_job',
        name='Sync tasks and send notifications',
        replace_existing=True
    )
    
    # Start contact sync scheduler (every 10 minutes)
    scheduler.add_job(
        scheduled_contact_sync,
        trigger=IntervalTrigger(minutes=10),
        id='contact_sync_job',
        name='Sync contacts and process follow-ups',
        replace_existing=True
    )
    
    # Start project creation scheduler (every 5 minutes)
    scheduler.add_job(
        scheduled_project_creation,
        trigger=IntervalTrigger(minutes=5),
        id='project_creation_job',
        name='Create projects for appointments',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Scheduler started with all jobs")
    
    # Run initial syncs
    scheduled_task_sync()
    scheduled_contact_sync()


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown scheduler on application shutdown."""
    logger.info("Shutting down Enhanced Albiware Agent...")
    scheduler.shutdown()


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the analytics dashboard."""
    try:
        with open("dashboard/index.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Dashboard not found</h1><p>Please ensure dashboard/index.html exists.</p>",
            status_code=404
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }


@app.get("/74916c351bd2f695c708eccb66f5bb12.html")
async def twilio_domain_verification():
    """Twilio domain verification endpoint."""
    return Response(
        content="twilio-domain-verification=74916c351bd2f695c708eccb66f5bb12",
        media_type="text/plain"
    )


@app.post("/webhooks/twilio/sms")
async def twilio_sms_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook endpoint for incoming Twilio SMS messages
    Handles two-way SMS conversations with technicians
    """
    try:
        # Parse Twilio webhook data
        form_data = await request.form()
        
        from_number = form_data.get('From')
        to_number = form_data.get('To')
        message_body = form_data.get('Body')
        message_sid = form_data.get('MessageSid')
        
        logger.info(f"Received SMS webhook from {from_number}: {message_body}")
        
        # Process the incoming message
        success = conversation_handler.handle_incoming_sms(
            db=db,
            from_number=from_number,
            message_body=message_body,
            twilio_sid=message_sid
        )
        
        if success:
            # Return TwiML response (empty response means no auto-reply)
            return Response(content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type="application/xml")
        else:
            logger.warning("Failed to process incoming SMS")
            return Response(content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error processing Twilio webhook: {e}")
        return Response(content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type="application/xml")


# ===== API ENDPOINTS =====

@app.post("/api/test/send-followup")
async def test_send_followup(
    contact_name: str,
    contact_phone: str,
    db: Session = Depends(get_db)
):
    """
    TEST ENDPOINT: Manually trigger a 24-hour follow-up SMS
    This creates a conversation and sends the initial follow-up message
    """
    try:
        # Create or get test contact
        contact = db.query(Contact).filter(Contact.phone_number == contact_phone).first()
        
        if not contact:
            # Use a numeric test ID (999000000 + last 4 digits of phone)
            test_id = 999000000 + int(contact_phone[-4:])
            contact = Contact(
                albiware_contact_id=test_id,
                full_name=contact_name,
                phone_number=contact_phone,
                email=None,
                status=ContactStatus.FOLLOW_UP_SCHEDULED,
                created_at=datetime.utcnow()
            )
            db.add(contact)
            db.flush()
        
        # Create conversation
        conversation = SMSConversation(
            contact_id=contact.id,
            technician_phone=settings.technician_phone_number,
            state=ConversationState.AWAITING_CONTACT_CONFIRMATION,
            started_at=datetime.utcnow(),
            last_message_at=datetime.utcnow()
        )
        db.add(conversation)
        db.flush()
        
        # Send follow-up message
        message = f"Hi Rudy, were you able to make contact with {contact_name} yet? Reply YES or NO."
        
        success = sms_service.send_sms(
            to_number=settings.technician_phone_number,
            message=message,
            contact_id=contact.id,
            conversation_id=conversation.id,
            db=db
        )
        
        if success:
            contact.follow_up_sent_at = datetime.utcnow()
            contact.status = ContactStatus.FOLLOW_UP_SENT
            db.commit()
            
            return {
                "success": True,
                "message": "Test follow-up sent",
                "contact_id": contact.id,
                "conversation_id": conversation.id
            }
        else:
            return {"success": False, "message": "Failed to send SMS"}
            
    except Exception as e:
        logger.error(f"Error in test endpoint: {e}")
        return {"success": False, "message": str(e)}


@app.get("/api/contacts")
async def get_contacts(
    status: str = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all contacts from the database."""
    query = db.query(Contact)
    
    if status:
        query = query.filter(Contact.status == status)
    
    contacts = query.order_by(Contact.created_at.desc()).limit(limit).all()
    
    return {
        "count": len(contacts),
        "contacts": [
            {
                "id": contact.id,
                "albiware_contact_id": contact.albiware_contact_id,
                "full_name": contact.full_name,
                "phone_number": contact.phone_number,
                "email": contact.email,
                "status": contact.status,
                "outcome": contact.outcome,
                "created_at": contact.created_at.isoformat() if contact.created_at else None,
                "follow_up_sent_at": contact.follow_up_sent_at.isoformat() if contact.follow_up_sent_at else None,
                "project_creation_needed": contact.project_creation_needed,
                "project_created": contact.project_created
            }
            for contact in contacts
        ]
    }


@app.get("/api/conversations")
async def get_conversations(
    contact_id: int = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get SMS conversation history."""
    query = db.query(SMSConversation)
    
    if contact_id:
        query = query.filter(SMSConversation.contact_id == contact_id)
    
    conversations = query.order_by(SMSConversation.started_at.desc()).limit(limit).all()
    
    return {
        "count": len(conversations),
        "conversations": [
            {
                "id": conv.id,
                "contact_id": conv.contact_id,
                "state": conv.state,
                "contact_confirmed": conv.contact_confirmed,
                "outcome": conv.outcome,
                "started_at": conv.started_at.isoformat() if conv.started_at else None,
                "completed_at": conv.completed_at.isoformat() if conv.completed_at else None
            }
            for conv in conversations
        ]
    }


@app.get("/api/tasks")
async def get_tasks(
    status: str = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all tasks from the database."""
    query = db.query(Task)
    
    if status:
        query = query.filter(Task.status == status)
    
    tasks = query.order_by(Task.due_date.asc()).limit(limit).all()
    
    return {
        "count": len(tasks),
        "tasks": [
            {
                "id": task.id,
                "albiware_task_id": task.albiware_task_id,
                "task_name": task.task_name,
                "project_name": task.project_name,
                "status": task.status,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None
            }
            for task in tasks
        ]
    }


@app.post("/api/admin/reset-database")
async def reset_database(db: Session = Depends(get_db)):
    """
    ADMIN ENDPOINT: Reset database by clearing all contact records
    This stops SMS spam to historical contacts
    Only contacts created after Feb 11, 2026 will be tracked going forward
    """
    try:
        logger.info("Starting database reset...")
        
        # Count existing records
        contact_count = db.query(Contact).count()
        conversation_count = db.query(SMSConversation).count()
        message_count = db.query(SMSMessage).count()
        project_log_count = db.query(ProjectCreationLog).count()
        
        logger.info(f"Found {contact_count} contacts, {conversation_count} conversations, "
                   f"{message_count} messages, {project_log_count} project creation logs")
        
        # Delete all records (in correct order due to foreign keys)
        db.query(ProjectCreationLog).delete()
        db.query(SMSMessage).delete()
        db.query(SMSConversation).delete()
        db.query(Contact).delete()
        
        db.commit()
        
        logger.info("✅ Database reset complete! All contact records cleared.")
        
        return {
            "success": True,
            "message": "Database reset complete",
            "records_deleted": {
                "contacts": contact_count,
                "conversations": conversation_count,
                "messages": message_count,
                "project_logs": project_log_count
            },
            "note": "System will now only track contacts created after Feb 11, 2026"
        }
        
    except Exception as e:
        logger.error(f"Error resetting database: {e}")
        db.rollback()
        return {
            "success": False,
            "message": f"Error resetting database: {str(e)}"
        }


@app.post("/api/admin/run-migration")
async def run_migration(db: Session = Depends(get_db)):
    """
    ADMIN ENDPOINT: Run database migration to add project detail fields
    Adds: project_type, property_type, has_insurance, insurance_company, referral_source
    """
    try:
        logger.info("Running database migration...")
        
        from sqlalchemy import text
        
        migrations = [
            "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS project_type VARCHAR(100)",
            "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS property_type VARCHAR(50)",
            "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS has_insurance BOOLEAN",
            "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS insurance_company VARCHAR(200)",
            "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS referral_source VARCHAR(100)",
        ]
        
        for migration_sql in migrations:
            logger.info(f"Running: {migration_sql}")
            db.execute(text(migration_sql))
        
        db.commit()
        
        logger.info("✅ Migration completed successfully!")
        
        return {
            "success": True,
            "message": "Database migration completed",
            "migrations_run": len(migrations),
            "fields_added": ["project_type", "property_type", "has_insurance", "insurance_company", "referral_source"]
        }
        
    except Exception as e:
        logger.error(f"Migration error: {e}")
        db.rollback()
        return {
            "success": False,
            "message": f"Migration failed: {str(e)}"
        }


@app.get("/api/analytics/summary")
async def get_analytics_summary(db: Session = Depends(get_db)):
    """Get summary analytics for both tasks and contacts."""
    # Task analytics
    total_tasks = db.query(Task).count()
    completed_tasks = db.query(Task).filter(Task.completed_at.isnot(None)).count()
    
    # Contact analytics
    total_contacts = db.query(Contact).count()
    contacts_with_follow_up = db.query(Contact).filter(Contact.follow_up_sent_at.isnot(None)).count()
    contacts_with_appointments = db.query(Contact).filter(Contact.outcome == 'appointment_set').count()
    projects_created = db.query(Contact).filter(Contact.project_created == True).count()
    
    # Conversation analytics
    total_conversations = db.query(SMSConversation).count()
    completed_conversations = db.query(SMSConversation).filter(SMSConversation.completed_at.isnot(None)).count()
    
    return {
        "tasks": {
            "total": total_tasks,
            "completed": completed_tasks,
            "active": total_tasks - completed_tasks
        },
        "contacts": {
            "total": total_contacts,
            "follow_ups_sent": contacts_with_follow_up,
            "appointments_set": contacts_with_appointments,
            "projects_created": projects_created
        },
        "conversations": {
            "total": total_conversations,
            "completed": completed_conversations,
            "active": total_conversations - completed_conversations
        }
    }


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
