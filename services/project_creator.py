"""
Automated Project Creator - FIXED VERSION
Uses browser automation to create projects in Albiware when API is not available

CRITICAL FIX: Properly handles Kendo dropdown widgets by simulating user interaction
instead of just setting values via jQuery
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
                        page_url = page.url
                        page_title = page.title()
                        raise Exception(f"Could not log in to Albiware. Current URL: {page_url}, Title: {page_title}")
                    
                    # Navigate to project creation
                    if not self._navigate_to_create_project(page):
                        raise Exception("Could not navigate to project creation")
                    
                    # Fill project form
                    self._fill_project_form(page, contact)
                    logger.info("Form filled successfully")
                    
                    # Submit and verify
                    project_id = self._submit_and_verify(page, contact)
                    
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
                        screenshot_path = f"/tmp/albiware_error_{int(time.time())}.png"
                        page.screenshot(path=screenshot_path)
                        logger.info(f"Screenshot saved to {screenshot_path}")
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
            logger.error(f"Playwright initialization error: {e}")
            log.status = 'failed'
            log.error_message = str(e)
            log.completed_at = datetime.utcnow()
            db.commit()
            return False
    
    def _login(self, page: Page) -> bool:
        """Login to Albiware"""
        try:
            logger.info("Logging in to Albiware...")
            page.goto(f"{self.albiware_url}/Login", wait_until="domcontentloaded", timeout=30000)
            
            # Wait for login form
            page.wait_for_selector('input#Email', timeout=15000)
            
            # Fill login form
            page.fill('input#Email', self.email)
            page.fill('input#password', self.password)
            
            # Click login button
            page.click('button[type="submit"]')
            
            # Wait for redirect to dashboard
            page.wait_for_url("**/TaskDashboard", timeout=30000)
            logger.info("Login successful")
            
            return True
            
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False
    
    def _navigate_to_create_project(self, page: Page) -> bool:
        """Navigate to the project creation page"""
        try:
            logger.info("Navigating to project creation...")
            page.goto(f"{self.albiware_url}/Project/New", wait_until="domcontentloaded", timeout=30000)
            logger.info(f"Loaded URL: {page.url}")
            logger.info(f"Page title: {page.title()}")
            
            # Wait for form to load
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
        """
        Fill out the project creation form
        
        CRITICAL FIX: Uses keyboard navigation and Enter key to properly select
        dropdown options instead of just setting values via jQuery
        """
        try:
            logger.info(f"Filling project form for {contact.full_name}...")
            time.sleep(3)  # Wait for page initialization
            
            # STEP 1: Customer Option - Select "Add Existing"
            logger.info("STEP 1: Customer Option...")
            page.select_option('#CustomerOption', label='Add Existing')
            time.sleep(2)
            logger.info("✓ Set to Add Existing")
            
            # STEP 2: Select Customer - CRITICAL FIX
            # Must click dropdown, type name, and press Enter to properly select
            logger.info(f"STEP 2: Selecting customer {contact.full_name}...")
            
            # Click on the customer dropdown to open it
            page.click('span[role="listbox"]:has-text("Choose One")')
            time.sleep(1)
            
            # Type the customer name in the search box
            search_input = page.locator('#ExistingOrganizationId-list input[role="listbox"]')
            search_input.fill(contact.full_name)
            time.sleep(1)
            
            # Press Arrow Down to highlight the first result
            page.keyboard.press('ArrowDown')
            time.sleep(0.5)
            
            # Press Enter to select
            page.keyboard.press('Enter')
            time.sleep(2)
            
            # Verify the customer was selected
            result = page.evaluate("""
                (function() {
                    var value = $('#ExistingOrganizationId').val();
                    return {value: value, success: !!value};
                })()
            """)
            if not result.get('success'):
                raise Exception(f"Customer selection failed - ExistingOrganizationId is empty")
            logger.info(f"✓ Customer selected (ID: {result.get('value')})")
            
            # STEP 3: Project Type - EMS
            logger.info("STEP 3: Project Type...")
            result = page.evaluate("""
                (function() {
                    try {
                        var widget = $('#ProjectTypeId').data('kendoDropDownList');
                        if (!widget) return {success: false, error: 'Widget not found'};
                        var data = widget.dataSource.data();
                        var emsOption = data.find(item => item.Text && item.Text.includes('Emergency Mitigation'));
                        if (emsOption) {
                            widget.value(emsOption.Value);
                            widget.trigger('change');
                            return {success: true, value: emsOption.Value, text: emsOption.Text};
                        }
                        return {success: false, error: 'EMS option not found'};
                    } catch(e) {
                        return {success: false, error: e.toString()};
                    }
                })()
            """)
            if not result.get('success'):
                raise Exception(f"Project Type failed: {result.get('error')}")
            time.sleep(1)
            logger.info(f"✓ Project Type set to: {result.get('text')}")
            
            # STEP 4: Property Type
            logger.info("STEP 4: Property Type...")
            prop_type = contact.property_type if contact.property_type else "Residential"
            page.select_option('#PropertyType', value=prop_type.lower())
            time.sleep(1)
            logger.info(f"✓ Property Type: {prop_type}")
            
            # STEP 5: Insurance Info
            logger.info("STEP 5: Insurance Info...")
            has_ins = contact.has_insurance if contact.has_insurance is not None else False
            page.select_option('#CoveredLoss', value=str(has_ins))
            time.sleep(1)
            logger.info(f"✓ Insurance Info: {'Yes' if has_ins else 'No'}")
            
            # STEP 6: Referrer Option - Add Existing
            logger.info("STEP 6: Referrer Option...")
            page.select_option('#ReferrerOption', label='Add Existing')
            time.sleep(2)  # Wait for Referral Sources field to appear
            logger.info("✓ Referrer Option set")
            
            # STEP 7: Referral Sources - CRITICAL FIX
            # Must click dropdown and select an option using keyboard
            logger.info("STEP 7: Referral Sources...")
            
            # Use JavaScript to select the first option from Referral Sources dropdown
            result = page.evaluate("""
                (function() {
                    try {
                        var widget = $('#ReferralSources').data('kendoDropDownList');
                        if (!widget) return {success: false, error: 'Widget not found'};
                        var data = widget.dataSource.data();
                        if (data && data.length > 0) {
                            var firstOption = data[0];
                            widget.value(firstOption.Value);
                            widget.trigger('change');
                            return {success: true, value: firstOption.Value, text: firstOption.Text};
                        }
                        return {success: false, error: 'No options available'};
                    } catch(e) {
                        return {success: false, error: e.toString()};
                    }
                })()
            """)
            if not result.get('success'):
                raise Exception(f"Referral Sources selection failed: {result.get('error')}")
            time.sleep(1)
            
            # Verify
            result = page.evaluate("""
                (function() {
                    var value = $('#ReferralSources').val();
                    return {value: value, success: !!value};
                })()
            """)
            if not result.get('success'):
                raise Exception(f"Referral Sources selection failed")
            logger.info(f"✓ Referral Sources selected (ID: {result.get('value')})")
            
            # STEP 8: Staff - Rodolfo Arceo
            logger.info("STEP 8: Staff...")
            page.select_option('#StaffId', label='Rodolfo Arceo')
            time.sleep(2)  # Wait for Project Role options to load
            logger.info("✓ Staff set to Rodolfo Arceo")
            
            # STEP 9: Project Role - Estimator - CRITICAL FIX
            # Field is #ProjectRoleId (singular, not plural!)
            logger.info("STEP 9: Project Role...")
            page.select_option('#ProjectRoleId', label='Estimator')
            time.sleep(1)
            
            # Verify
            result = page.evaluate("""
                (function() {
                    var value = $('#ProjectRoleId').val();
                    return {value: value, success: !!value};
                })()
            """)
            if not result.get('success'):
                raise Exception(f"Project Role selection failed")
            logger.info(f"✓ Project Role set to Estimator (ID: {result.get('value')})")
            
            # Wait for all events to propagate
            time.sleep(2)
            
            logger.info("✅ Form filling complete!")
            return True
            
        except Exception as e:
            logger.error(f"Form filling error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def _submit_and_verify(self, page: Page, contact: Contact) -> Optional[str]:
        """Submit the form and verify project creation"""
        try:
            logger.info("Submitting form...")
            
            # Click the Create button
            page.click('input#SubmitButton[type="submit"]')
            
            # Wait for redirect to project page
            # URL pattern: https://app.albiware.com/Project/{project_id}
            page.wait_for_url("**/Project/**", timeout=30000)
            
            # Extract project ID from URL
            current_url = page.url
            logger.info(f"Redirected to: {current_url}")
            
            # Parse project ID from URL
            if "/Project/" in current_url:
                parts = current_url.split("/Project/")
                if len(parts) > 1:
                    project_id = parts[1].split("?")[0].split("#")[0]
                    logger.info(f"✅ Project created successfully! ID: {project_id}")
                    return project_id
            
            raise Exception(f"Could not extract project ID from URL: {current_url}")
            
        except Exception as e:
            logger.error(f"Submit/verify error: {e}")
            logger.error(f"Current URL: {page.url}")
            
            # Check for validation errors
            try:
                errors = page.locator('.field-validation-error, .validation-summary-errors').all_text_contents()
                if errors:
                    logger.error(f"Validation errors: {errors}")
            except:
                pass
            
            return None
