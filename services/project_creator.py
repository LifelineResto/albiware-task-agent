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
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                
                try:
                    # Login
                    login_result = self._login(page)
                    if not login_result:
                        # Get page content for debugging
                        page_url = page.url
                        page_title = page.title()
                        raise Exception(f"Could not log in to Albiware. Current URL: {page_url}, Title: {page_title}")
                    
                    # Navigate to project creation
                    if not self._navigate_to_create_project(page):
                        raise Exception("Could not navigate to project creation")
                    
                    # Fill project form (will raise exception if it fails)
                    self._fill_project_form(page, contact)
                    logger.info("Form filled successfully")
                    
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
                    import traceback
                    error_details = traceback.format_exc()
                    logger.error(f"Error during browser automation: {e}")
                    logger.error(f"Full traceback:\n{error_details}")
                    
                    # Take screenshot for debugging
                    try:
                        screenshot_path = f"/tmp/albiware_error_{contact.id}_{int(time.time())}.png"
                        page.screenshot(path=screenshot_path)
                        log.screenshot_path = screenshot_path
                    except:
                        pass
                    
                    log.status = 'failed'
                    log.error_message = f"{str(e)}\n\nTraceback:\n{error_details}"
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
    
    def process_pending_projects(self, db: Session) -> int:
        """
        Process all contacts that need project creation
        
        Returns:
            Number of projects successfully created
        """
        # Find contacts that need project creation
        contacts = db.query(Contact).filter(
            Contact.project_creation_needed == True,
            Contact.project_created == False
        ).all()
        
        logger.info(f"Found {len(contacts)} contacts needing project creation")
        
        created_count = 0
        for contact in contacts:
            logger.info(f"Processing contact: {contact.full_name}")
            if self.create_project_for_contact(db, contact):
                created_count += 1
        
        return created_count
    
    def _login(self, page: Page) -> bool:
        """Log in to Albiware"""
        try:
            logger.info("Logging in to Albiware...")
            page.goto(f"{self.albiware_url}/login", wait_until="domcontentloaded", timeout=30000)
            logger.info(f"Loaded page: {page.url}")
            
            # Wait for login form
            page.wait_for_selector('#Email', timeout=10000)
            logger.info("Found email field")
            
            # Fill login form
            page.fill('#Email', self.email)
            logger.info(f"Filled email: {self.email}")
            page.fill('#password', self.password)
            logger.info("Filled password")
            page.click('#btn-login')
            logger.info("Clicked login button")
            
            # Wait for navigation after login
            page.wait_for_load_state("networkidle", timeout=15000)
            logger.info(f"After login URL: {page.url}")
            
            # Verify login was successful - check page title (Albiware does soft redirect)
            page_title = page.title()
            if page_title.lower() == 'login':
                logger.error(f"Login failed - title still 'Login': {page.url}")
                return False
            
            logger.info("Login successful")
            return True
            
        except Exception as e:
            logger.error(f"Login error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _navigate_to_create_project(self, page: Page) -> bool:
        """Navigate to the project creation page"""
        try:
            logger.info("Navigating to project creation...")
            page.goto(f"{self.albiware_url}/Project/New", wait_until="domcontentloaded", timeout=30000)
            logger.info(f"Loaded URL: {page.url}")
            logger.info(f"Page title: {page.title()}")
            
            # Wait for form to load - check for key form elements
            logger.info("Waiting for CustomerOption selector...")
            page.wait_for_selector('select#CustomerOption', timeout=15000)
            logger.info("Project creation form loaded")
            
            # Wait for page to fully initialize (jQuery, Kendo widgets, etc.)
            time.sleep(3)
            
            return True
            
        except Exception as e:
            logger.error(f"Navigation error: {e}")
            logger.error(f"Current URL: {page.url}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _fill_project_form(self, page: Page, contact: Contact) -> bool:
        """Fill out the project creation form - simplified approach using direct selectors"""
        try:
            logger.info(f"Filling project form for {contact.full_name}...")
            
            # STEP 1: Customer - Select "Add Existing" then customer
            logger.info("STEP 1: Customer Information...")
            page.wait_for_selector('select#CustomerOption', state='visible', timeout=10000)
            # Wait for element to be enabled (Kendo initialization)
            page.wait_for_function("document.querySelector('select#CustomerOption') && !document.querySelector('select#CustomerOption').disabled", timeout=10000)
            page.locator('select#CustomerOption').select_option('AddExisting')
            time.sleep(3)
            
            # Set customer using Select2
            result = page.evaluate(f"""
                (function() {{
                    const sel = document.querySelector('select[name="ProjectCustomer.ExistingOrganizationContactIds"]');
                    if (!sel || !window.jQuery) return {{success: false}};
                    const $s = jQuery(sel);
                    const id = '{contact.albiware_contact_id}';
                    const name = '{contact.full_name}';
                    if ($s.find(`option[value="${{id}}"]`).length === 0) {{
                        $s.append(new Option(name, id, true, true));
                    }} else {{
                        $s.val(id);
                    }}
                    $s.trigger('change.select2').trigger('change');
                    return {{success: true}};
                }})()
            """)
            if not result.get('success'):
                raise Exception("Customer selection failed")
            logger.info("✓ Customer selected")
            time.sleep(2)
            
            # STEP 2: Project Type - EMS
            logger.info("STEP 2: Project Type...")
            page.locator('select#ProjectTypeId').select_option(label='Emergency Mitigation Services (EMS)')
            logger.info("✓ Project Type: EMS")
            time.sleep(1)
            
            # STEP 3: Property Type
            logger.info("STEP 3: Property Type...")
            prop_type = contact.property_type if contact.property_type else "Residential"
            page.locator('select#PropertyType').select_option(label=prop_type)
            logger.info(f"✓ Property Type: {prop_type}")
            time.sleep(1)
            
            # STEP 4: Insurance
            logger.info("STEP 4: Insurance...")
            has_ins = contact.has_insurance if contact.has_insurance is not None else False
            page.locator('select#InsuranceInfo').select_option(label="Yes" if has_ins else "No")
            time.sleep(2)
            if has_ins:
                ins_co = contact.insurance_company if contact.insurance_company else "N/A"
                page.locator('input#InsuranceCompany').fill(ins_co)
                logger.info(f"✓ Insurance: Yes - {ins_co}")
            else:
                logger.info("✓ Insurance: No")
            time.sleep(1)
            
            # STEP 5: Referrer Option - Add Existing (skip if not found)
            logger.info("STEP 5: Referrer Option...")
            try:
                # This might not exist or might be in a different location
                page.locator('select').filter(has_text="Add Existing").nth(1).select_option('AddExisting')
                logger.info("✓ Referrer Option: Add Existing")
            except:
                logger.info("⚠ Referrer Option not found (skipping)")
            time.sleep(1)
            
            # STEP 6: Referral Sources - Lead Gen
            logger.info("STEP 6: Referral Sources...")
            ref_source = contact.referral_source if contact.referral_source else "Lead Gen"
            page.locator('select#ReferralSourceId').select_option(label=ref_source)
            logger.info(f"✓ Referral Source: {ref_source}")
            time.sleep(1)
            
            # STEP 7: Staff - Rodolfo Arceo
            logger.info("STEP 7: Staff...")
            page.locator('select#StaffId').select_option(label='Rodolfo Arceo')
            logger.info("✓ Staff: Rodolfo Arceo")
            time.sleep(1)
            
            # STEP 8: Project Roles - Estimator
            logger.info("STEP 8: Project Roles...")
            try:
                # Try clicking the multi-select input and selecting Estimator
                page.locator('input[placeholder=""]').last.click()
                time.sleep(0.5)
                page.locator('li:has-text("Estimator")').first.click()
                logger.info("✓ Project Role: Estimator")
            except:
                logger.warning("⚠ Could not set Project Role")
            time.sleep(1)
            
            logger.info("✅ Form filled successfully")
            return True
            
        except Exception as e:
            logger.error(f"Form filling error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def _submit_and_verify(self, page: Page) -> Optional[int]:
        """Submit the form and verify project was created"""
        try:
            logger.info("Submitting project form...")
            
            # Click the Create button
            page.click('button:has-text("Create"), input[value="Create"]')
            
            # Wait for navigation (project creation redirects to project detail page)
            page.wait_for_url("**/Project/*", timeout=30000)
            
            # Extract project ID from URL
            current_url = page.url
            logger.info(f"Redirected to: {current_url}")
            
            # URL format: https://app.albiware.com/Project/1617650?tab=BasicInfo
            if '/Project/' in current_url and '/Project/New' not in current_url:
                project_id_str = current_url.split('/Project/')[-1].split('?')[0].split('/')[0]
                try:
                    project_id = int(project_id_str)
                    logger.info(f"✅ Project created with ID: {project_id}")
                    return project_id
                except ValueError:
                    logger.error(f"Could not parse project ID from: {project_id_str}")
                    return None
            
            logger.warning("Could not extract project ID from URL")
            return None
            
        except PlaywrightTimeout:
            logger.error("Timeout waiting for project creation")
            return None
        except Exception as e:
            logger.error(f"Submit/verify error: {e}")
            return None
