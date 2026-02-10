"""
Notification Engine
Core logic for determining when to send notifications and tracking task completion.
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import logging

from database.models import Task, Notification, TaskCompletionLog, SystemLog
from services.albiware_client import AlbiwareClient
from services.sms_service import SMSService

logger = logging.getLogger(__name__)


class NotificationEngine:
    """Engine for managing task notifications and tracking."""
    
    def __init__(
        self,
        albiware_client: AlbiwareClient,
        sms_service: SMSService,
        reminder_hours_before_due: int = 24,
        max_reminders_per_task: int = 5
    ):
        """
        Initialize the notification engine.
        
        Args:
            albiware_client: Albiware API client
            sms_service: SMS service for sending notifications
            reminder_hours_before_due: Hours before due date to send first reminder
            max_reminders_per_task: Maximum number of reminders per task
        """
        self.albiware_client = albiware_client
        self.sms_service = sms_service
        self.reminder_hours_before_due = reminder_hours_before_due
        self.max_reminders_per_task = max_reminders_per_task
    
    def sync_tasks_from_albiware(self, db: Session) -> int:
        """
        Sync tasks from Albiware to local database.
        
        Args:
            db: Database session
            
        Returns:
            Number of tasks synced
        """
        try:
            # Get all open projects
            projects = self.albiware_client.get_all_projects(open_only=True)
            tasks_synced = 0
            
            for project in projects:
                project_id = project.get('id')
                project_name = project.get('name', 'Unknown Project')
                
                # Get tasks for this project
                tasks = self.albiware_client.get_all_tasks(project_id=project_id)
                
                for task_data in tasks:
                    task_id = task_data.get('id')
                    
                    # Check if task already exists
                    existing_task = db.query(Task).filter(
                        Task.albiware_task_id == task_id
                    ).first()
                    
                    if existing_task:
                        # Update existing task
                        existing_task.task_name = task_data.get('name', 'Unnamed Task')
                        existing_task.status = task_data.get('status', 'unknown')
                        existing_task.assigned_to = task_data.get('assignedTo')
                        existing_task.updated_at = datetime.utcnow()
                        
                        # Check if task was completed
                        if task_data.get('status') == 'completed' and not existing_task.completed_at:
                            existing_task.completed_at = datetime.utcnow()
                            self._log_task_completion(db, existing_task)
                    else:
                        # Create new task
                        due_date_str = task_data.get('dueDate')
                        due_date = None
                        if due_date_str:
                            try:
                                due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                            except:
                                pass
                        
                        new_task = Task(
                            albiware_task_id=task_id,
                            task_name=task_data.get('name', 'Unnamed Task'),
                            project_id=project_id,
                            project_name=project_name,
                            due_date=due_date,
                            status=task_data.get('status', 'unknown'),
                            assigned_to=task_data.get('assignedTo')
                        )
                        db.add(new_task)
                    
                    tasks_synced += 1
            
            db.commit()
            logger.info(f"Synced {tasks_synced} tasks from Albiware")
            
            # Log system event
            self._log_system_event(
                db,
                event_type='polling',
                message=f'Successfully synced {tasks_synced} tasks from Albiware',
                severity='info'
            )
            
            return tasks_synced
            
        except Exception as e:
            logger.error(f"Error syncing tasks from Albiware: {e}")
            self._log_system_event(
                db,
                event_type='error',
                message=f'Error syncing tasks: {str(e)}',
                severity='error'
            )
            db.rollback()
            return 0
    
    def process_task_notifications(self, db: Session, staff_phone_numbers: List[str]) -> int:
        """
        Process all tasks and send notifications as needed.
        
        Args:
            db: Database session
            staff_phone_numbers: List of phone numbers to send notifications to
            
        Returns:
            Number of notifications sent
        """
        notifications_sent = 0
        
        try:
            # Get all incomplete tasks
            incomplete_tasks = db.query(Task).filter(
                Task.status != 'completed',
                Task.completed_at.is_(None)
            ).all()
            
            for task in incomplete_tasks:
                # Skip tasks without due dates
                if not task.due_date:
                    continue
                
                # Check if task needs a reminder
                if self._should_send_reminder(db, task):
                    for phone_number in staff_phone_numbers:
                        if self._send_task_notification(db, task, phone_number):
                            notifications_sent += 1
            
            db.commit()
            logger.info(f"Sent {notifications_sent} notifications")
            
            return notifications_sent
            
        except Exception as e:
            logger.error(f"Error processing task notifications: {e}")
            self._log_system_event(
                db,
                event_type='error',
                message=f'Error processing notifications: {str(e)}',
                severity='error'
            )
            db.rollback()
            return 0
    
    def _should_send_reminder(self, db: Session, task: Task) -> bool:
        """
        Determine if a task should receive a reminder.
        
        Args:
            db: Database session
            task: Task to check
            
        Returns:
            True if reminder should be sent, False otherwise
        """
        # Count existing notifications for this task
        notification_count = db.query(Notification).filter(
            Notification.task_id == task.id
        ).count()
        
        # Check if max reminders reached
        if notification_count >= self.max_reminders_per_task:
            return False
        
        # Calculate time until due
        now = datetime.utcnow()
        time_until_due = task.due_date - now
        
        # Send first reminder X hours before due date
        if notification_count == 0:
            reminder_threshold = timedelta(hours=self.reminder_hours_before_due)
            if time_until_due <= reminder_threshold and time_until_due > timedelta(0):
                return True
        
        # Send reminders for overdue tasks
        if time_until_due < timedelta(0):
            # Get last notification
            last_notification = db.query(Notification).filter(
                Notification.task_id == task.id
            ).order_by(Notification.sent_at.desc()).first()
            
            if last_notification:
                # Send reminder every 24 hours for overdue tasks
                time_since_last = now - last_notification.sent_at
                if time_since_last >= timedelta(hours=24):
                    return True
            else:
                # No notifications sent yet, send one
                return True
        
        return False
    
    def _send_task_notification(self, db: Session, task: Task, phone_number: str) -> bool:
        """
        Send a notification for a specific task.
        
        Args:
            db: Database session
            task: Task to send notification for
            phone_number: Recipient phone number
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        try:
            now = datetime.utcnow()
            is_overdue = task.due_date < now
            
            # Send appropriate notification type
            if is_overdue:
                days_overdue = (now - task.due_date).days
                message_sid = self.sms_service.send_task_completion_reminder(
                    to_number=phone_number,
                    task_name=task.task_name,
                    project_name=task.project_name,
                    days_overdue=days_overdue,
                    task_id=task.albiware_task_id
                )
                notification_type = 'overdue'
            else:
                message_sid = self.sms_service.send_task_reminder(
                    to_number=phone_number,
                    task_name=task.task_name,
                    project_name=task.project_name,
                    due_date=task.due_date,
                    task_id=task.albiware_task_id
                )
                notification_type = 'reminder'
            
            if message_sid:
                # Log notification in database
                notification = Notification(
                    task_id=task.id,
                    recipient_phone=phone_number,
                    message_body=f"Task reminder sent for: {task.task_name}",
                    twilio_message_sid=message_sid,
                    delivery_status='sent',
                    notification_type=notification_type
                )
                db.add(notification)
                db.commit()
                
                logger.info(f"Notification sent for task {task.albiware_task_id} to {phone_number}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error sending notification for task {task.id}: {e}")
            return False
    
    def _log_task_completion(self, db: Session, task: Task):
        """
        Log task completion for analytics.
        
        Args:
            db: Database session
            task: Completed task
        """
        try:
            # Count notifications sent for this task
            notification_count = db.query(Notification).filter(
                Notification.task_id == task.id
            ).count()
            
            # Get first and last notification times
            first_notification = db.query(Notification).filter(
                Notification.task_id == task.id
            ).order_by(Notification.sent_at.asc()).first()
            
            last_notification = db.query(Notification).filter(
                Notification.task_id == task.id
            ).order_by(Notification.sent_at.desc()).first()
            
            # Calculate completion metrics
            days_to_complete = None
            was_overdue = False
            days_overdue = None
            
            if task.due_date:
                completion_time = task.completed_at or datetime.utcnow()
                time_diff = completion_time - task.due_date
                days_to_complete = time_diff.days
                
                if time_diff.total_seconds() > 0:
                    was_overdue = True
                    days_overdue = time_diff.days
            
            # Create completion log
            completion_log = TaskCompletionLog(
                albiware_task_id=task.albiware_task_id,
                task_name=task.task_name,
                project_name=task.project_name,
                due_date=task.due_date,
                completed_at=task.completed_at or datetime.utcnow(),
                days_to_complete=days_to_complete,
                was_overdue=was_overdue,
                days_overdue=days_overdue,
                total_notifications_sent=notification_count,
                first_notification_sent_at=first_notification.sent_at if first_notification else None,
                last_notification_sent_at=last_notification.sent_at if last_notification else None
            )
            
            db.add(completion_log)
            db.commit()
            
            logger.info(f"Task completion logged for task {task.albiware_task_id}")
            
        except Exception as e:
            logger.error(f"Error logging task completion: {e}")
    
    def _log_system_event(
        self,
        db: Session,
        event_type: str,
        message: str,
        severity: str,
        metadata: Optional[str] = None
    ):
        """
        Log a system event.
        
        Args:
            db: Database session
            event_type: Type of event
            message: Event message
            severity: Event severity
            metadata: Optional metadata JSON string
        """
        try:
            system_log = SystemLog(
                event_type=event_type,
                message=message,
                severity=severity,
                metadata=metadata
            )
            db.add(system_log)
            db.commit()
        except Exception as e:
            logger.error(f"Error logging system event: {e}")
