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
            
            # Wait a bit more for soft redirect to complete
            time.sleep(3)
            
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
    
    def _fill_project_form(self, page: Page, contact: Contact):        """Fill the project creation form"""        try:            logger.info("Starting form fill...")            time.sleep(3)  # Wait for page to fully load                        # STEP 1: Customer Option - Select "Add Existing" using Select2            logger.info("STEP 1: Customer Option - Add Existing...")            page.evaluate("""                $('#CustomerOption').val('AddExisting').trigger('change');            """)            time.sleep(2)            logger.info("✓ Customer Option set to Add Existing")                        # STEP 2: Select Customer using Select2            logger.info(f"STEP 2: Selecting customer {contact.full_name} (ID: {contact.albiware_contact_id})...")            result = page.evaluate(f"""                (function() {{                    try {{                        // Find the Select2 for customer selection                        var $select = $('select[name="ProjectCustomer.ExistingOrganizationContactIds"]');                                                // Create option with contact ID and name                        var option = new Option("{contact.full_name}", "{contact.albiware_contact_id}", true, true);                        $select.append(option).trigger('change');                                                return {{success: true}};                    }} catch(e) {{                        return {{success: false, error: e.toString()}};                    }}                }})()            """)            if not result.get('success'):                raise Exception(f"Customer selection failed: {result.get('error')}")            time.sleep(2)            logger.info("✓ Customer selected")                        # STEP 3: Project Type - Use Kendo API            logger.info("STEP 3: Project Type - Emergency Mitigation Services (EMS)...")            project_type_value = "Emergency Mitigation Services (EMS)"            result = page.evaluate(f"""                (function() {{                    try {{                        // Find the Kendo DropDownList for Project Type                        var dropdown = $('[aria-labelledby="ProjectTypeId_label"]').data('kendoDropDownList');                        if (!dropdown) {{                            return {{success: false, error: 'Kendo dropdown not found'}};                        }}                                                // Select by text                        dropdown.select(function(dataItem) {{                            return dataItem.text === "{project_type_value}";                        }});                        dropdown.trigger('change');                                                return {{success: true}};                    }} catch(e) {{                        return {{success: false, error: e.toString()}};                    }}                }})()            """)            if not result.get('success'):                raise Exception(f"Project Type selection failed: {result.get('error')}")            time.sleep(1)            logger.info("✓ Project Type set")                        # STEP 4: Property Type - Use select element directly            logger.info(f"STEP 4: Property Type - {contact.property_type}...")            page.evaluate(f"""                $('#PropertyType').val('{contact.property_type}').trigger('change');            """)            time.sleep(1)            logger.info("✓ Property Type set")                        # STEP 5: Insurance Info            logger.info(f"STEP 5: Insurance Info - {'Yes' if contact.has_insurance else 'No'}...")            insurance_value = 'Yes' if contact.has_insurance else 'No'            result = page.evaluate(f"""                (function() {{                    try {{                        // Find Insurance Info Kendo dropdown                        var dropdown = $('[aria-label*="Insurance"]').closest('.form-group').find('[role="listbox"]').data('kendoDropDownList');                        if (!dropdown) {{                            // Try alternative selector                            dropdown = $('select[name*="Insurance"]').data('kendoDropDownList');                        }}                        if (!dropdown) {{                            return {{success: false, error: 'Insurance dropdown not found'}};                        }}                                                dropdown.select(function(dataItem) {{                            return dataItem.text === "{insurance_value}";                        }});                        dropdown.trigger('change');                                                return {{success: true}};                    }} catch(e) {{                        return {{success: false, error: e.toString()}};                    }}                }})()            """)            if not result.get('success'):                raise Exception(f"Insurance Info selection failed: {result.get('error')}")            time.sleep(1)            logger.info("✓ Insurance Info set")                        # STEP 6: Insurance Company (if has insurance)            if contact.has_insurance and contact.insurance_company:                logger.info(f"STEP 6: Insurance Company - {contact.insurance_company}...")                page.fill('input[name*="InsuranceCompany"]', contact.insurance_company)                time.sleep(1)                logger.info("✓ Insurance Company set")                        # STEP 7: Referrer Option - Add Existing            logger.info("STEP 7: Referrer Option - Add Existing...")            result = page.evaluate("""                (function() {                    try {                        // Find Referrer Option dropdown in Referrer Information section                        var dropdown = $('#ReferrerInformation').find('[role="listbox"]').first().data('kendoDropDownList');                        if (!dropdown) {                            return {success: false, error: 'Referrer Option dropdown not found'};                        }                                                dropdown.select(function(dataItem) {                            return dataItem.text === "Add Existing";                        });                        dropdown.trigger('change');                                                return {success: true};                    } catch(e) {                        return {success: false, error: e.toString()};                    }                })()            """)            if not result.get('success'):                raise Exception(f"Referrer Option selection failed: {result.get('error')}")            time.sleep(1)            logger.info("✓ Referrer Option set")                        # STEP 8: Referral Sources - Lead Gen            logger.info("STEP 8: Referral Sources - Lead Gen...")            result = page.evaluate("""                (function() {                    try {                        // Find Referral Sources dropdown                        var dropdown = $('label:contains("Referral Sources")').next().find('[role="listbox"]').data('kendoDropDownList');                        if (!dropdown) {                            return {success: false, error: 'Referral Sources dropdown not found'};                        }                                                dropdown.select(function(dataItem) {                            return dataItem.text === "Lead Gen";                        });                        dropdown.trigger('change');                                                return {success: true};                    } catch(e) {                        return {success: false, error: e.toString()};                    }                })()            """)            if not result.get('success'):                raise Exception(f"Referral Sources selection failed: {result.get('error')}")            time.sleep(1)            logger.info("✓ Referral Sources set")                        # STEP 9: Staff - Rodolfo Arceo            logger.info("STEP 9: Staff - Rodolfo Arceo...")            result = page.evaluate("""                (function() {                    try {                        // Find Staff dropdown                        var dropdown = $('label:contains("Staff")').next().find('[role="listbox"]').data('kendoDropDownList');                        if (!dropdown) {                            return {success: false, error: 'Staff dropdown not found'};                        }                                                dropdown.select(function(dataItem) {                            return dataItem.text === "Rodolfo Arceo";                        });                        dropdown.trigger('change');                                                return {success: true};                    } catch(e) {                        return {success: false, error: e.toString()};                    }                })()            """)            if not result.get('success'):                raise Exception(f"Staff selection failed: {result.get('error')}")            time.sleep(1)            logger.info("✓ Staff set")                        # STEP 10: Project Roles - Estimator            logger.info("STEP 10: Project Roles - Estimator...")            result = page.evaluate("""                (function() {                    try {                        // Find Project Roles multiselect                        var multiselect = $('label:contains("Project Roles")').next().find('[role="combobox"]').data('kendoMultiSelect');                        if (!multiselect) {                            return {success: false, error: 'Project Roles multiselect not found'};                        }                                                // Find Estimator in the data source                        var dataSource = multiselect.dataSource;                        var estimatorItem = dataSource.data().find(item => item.text === "Estimator");                        if (estimatorItem) {                            multiselect.value([estimatorItem.value]);                            multiselect.trigger('change');                        }                                                return {success: true};                    } catch(e) {                        return {success: false, error: e.toString()};                    }                })()            """)            if not result.get('success'):                raise Exception(f"Project Roles selection failed: {result.get('error')}")            time.sleep(1)            logger.info("✓ Project Roles set")                        logger.info("Form filling complete!")            return True                    except Exception as e:            logger.error(f"Form filling error: {str(e)}")            raise Exception(f"Form filling failed: {str(e)}")    
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
