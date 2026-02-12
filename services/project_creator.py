"""
Automated Project Creator
Uses browser automation to create projects in Albiware when API is not available
"""

import logging
import time
from datetime import datetime
from typing import Optional, Dict
from sqlalchemy.orm import Session
from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError as PlaywrightTimeout

from database.enhanced_models import Contact, ProjectCreationLog

logger = logging.getLogger(__name__)


class AlbiwareProjectCreator:
    """Automates project creation in Albiware using browser automation"""
    
    def __init__(self, albiware_email: str, albiware_password: str):
        """
        Initialize the project creator
        
        Args:
            albiware_email: Albiware login email
            albiware_password: Albiware login password
        """
        self.email = albiware_email
        self.password = albiware_password
        self.albiware_url = "https://app.albiware.com"
    
    def create_project_for_contact(self, db: Session, contact: Contact) -> bool:
        """
        Create a project in Albiware for the given contact
        
        Args:
            db: Database session
            contact: Contact object to create project for
            
        Returns:
            True if project created successfully
        """
        log = ProjectCreationLog(
            contact_id=contact.id,
            status='pending',
            started_at=datetime.utcnow()
        )
        db.add(log)
        db.flush()
        
        try:
            logger.info(f"Starting project creation for contact: {contact.full_name}")
            log.status = 'in_progress'
            db.commit()
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                
                try:
                    # Login to Albiware
                    if not self._login(page, log, db):
                        raise Exception("Login failed")
                    
                    # Navigate to project creation
                    if not self._navigate_to_create_project(page):
                        raise Exception("Could not navigate to project creation")
                    
                    # Fill project form
                    if not self._fill_project_form(page, contact):
                        raise Exception("Could not fill project form")
                    
                    # Submit and verify
                    project_id = self._submit_and_verify(page)
                    
                    if project_id:
                        # Success!
                        log.status = 'success'
                        log.albiware_project_id = project_id
                        log.completed_at = datetime.utcnow()
                        
                        contact.project_created = True
                        contact.albiware_project_id = project_id
                        contact.project_created_at = datetime.utcnow()
                        
                        db.commit()
                        logger.info(f"Successfully created project {project_id} for {contact.full_name}")
                        return True
                    else:
                        raise Exception("Could not verify project creation")
                
                except Exception as e:
                    logger.error(f"Error during browser automation: {e}")
                    
                    # Take screenshot for debugging
                    try:
                        screenshot_path = f"/tmp/albiware_error_{contact.id}_{int(time.time())}.png"
                        page.screenshot(path=screenshot_path)
                        log.screenshot_path = screenshot_path
                    except:
                        pass
                    
                    log.status = 'failed'
                    log.error_message = str(e)
                    log.completed_at = datetime.utcnow()
                    db.commit()
                    return False
                
                finally:
                    browser.close()
        
        except Exception as e:
            logger.error(f"Fatal error in project creation: {e}")
            log.status = 'failed'
            log.error_message = str(e)
            log.completed_at = datetime.utcnow()
            db.commit()
            return False
    
    def _login(self, page: Page, log: ProjectCreationLog, db: Session) -> bool:
        """Login to Albiware"""
        try:
            logger.info("Logging into Albiware...")
            page.goto(f"{self.albiware_url}/login", wait_until="domcontentloaded", timeout=60000)
            logger.info(f"Loaded login page: {page.url}")
            
            # Wait for login form to be visible
            page.wait_for_selector('#Email', timeout=30000)
            logger.info("Login form found")
            
            # Fill login form
            page.fill('#Email', self.email)
            logger.info(f"Filled email: {self.email}")
            
            page.fill('#password', self.password)
            logger.info("Filled password")
            
            # Click login button
            page.click('#btn-login')
            logger.info("Clicked login button")
            
            # Wait for navigation to complete (Albiware redirects to TaskDashboard)
            page.wait_for_load_state("networkidle", timeout=10000)
            
            logger.info("Successfully logged in to Albiware")
            return True
            
        except PlaywrightTimeout:
            logger.error("Login timeout - check credentials or Albiware availability")
            return False
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False
    
    def _navigate_to_create_project(self, page: Page) -> bool:
        """Navigate to the project creation page"""
        try:
            logger.info("Navigating to project creation...")
            
            # Click on Projects menu
            page.click('text=Projects')
            time.sleep(1)
            
            # Click Create New Project button
            page.click('button:has-text("Create New")')
            
            # Wait for form to load
            page.wait_for_selector('form', timeout=10000)
            
            logger.info("Project creation form loaded")
            return True
            
        except Exception as e:
            logger.error(f"Navigation error: {e}")
            return False
    
    def _fill_project_form(self, page: Page, contact: Contact) -> bool:
        """Fill out the project creation form"""
        try:
            logger.info(f"Filling project form for {contact.full_name}...")
            
            # Customer name
            if contact.full_name:
                page.fill('input[name="customerName"]', contact.full_name)
            
            # Phone number
            if contact.phone_number:
                page.fill('input[name="phoneNumber"]', contact.phone_number)
            
            # Email
            if contact.email:
                page.fill('input[name="email"]', contact.email)
            
            # Address (if available)
            if contact.address:
                page.fill('input[name="address"]', contact.address)
            
            # Project type - set to "Restoration" or similar default
            try:
                page.select_option('select[name="projectType"]', label="Restoration")
            except:
                logger.warning("Could not set project type")
            
            # Notes - add context about automated creation
            notes = f"Project created automatically via AI agent. Contact outcome: Appointment Set. Created: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
            try:
                page.fill('textarea[name="notes"]', notes)
            except:
                logger.warning("Could not add notes")
            
            logger.info("Project form filled successfully")
            return True
            
        except Exception as e:
            logger.error(f"Form filling error: {e}")
            return False
    
    def _submit_and_verify(self, page: Page) -> Optional[int]:
        """Submit the form and verify project was created"""
        try:
            logger.info("Submitting project form...")
            
            # Click submit/save button
            page.click('button:has-text("Save"), button:has-text("Create")')
            
            # Wait for success indication or redirect
            time.sleep(3)
            
            # Try to extract project ID from URL or page
            current_url = page.url
            
            # Albiware typically redirects to /projects/{id} after creation
            if '/projects/' in current_url:
                project_id_str = current_url.split('/projects/')[-1].split('/')[0].split('?')[0]
                try:
                    project_id = int(project_id_str)
                    logger.info(f"Project created with ID: {project_id}")
                    return project_id
                except:
                    pass
            
            # Alternative: look for success message
            if page.locator('text=successfully created').count() > 0:
                logger.info("Project created successfully (no ID extracted)")
                return -1  # Indicate success but no ID
            
            logger.warning("Could not verify project creation")
            return None
            
        except Exception as e:
            logger.error(f"Submit/verify error: {e}")
            return None
    
    def process_pending_projects(self, db: Session) -> int:
        """
        Process all contacts that need project creation
        
        Returns:
            Number of projects created
        """
        try:
            # Find contacts that need project creation
            contacts = db.query(Contact).filter(
                Contact.project_creation_needed == True,
                Contact.project_created == False
            ).all()
            
            if not contacts:
                logger.info("No pending project creations")
                return 0
            
            logger.info(f"Found {len(contacts)} contacts needing project creation")
            
            created_count = 0
            for contact in contacts:
                try:
                    if self.create_project_for_contact(db, contact):
                        created_count += 1
                        # Add delay between creations to avoid rate limiting
                        time.sleep(5)
                except Exception as e:
                    logger.error(f"Error creating project for contact {contact.id}: {e}")
                    continue
            
            logger.info(f"Created {created_count} projects")
            return created_count
            
        except Exception as e:
            logger.error(f"Error processing pending projects: {e}")
            return 0
