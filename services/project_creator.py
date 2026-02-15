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
            
            # Fill login form with human-like behavior
            page.click('#Email')  # Click to focus
            time.sleep(0.5)
            page.type('#Email', self.email, delay=100)  # Type slowly
            logger.info(f"Filled email: {self.email}")
            time.sleep(0.3)
            page.click('#password')  # Click to focus
            time.sleep(0.5)
            page.type('#password', self.password, delay=100)  # Type slowly
            logger.info("Filled password")
            time.sleep(1)  # Pause before clicking submit
            page.click('#btn-login')
            logger.info("Clicked login button")
            
            # Wait for navigation after login
            page.wait_for_load_state("networkidle", timeout=20000)
            logger.info(f"After login URL: {page.url}")
            
            # Wait a bit more for soft redirect to complete
            time.sleep(5)
            
            # Verify login was successful - check page title (Albiware does soft redirect)
            page_title = page.title()
            logger.info(f"Page title after login: {page_title}")
            if page_title.lower() == 'login':
                logger.error(f"Login failed - title still 'Login': {page.url}")
                # Check for error messages
                error_text = page.evaluate("document.querySelector('.alert-danger, .error')?.textContent || ''")
                if error_text:
                    logger.error(f"Login error message: {error_text}")
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
        """Fill out the project creation form using Kendo API"""
        try:
            logger.info(f"Filling project form for {contact.full_name}...")
            time.sleep(3)  # Wait for page initialization
            
            # STEP 1: Customer Option - Select "Add Existing" (Select2 dropdown)
            logger.info("STEP 1: Customer Option...")
            result = page.evaluate("""
                (function() {
                    try {
                        // CustomerOption is a Select2 dropdown
                        // Options: "" (Choose One), "existing" (Add Existing), "new" (Create New)
                        $('#CustomerOption').val('existing').trigger('change');
                        
                        // Verify it was set
                        var value = $('#CustomerOption').val();
                        return {success: true, value: value};
                    } catch(e) {
                        return {success: false, error: e.toString()};
                    }
                })()
            """)
            if not result.get('success'):
                raise Exception(f"CustomerOption selection failed: {result.get('error')}")
            logger.info(f"✓ Set to Add Existing (value: {result.get('value')})")
            time.sleep(2)
            
            # STEP 2: Select Customer
            logger.info(f"STEP 2: Selecting customer {contact.full_name}...")
            result = page.evaluate(f"""
                (function() {{
                    try {{
                        var $select = $('select[name="ProjectCustomer.ExistingOrganizationContactIds"]');
                        var option = new Option("{contact.full_name}", "{contact.albiware_contact_id}", true, true);
                        $select.append(option).trigger('change');
                        return {{success: true}};
                    }} catch(e) {{
                        return {{success: false, error: e.toString()}};
                    }}
                }})()
            """)
            if not result.get('success'):
                raise Exception(f"Customer selection failed: {result.get('error')}")
            time.sleep(2)
            logger.info("✓ Customer selected")
            
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
            # Verify the value persists
            verify_result = page.evaluate("$('#ProjectTypeId').data('kendoDropDownList')?.value()")
            logger.info(f"✓ Project Type set to: {result.get('text')} (Value: {result.get('value')}, Verified: {verify_result})")
            
            # STEP 4: Property Type (regular select)
            logger.info("STEP 4: Property Type...")
            prop_type = contact.property_type if contact.property_type else "Residential"
            # Map display name to value: "Residential" -> "residential", "Commercial" -> "commercial"
            prop_type_value = prop_type.lower()
            try:
                page.wait_for_selector('#PropertyType', state='visible', timeout=10000)
                page.select_option('#PropertyType', value=prop_type.lower(), timeout=10000)
                time.sleep(1)
                verify_prop = page.evaluate("$('#PropertyType').val()")
                logger.info(f"✓ Property Type: {prop_type} (Verified: {verify_prop})")
            except Exception as e:
                raise Exception(f"Property Type failed: {str(e)}")
            
            # STEP 5: Insurance Info (regular select - CoveredLoss)
            logger.info("STEP 5: Insurance Info...")
            has_ins = contact.has_insurance if contact.has_insurance is not None else False
            # Values are "True" and "False" (strings), not "Yes" and "No"
            ins_value = "True" if has_ins else "False"
            ins_label = "Yes" if has_ins else "No"
            try:
                page.wait_for_selector('#CoveredLoss', state='visible', timeout=10000)
                page.select_option('#CoveredLoss', value=str(has_ins), timeout=10000)
                time.sleep(1)
                verify_ins = page.evaluate("$('#CoveredLoss').val()")
                logger.info(f"✓ Insurance Info: {has_ins} (Verified: {verify_ins})")
            except Exception as e:
                raise Exception(f"Insurance Info failed: {str(e)}")
            
            # STEP 6: Insurance Company (if has insurance)
            if has_ins and contact.insurance_company:
                logger.info(f"STEP 6: Insurance Company...")
                page.fill('input#InsuranceCompany', contact.insurance_company)
                time.sleep(1)
                logger.info(f"✓ Insurance Company: {contact.insurance_company}")
            
            # STEP 7: Referrer Option - Add Existing (regular select)
            logger.info("STEP 7: Referrer Option...")
            try:
                page.wait_for_selector('#ReferrerOption', state='visible', timeout=10000)
                page.select_option('#ReferrerOption', label='Add Existing', timeout=10000)
                time.sleep(3)  # Wait for Referral Sources field to appear
                logger.info("✓ Referrer Option set")
            except Exception as e:
                raise Exception(f"Referrer Option failed: {str(e)}")
            
            # STEP 8: Referral Sources - Lead Gen (hidden select, use JavaScript)
            logger.info("STEP 8: Referral Sources...")
            try:
                # Field exists but is hidden, so use JavaScript to set value
                page.wait_for_selector('#ProjectReferrer_ReferralSourceId', state='attached', timeout=10000)
                result = page.evaluate("""
                    (function() {
                        try {
                            $('#ProjectReferrer_ReferralSourceId').val('28704').trigger('change');
                            return {success: true};
                        } catch(e) {
                            return {success: false, error: e.toString()};
                        }
                    })()
                """)
                if not result.get('success'):
                    raise Exception(f"JavaScript failed: {result.get('error')}")
                time.sleep(1)
                logger.info("✓ Referral Sources set to Lead Gen")
            except Exception as e:
                raise Exception(f"Referral Sources failed: {str(e)}")
            
            # STEP 9: Staff - Rodolfo Arceo (regular select)
            logger.info("STEP 9: Staff...")
            try:
                page.wait_for_selector('#StaffId', state='visible', timeout=10000)
                page.select_option('#StaffId', label='Rodolfo Arceo', timeout=10000)
                time.sleep(1)
                verify_staff = page.evaluate("$('#StaffId').val()")
                logger.info(f"✓ Staff set to Rodolfo Arceo (Verified: {verify_staff})")
                # Wait longer for Project Role options to dynamically load
                time.sleep(3)
            except Exception as e:
                raise Exception(f"Staff failed: {str(e)}")
            
            # STEP 10: Project Roles - Estimator (regular select)
            logger.info("STEP 10: Project Roles...")
            try:
                page.wait_for_selector('#ProjectRoleId', state='visible', timeout=10000)
                # Wait for options to be populated
                time.sleep(1)
                page.select_option('#ProjectRoleId', label='Estimator', timeout=10000)
                time.sleep(1)
                verify_role = page.evaluate("$('#ProjectRoleId').val()")
                logger.info(f"✓ Project Roles set to Estimator (Verified: {verify_role})")
                # Wait for all events to propagate before submit
                time.sleep(2)
            except Exception as e:
                raise Exception(f"Project Roles failed: {str(e)}")
            
            logger.info("✅ Form filling complete!")
            return True
            
        except Exception as e:
            logger.error(f"Form filling error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise Exception(f"Form filling failed: {str(e)}")


    def _submit_and_verify(self, page: Page, contact: Contact) -> Optional[int]:
        """Submit the form and verify project was created"""
        logger.info("========== _submit_and_verify CALLED ==========")
        logger.info(f"Contact: {contact.full_name} (ID: {contact.id})")
        try:
            # Wait for all events to settle before submitting
            logger.info("Waiting 3 seconds for all form events to settle...")
            time.sleep(3)
            
            logger.info("Submitting project form...")
            
            # Check all field values before submitting
            field_values = page.evaluate("""
                () => {
                    return {
                        CustomerOption: $('#CustomerOption').val(),
                        Customer: $('select[name="ProjectCustomer.ExistingOrganizationContactIds"]').val(),
                        ProjectType: $('#ProjectTypeId').data('kendoDropDownList')?.value(),
                        PropertyType: $('#PropertyType').val(),
                        CoveredLoss: $('#CoveredLoss').val(),
                        ReferrerOption: $('#ReferrerOption').val(),
                        ReferralSourceId: $('#ProjectReferrer_ReferralSourceId').val(),
                        Staff: $('#StaffId').val(),
                        ProjectRole: $('#ProjectRoleId').val()
                    };
                }
            """)
            logger.info(f"Field values before submit: {field_values}")
            
            # Check for validation errors before submitting
            validation_errors = page.evaluate("""
                () => {
                    const errors = document.querySelectorAll('.field-validation-error, .validation-summary-errors');
                    return Array.from(errors).map(e => e.textContent.trim()).filter(t => t);
                }
            """)
            if validation_errors:
                logger.error(f"Form has validation errors: {validation_errors}")
                return None
            
            # Get current URL before submit
            before_url = page.url
            logger.info(f"URL before submit: {before_url}")
            
            # Click the Create button using JavaScript (more reliable than Playwright click)
            logger.info("Clicking Create button...")
            # Wait for button to be ready
            page.wait_for_selector('input#SubmitButton[type="submit"]', state='visible', timeout=5000)
            # Use JavaScript click instead of Playwright click to ensure event handlers fire
            click_result = page.evaluate("""
                () => {
                    try {
                        const button = document.querySelector('input#SubmitButton[type="submit"]');
                        if (!button) return {success: false, error: 'Button not found'};
                        button.click();
                        return {success: true};
                    } catch(e) {
                        return {success: false, error: e.toString()};
                    }
                }
            """)
            if not click_result.get('success'):
                logger.error(f"Button click failed: {click_result.get('error')}")
                return None
            logger.info("Create button clicked successfully (via JavaScript)")
            
            # Wait for navigation (may redirect to project detail or project list)
            logger.info("Waiting for navigation...")
            logger.info(f"Current URL before wait: {page.url}")
            try:
                # Wait for URL to change from /Project/New
                logger.info("Calling wait_for_function...")
                page.wait_for_function("window.location.pathname !== '/Project/New'", timeout=30000)
                logger.info("wait_for_function completed")
                time.sleep(2)  # Wait for page to settle
                logger.info(f"URL after wait: {page.url}")
            except PlaywrightTimeout as timeout_err:
                after_url = page.url
                logger.error(f"PlaywrightTimeout: URL is still: {after_url}")
                # Check for error messages on the page
                error_msgs = page.evaluate("""
                    () => {
                        const errors = document.querySelectorAll('.alert-danger, .error, .field-validation-error');
                        return Array.from(errors).map(e => e.textContent.trim()).filter(t => t);
                    }
                """)
                if error_msgs:
                    logger.error(f"Error messages on page: {error_msgs}")
                return None
            except Exception as wait_err:
                logger.error(f"Exception during wait_for_function: {type(wait_err).__name__}: {wait_err}")
                import traceback
                logger.error(traceback.format_exc())
                return None
            
            # Extract project ID from URL
            current_url = page.url
            logger.info(f"Redirected to: {current_url}")
            logger.info(f"albiware_url: {self.albiware_url}")
            logger.info(f"Checking if current_url == '{self.albiware_url}/Project': {current_url == f'{self.albiware_url}/Project'}")
            logger.info(f"Checking if current_url.startswith('{self.albiware_url}/Project?'): {current_url.startswith(f'{self.albiware_url}/Project?')}")
            
            # Case 1: Redirected to project detail page (e.g., /Project/1617650)
            if '/Project/' in current_url and '/Project/New' not in current_url and current_url != f"{self.albiware_url}/Project":
                logger.info("Case 1: Project detail page detected")
                project_id_str = current_url.split('/Project/')[-1].split('?')[0].split('/')[0]
                try:
                    project_id = int(project_id_str)
                    logger.info(f"✅ Project created with ID: {project_id}")
                    return project_id
                except ValueError:
                    logger.error(f"Could not parse project ID from: {project_id_str}")
            
            # Case 2: Redirected to project list page (/Project)
            if current_url == f"{self.albiware_url}/Project" or current_url.startswith(f"{self.albiware_url}/Project?"):
                logger.info("Case 2: Project list page detected")
                logger.info("✅ Project created successfully (ID not captured)")
                return -1  # Use -1 to indicate success without ID
            
            logger.warning(f"Could not verify project creation from URL: {current_url}")
            logger.warning(f"URL did not match any expected patterns")
            return None
            
        except Exception as e:
            logger.error(f"Submit/verify error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
