"""
Database Migration: Add Project Detail Fields
Adds fields to Contact table for storing project details collected via SMS
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Add project detail columns to contacts table"""
    
    database_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/albiware_tracking")
    engine = create_engine(database_url)
    
    migrations = [
        # Add project detail fields
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS project_type VARCHAR(100)",
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS property_type VARCHAR(50)",
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS has_insurance BOOLEAN",
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS insurance_company VARCHAR(200)",
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS referral_source VARCHAR(100)",
    ]
    
    try:
        with engine.connect() as conn:
            for migration_sql in migrations:
                logger.info(f"Running: {migration_sql}")
                conn.execute(text(migration_sql))
                conn.commit()
        
        logger.info("✅ Migration completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
