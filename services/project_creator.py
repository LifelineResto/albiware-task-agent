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
            
            # Direct navigation to project creation URL (more reliable)
            page.goto(f"{self.albiware_url}/Project/New", wait_until="networkidle", timeout=45000)
            logger.info(f"Navigated to: {page.url}")
            
            # Wait for form to load (try multiple selectors)
            try:
                page.wait_for_selector('#NewProjectForm', timeout=30000)
                logger.info("Project creation form loaded (#NewProjectForm found)")
            except:
                # Try alternative - wait for any form element
                logger.info("#NewProjectForm not found, checking for form elements...")
                page.wait_for_selector('form', timeout=10000)
                logger.info("Form element found")
            
            return True
            
        except Exception as e:
            logger.error(f"Navigation error: {e}")
            logger.error(f"Current URL: {page.url}")
            # Take screenshot for debugging
            try:
                page.screenshot(path="/tmp/nav_error.png")
                logger.error("Screenshot saved to /tmp/nav_error.png")
            except:
                pass
            return False
    
    def _fill_project_form(self, page: Page, contact: Contact) -> bool:
        """Fill out the project creation form with collected details"""
        try:
            logger.info(f"Filling project form for {contact.full_name}...")
            
            # Helper function for Kendo dropdowns
            def select_dropdown(label_text: str, value_text: str) -> bool:
                try:
                    # Scroll label into view
                    page.locator(f'label:has-text("{label_text}")').scroll_into_view_if_needed()
                    time.sleep(0.3)
                    
                    # Click dropdown to open
                    page.locator(f'label:has-text("{label_text}")').locator('..').locator('span[role="listbox"], span[role="combobox"]').first.click()
                    time.sleep(0.5)
                    
                    # Select option
                    page.locator(f'li:has-text("{value_text}")').first.click(timeout=5000)
                    time.sleep(0.3)
                    
                    logger.info(f"Selected {label_text}: {value_text}")
                    return True
                except Exception as e:
                    logger.warning(f"Could not select {label_text}: {e}")
                    return False
            
            # 1. Customer - Use JavaScript to directly set the customer value
            logger.info(f"Selecting customer: {contact.full_name} (Albiware ID: {contact.albiware_contact_id})")
            try:
                # Step 1: Select "Add Existing" from CustomerOption dropdown
                logger.info("Setting CustomerOption to Add Existing")
                page.evaluate("""
                    const customerOption = document.querySelector('#CustomerOption');
                    if (customerOption) {
                        customerOption.value = 'AddExisting';
                        customerOption.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                """)
                logger.info("Waiting for customer field to appear...")
                time.sleep(4)  # Wait for the customer field to be added to DOM
                
                # Step 2: Use JavaScript to directly set the Select2 value
                logger.info(f"Setting customer Select2 value to {contact.albiware_contact_id}")
                result = page.evaluate(f"""
                    (function() {{
                        try {{
                            // Wait for Select2 to be initialized
                            const customerSelect = document.querySelector('select[name="ProjectCustomer.ExistingOrganizationContactIds"]');
                            if (!customerSelect) {{
                                return {{ success: false, error: 'Customer select element not found' }};
                            }}
                            
                            // Check if jQuery and Select2 are available
                            if (typeof jQuery === 'undefined' || typeof jQuery.fn.select2 === 'undefined') {{
                                return {{ success: false, error: 'jQuery or Select2 not available' }};
                            }}
                            
                            // Create a new option with the contact ID and name
                            const contactId = '{contact.albiware_contact_id}';
                            const contactName = '{contact.full_name}';
                            
                            // Add the option if it doesn't exist
                            const $select = jQuery(customerSelect);
                            if ($select.find(`option[value="${{contactId}}"]`).length === 0) {{
                                const newOption = new Option(contactName, contactId, true, true);
                                $select.append(newOption);
                            }} else {{
                                $select.val(contactId);
                            }}
                            
                            // Trigger change event
                            $select.trigger('change');
                            
                            return {{ success: true, value: contactId, name: contactName }};
                        }} catch (e) {{
                            return {{ success: false, error: e.toString() }};
                        }}
                    }})()
                """)
                
                logger.info(f"JavaScript result: {result}")
                
                if not result.get('success'):
                    raise Exception(f"Failed to set customer value: {result.get('error')}")
                
                time.sleep(1)
                logger.info(f"Customer selected successfully: {result.get('name')}")
                
                
            except Exception as e:
                logger.error(f"Failed to select customer: {e}")
                logger.error(f"Full error: {str(e)}")
                return False
            
            # 2. Project Type
            project_type_map = {
                'Water Damage': 'Emergency Mitigation Services (EMS)',
                'Fire Damage': 'Emergency Mitigation Services (EMS)',
                'Mold': 'Emergency Mitigation Services (EMS)',
                'Other': 'Emergency Mitigation Services (EMS)'
            }
            albiware_project_type = project_type_map.get(contact.project_type, 'Emergency Mitigation Services (EMS)')
            select_dropdown("Project Type", albiware_project_type)
            
            # 3. Property Type
            if contact.property_type:
                select_dropdown("Property Type", contact.property_type)
            
            # 4. Location
            select_dropdown("Location", "Main Office")
            
            # 5. Insurance
            insurance_value = "Yes" if contact.has_insurance else "No"
            select_dropdown("Insurance Info", insurance_value)
            
            # 6. Referral Source (already in Albiware format from SMS)
            if contact.referral_source:
                select_dropdown("Referral Source", contact.referral_source)
            else:
                select_dropdown("Referral Source", "Lead Gen")  # Default
            
            # 7. Assigned Staff - Use direct select element
            try:
                logger.info("Selecting Staff: Rodolfo Arceo")
                page.select_option('select#StaffId', label='Rodolfo Arceo')
                logger.info("Staff selected successfully")
            except Exception as e:
                logger.warning(f"Could not select Staff: {e}")
            
            # 8. Project Roles - Use Select2 for searchable dropdown
            try:
                logger.info("Selecting Project Role: Estimator")
                # Open the Project Role Select2 dropdown
                page.locator('select#ProjectRoleId').evaluate('el => jQuery(el).select2("open")')
                time.sleep(0.5)
                
                # Type to search for Estimator
                search_input = page.locator('.select2-search__field').last
                search_input.type('Estimator', delay=100)
                time.sleep(1)
                
                # Click the result
                page.locator('.select2-results__option:has-text("Estimator")').first.click()
                logger.info("Project role selected successfully")
            except Exception as e:
                logger.warning(f"Could not select Project Role: {e}")
            
            # 9. Internal Details
            try:
                notes = (
                    f"AUTO-CREATED via AI Agent\\n"
                    f"Outcome: Appointment Set\\n"
                    f"Type: {contact.project_type}\\n"
                    f"Property: {contact.property_type}\\n"
                    f"Insurance: {'Yes - ' + (contact.insurance_company or 'Unknown') if contact.has_insurance else 'No'}\\n"
                    f"Source: {contact.referral_source}\\n"
                    f"Created: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
                )
                page.fill('textarea#Sandbox', notes)
            except Exception as e:
                logger.warning(f"Could not add notes: {e}")
            
            logger.info("Project form filled successfully")
            return True
            
        except Exception as e:
            logger.error(f"Form filling error: {e}")
            return False
    
    def _submit_and_verify(self, page: Page) -> Optional[int]:
        """Submit the form and verify project was created"""
        try:
            logger.info("Submitting project form...")
            
            # Check if submit button exists
            submit_button = page.locator('input#SubmitButton')
            if submit_button.count() == 0:
                logger.error("Submit button not found!")
                # Try alternative selectors
                logger.info("Trying alternative submit button selectors...")
                submit_button = page.locator('button[type="submit"], input[type="submit"]').first
            
            # Wait for button to be visible and enabled
            submit_button.wait_for(state='visible', timeout=10000)
            logger.info("Submit button found and visible")
            
            # Scroll to button
            submit_button.scroll_into_view_if_needed()
            time.sleep(0.5)
            
            # Click Create button
            submit_button.click()
            logger.info("Clicked submit button")
            
            # Wait for redirect to project detail page
            logger.info("Waiting for redirect to project page...")
            page.wait_for_url("**/Project/*", timeout=30000)
            
            current_url = page.url
            logger.info(f"Project created, redirected to: {current_url}")
            
            # Extract project ID from URL
            # Format: https://app.albiware.com/Project/1617650?tab=BasicInfo
            if '/Project/' in current_url:
                try:
                    project_id_str = current_url.split('/Project/')[-1].split('?')[0].split('#')[0]
                    project_id = int(project_id_str)
                    logger.info(f"✅ Project created successfully with ID: {project_id}")
                    return project_id
                except (ValueError, IndexError) as e:
                    logger.error(f"Could not parse project ID: {e}")
                    return None
            
            logger.warning("Could not extract project ID from URL")
            return None
            
        except PlaywrightTimeout as e:
            logger.error(f"Timeout waiting for project creation redirect: {e}")
            logger.info(f"Current URL: {page.url}")
            # Check for validation errors on the page
            try:
                errors = page.locator('.field-validation-error, .validation-summary-errors').all_text_contents()
                if errors:
                    logger.error(f"Validation errors on form: {errors}")
            except:
                pass
            return None
        except Exception as e:
            logger.error(f"Submit/verify error: {e}")
            logger.info(f"Current URL: {page.url}")
            return None
    
    def process_pending_projects(self, db: Session) -> int:
        """
        Process all contacts that need project creation
        
        Returns:
            Number of projects created
        """
        try:
            # Find contacts that need project creation
            logger.info("Querying for contacts needing project creation...")
            all_contacts = db.query(Contact).all()
            logger.info(f"Total contacts in database: {len(all_contacts)}")
            
            contacts = db.query(Contact).filter(
                Contact.project_creation_needed == True,
                Contact.project_created == False
            ).all()
            
            logger.info(f"Contacts with project_creation_needed=True: {len(contacts)}")
            for c in contacts:
                logger.info(f"  - Contact {c.id}: {c.full_name}, project_created={c.project_created}")
            
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
