"""
Database models for tracking notifications and task completion.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Task(Base):
    """Model for tracking tasks from Albiware."""
    
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    albiware_task_id = Column(Integer, unique=True, index=True, nullable=False)
    task_name = Column(String(500), nullable=False)
    project_id = Column(Integer, nullable=False)
    project_name = Column(String(500), nullable=False)
    due_date = Column(DateTime, nullable=True)
    status = Column(String(100), nullable=False)
    assigned_to = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    notifications = relationship("Notification", back_populates="task", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Task(id={self.id}, name='{self.task_name}', status='{self.status}')>"


class Notification(Base):
    """Model for tracking sent notifications."""
    
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    recipient_phone = Column(String(20), nullable=False)
    recipient_name = Column(String(200), nullable=True)
    message_body = Column(Text, nullable=False)
    twilio_message_sid = Column(String(100), nullable=True)
    delivery_status = Column(String(50), nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime, nullable=True)
    notification_type = Column(String(50), nullable=False)  # 'reminder', 'overdue', 'custom'
    
    # Relationships
    task = relationship("Task", back_populates="notifications")
    
    def __repr__(self):
        return f"<Notification(id={self.id}, task_id={self.task_id}, status='{self.delivery_status}')>"


class TaskCompletionLog(Base):
    """Model for tracking task completion timeline and notification effectiveness."""
    
    __tablename__ = "task_completion_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    albiware_task_id = Column(Integer, nullable=False, index=True)
    task_name = Column(String(500), nullable=False)
    project_name = Column(String(500), nullable=False)
    due_date = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=False)
    days_to_complete = Column(Integer, nullable=True)
    was_overdue = Column(Boolean, default=False)
    days_overdue = Column(Integer, nullable=True)
    total_notifications_sent = Column(Integer, default=0)
    first_notification_sent_at = Column(DateTime, nullable=True)
    last_notification_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<TaskCompletionLog(id={self.id}, task='{self.task_name}', completed_at={self.completed_at})>"


class SystemLog(Base):
    """Model for tracking system events and errors."""
    
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(100), nullable=False)  # 'polling', 'notification', 'error', 'system'
    message = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)  # 'info', 'warning', 'error', 'critical'
    metadata = Column(Text, nullable=True)  # JSON string for additional data
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<SystemLog(id={self.id}, type='{self.event_type}', severity='{self.severity}')>"
