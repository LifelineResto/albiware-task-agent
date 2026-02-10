"""
Main application for the Albiware Task Agent system.
Provides REST API and scheduled task processing.
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
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
from services.albiware_client import AlbiwareClient
from services.sms_service import SMSService
from services.notification_engine import NotificationEngine

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
    title="Albiware Task Agent",
    description="AI agent for tracking Albiware tasks and sending SMS reminders",
    version="1.0.0"
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
    """Scheduled task to sync data from Albiware and send notifications."""
    logger.info("Starting scheduled task sync...")
    
    db_gen = database.get_session()
    db = next(db_gen)
    
    try:
        # Sync tasks from Albiware
        tasks_synced = notification_engine.sync_tasks_from_albiware(db)
        logger.info(f"Synced {tasks_synced} tasks")
        
        # Process notifications
        staff_phones = [
            phone.strip() 
            for phone in settings.staff_phone_numbers.split(',') 
            if phone.strip()
        ]
        
        if staff_phones:
            notifications_sent = notification_engine.process_task_notifications(db, staff_phones)
            logger.info(f"Sent {notifications_sent} notifications")
        else:
            logger.warning("No staff phone numbers configured")
        
    except Exception as e:
        logger.error(f"Error in scheduled task: {e}")
    finally:
        db.close()


@app.on_event("startup")
async def startup_event():
    """Initialize database and start scheduler on application startup."""
    logger.info("Starting Albiware Task Agent...")
    
    # Create database tables
    database.create_tables()
    logger.info("Database initialized")
    
    # Start scheduler
    scheduler.add_job(
        scheduled_task_sync,
        trigger=IntervalTrigger(minutes=settings.polling_interval_minutes),
        id='task_sync_job',
        name='Sync tasks and send notifications',
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"Scheduler started with {settings.polling_interval_minutes} minute interval")
    
    # Run initial sync
    scheduled_task_sync()


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown scheduler on application shutdown."""
    logger.info("Shutting down Albiware Task Agent...")
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
        "timestamp": datetime.utcnow().isoformat()
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


@app.get("/api/notifications")
async def get_notifications(
    task_id: int = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get notification history."""
    query = db.query(Notification)
    
    if task_id:
        query = query.filter(Notification.task_id == task_id)
    
    notifications = query.order_by(Notification.sent_at.desc()).limit(limit).all()
    
    return {
        "count": len(notifications),
        "notifications": [
            {
                "id": notif.id,
                "task_id": notif.task_id,
                "recipient_phone": notif.recipient_phone,
                "notification_type": notif.notification_type,
                "delivery_status": notif.delivery_status,
                "sent_at": notif.sent_at.isoformat()
            }
            for notif in notifications
        ]
    }


@app.get("/api/completion-logs")
async def get_completion_logs(
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get task completion logs for analytics."""
    logs = db.query(TaskCompletionLog).order_by(
        TaskCompletionLog.completed_at.desc()
    ).limit(limit).all()
    
    return {
        "count": len(logs),
        "logs": [
            {
                "id": log.id,
                "task_name": log.task_name,
                "project_name": log.project_name,
                "completed_at": log.completed_at.isoformat(),
                "was_overdue": log.was_overdue,
                "days_overdue": log.days_overdue,
                "total_notifications_sent": log.total_notifications_sent
            }
            for log in logs
        ]
    }


@app.get("/api/analytics/summary")
async def get_analytics_summary(db: Session = Depends(get_db)):
    """Get summary analytics."""
    total_tasks = db.query(Task).count()
    completed_tasks = db.query(Task).filter(Task.completed_at.isnot(None)).count()
    overdue_tasks = db.query(Task).filter(
        Task.due_date < datetime.utcnow(),
        Task.completed_at.is_(None)
    ).count()
    total_notifications = db.query(Notification).count()
    
    # Calculate average notifications per completed task
    completion_logs = db.query(TaskCompletionLog).all()
    avg_notifications = 0
    if completion_logs:
        avg_notifications = sum(log.total_notifications_sent for log in completion_logs) / len(completion_logs)
    
    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "overdue_tasks": overdue_tasks,
        "total_notifications_sent": total_notifications,
        "average_notifications_per_task": round(avg_notifications, 2)
    }


@app.post("/api/sync")
async def manual_sync(db: Session = Depends(get_db)):
    """Manually trigger a sync from Albiware."""
    try:
        tasks_synced = notification_engine.sync_tasks_from_albiware(db)
        return {
            "success": True,
            "tasks_synced": tasks_synced,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error in manual sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/notifications/send")
async def manual_notification_send(db: Session = Depends(get_db)):
    """Manually trigger notification processing."""
    try:
        staff_phones = [
            phone.strip() 
            for phone in settings.staff_phone_numbers.split(',') 
            if phone.strip()
        ]
        
        if not staff_phones:
            raise HTTPException(status_code=400, detail="No staff phone numbers configured")
        
        notifications_sent = notification_engine.process_task_notifications(db, staff_phones)
        return {
            "success": True,
            "notifications_sent": notifications_sent,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error sending notifications: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
