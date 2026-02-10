"""
Configuration settings for the Albiware Task Agent system.
All sensitive credentials are loaded from environment variables.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Albiware API Configuration
    albiware_api_key: str
    albiware_base_url: str = "https://api.albiware.com/v5"
    
    # Twilio Configuration
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str
    
    # Database Configuration
    database_url: str = "postgresql://user:password@localhost:5432/albiware_tracking"
    
    # Polling Configuration
    polling_interval_minutes: int = 15
    
    # Notification Configuration
    reminder_hours_before_due: int = 24
    max_reminders_per_task: int = 5
    
    # Staff Phone Numbers (comma-separated)
    staff_phone_numbers: str = ""
    
    # Railway Configuration
    railway_token: Optional[str] = None
    port: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
