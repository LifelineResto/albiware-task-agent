"""
Test script for validating the Albiware Task Agent system components.
Run this script to verify all services are working correctly.
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings
from services.albiware_client import AlbiwareClient
from services.sms_service import SMSService
from database.database import Database
from database.models import Task, Notification


def test_albiware_connection():
    """Test connection to Albiware API."""
    print("\n=== Testing Albiware API Connection ===")
    try:
        client = AlbiwareClient(settings.albiware_api_key, settings.albiware_base_url)
        projects = client.get_all_projects(open_only=True, page_size=5)
        
        if projects:
            print(f"✅ Successfully connected to Albiware API")
            print(f"   Retrieved {len(projects)} projects")
            if projects:
                print(f"   First project: {projects[0].get('name', 'N/A')}")
            return True
        else:
            print("⚠️  Connected but no projects found")
            return True
    except Exception as e:
        print(f"❌ Failed to connect to Albiware API: {e}")
        return False


def test_twilio_connection():
    """Test connection to Twilio API."""
    print("\n=== Testing Twilio API Connection ===")
    try:
        sms_service = SMSService(
            settings.twilio_account_sid,
            settings.twilio_auth_token,
            settings.twilio_from_number
        )
        
        # Try to get account info (validates credentials)
        account = sms_service.client.api.accounts(settings.twilio_account_sid).fetch()
        
        print(f"✅ Successfully connected to Twilio API")
        print(f"   Account Status: {account.status}")
        print(f"   From Number: {settings.twilio_from_number}")
        return True
    except Exception as e:
        print(f"❌ Failed to connect to Twilio API: {e}")
        return False


def test_database_connection():
    """Test database connection and table creation."""
    print("\n=== Testing Database Connection ===")
    try:
        db = Database(settings.database_url)
        
        # Try to create tables
        db.create_tables()
        print(f"✅ Successfully connected to database")
        print(f"   Database URL: {settings.database_url[:30]}...")
        
        # Test session
        session_gen = db.get_session()
        session = next(session_gen)
        
        # Try a simple query
        task_count = session.query(Task).count()
        print(f"   Current tasks in database: {task_count}")
        
        session.close()
        return True
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return False


def test_sms_format():
    """Test SMS date/time formatting."""
    print("\n=== Testing SMS Date/Time Formatting ===")
    try:
        test_date = datetime(2026, 2, 15, 14, 30, 0)
        formatted = test_date.strftime("%m/%d/%Y %I:%M %p").replace(" 0", " ").lower()
        
        expected = "02/15/2026 2:30 p.m."
        
        if formatted == expected:
            print(f"✅ SMS date formatting is correct")
            print(f"   Format: {formatted}")
            return True
        else:
            print(f"❌ SMS date formatting is incorrect")
            print(f"   Expected: {expected}")
            print(f"   Got: {formatted}")
            return False
    except Exception as e:
        print(f"❌ Failed to test SMS formatting: {e}")
        return False


def test_configuration():
    """Test configuration settings."""
    print("\n=== Testing Configuration ===")
    
    required_settings = [
        ('albiware_api_key', settings.albiware_api_key),
        ('twilio_account_sid', settings.twilio_account_sid),
        ('twilio_auth_token', settings.twilio_auth_token),
        ('twilio_from_number', settings.twilio_from_number),
        ('database_url', settings.database_url),
    ]
    
    all_configured = True
    
    for name, value in required_settings:
        if not value or value == "your_" in value:
            print(f"❌ {name} is not configured")
            all_configured = False
        else:
            print(f"✅ {name} is configured")
    
    print(f"\nOptional Settings:")
    print(f"   Polling Interval: {settings.polling_interval_minutes} minutes")
    print(f"   Reminder Hours Before Due: {settings.reminder_hours_before_due} hours")
    print(f"   Max Reminders Per Task: {settings.max_reminders_per_task}")
    print(f"   Staff Phone Numbers: {settings.staff_phone_numbers or 'Not configured'}")
    
    return all_configured


def run_all_tests():
    """Run all system tests."""
    print("=" * 60)
    print("Albiware Task Agent - System Validation Tests")
    print("=" * 60)
    
    results = {
        "Configuration": test_configuration(),
        "SMS Formatting": test_sms_format(),
        "Database Connection": test_database_connection(),
        "Albiware API": test_albiware_connection(),
        "Twilio API": test_twilio_connection(),
    }
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:.<40} {status}")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    print("\n" + "=" * 60)
    print(f"Total: {passed_tests}/{total_tests} tests passed")
    print("=" * 60)
    
    if passed_tests == total_tests:
        print("\n🎉 All tests passed! System is ready to deploy.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
