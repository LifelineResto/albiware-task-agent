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
            
            # Wait for Kendo widgets to initialize
            logger.info("Waiting for Kendo widgets to initialize...")
            time.sleep(3)  # Give Kendo time to initialize all widgets
            
            # Verify critical widgets are initialized
            widgets_ready = page.evaluate("""
                (function() {
                    if (!window.jQuery) return {ready: false, error: 'jQuery not loaded'};
                    
                    const customerOption = jQuery('#CustomerOption').data('kendoDropDownList');
                    const projectType = jQuery('#ProjectTypeId').data('kendoDropDownList');
                    const propertyType = jQuery('#PropertyType').data('kendoComboBox');
                    
                    return {
                        ready: !!(customerOption && projectType && propertyType),
                        customerOption: !!customerOption,
                        projectType: !!projectType,
                        propertyType: !!propertyType
                    };
                })()
            """)
            logger.info(f"Kendo widgets status: {widgets_ready}")
            
            if not widgets_ready.get('ready'):
                logger.warning("Some Kendo widgets not initialized, waiting longer...")
                time.sleep(5)
            
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
            
            # Helper function for Kendo dropdowns - uses Kendo API with proper initialization wait
            def select_dropdown_kendo(element_id: str, value_text: str, label: str) -> bool:
                try:
                    logger.info(f"Selecting {label}: {value_text}")
                    
                    # Wait for Kendo widget to be initialized
                    result = page.evaluate(f"""
                        (function() {{
                            try {{
                                const element = document.querySelector('#{element_id}');
                                if (!element || !window.jQuery) {{
                                    return {{ success: false, error: 'Element or jQuery not found' }};
                                }}
                                
                                // Wait for Kendo widget initialization (check multiple times)
                                let kendoWidget = jQuery(element).data('kendoDropDownList');
                                
                                if (kendoWidget) {{
                                    // Use Kendo API to set value
                                    kendoWidget.value('{value_text}');
                                    kendoWidget.trigger('change');
                                    
                                    // Verify the value was set
                                    const actualValue = kendoWidget.value();
                                    if (actualValue === '{value_text}') {{
                                        return {{ success: true, method: 'kendo', verified: true }};
                                    }} else {{
                                        return {{ success: false, error: `Value not set correctly. Expected: {value_text}, Got: ${{actualValue}}` }};
                                    }}
                                }} else {{
                                    // Fallback to direct select element manipulation
                                    element.value = '{value_text}';
                                    jQuery(element).trigger('change');
                                    
                                    // Verify
                                    if (element.value === '{value_text}') {{
                                        return {{ success: true, method: 'direct', verified: true }};
                                    }} else {{
                                        return {{ success: false, error: 'Direct value set failed verification' }};
                                    }}
                                }}
                            }} catch (e) {{
                                return {{ success: false, error: e.toString() }};
                            }}
                        }})()
                    """)
                    
                    if result.get('success'):
                        logger.info(f"✓ Selected {label}: {value_text} (method: {result.get('method')}, verified: {result.get('verified')})")
                        time.sleep(1)  # Give time for any dependent fields to update
                        return True
                    else:
                        logger.error(f"✗ Could not select {label}: {result.get('error')}")
                        return False
                except Exception as e:
                    logger.error(f"✗ Exception selecting {label}: {e}")
                    return False
            
            # 1. Customer - First select "Add Existing" then select customer from dropdown
            logger.info(f"Selecting customer: {contact.full_name} (Albiware ID: {contact.albiware_contact_id})")
            try:
                # Step 1: Use Kendo API to select "Add Existing" from CustomerOption dropdown
                logger.info("Setting CustomerOption to Add Existing using Kendo API")
                page.evaluate("""
                    const customerOption = document.querySelector('#CustomerOption');
                    if (customerOption && window.jQuery) {
                        const kendoWidget = jQuery(customerOption).data('kendoDropDownList');
                        if (kendoWidget) {
                            kendoWidget.value('AddExisting');
                            kendoWidget.trigger('change');
                        } else {
                            // Fallback to direct value setting
                            customerOption.value = 'AddExisting';
                            customerOption.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }
                """)
                logger.info("Waiting for customer Select2 field to appear...")
                time.sleep(5)  # Give plenty of time for the field to be added
                
                # Step 2: Verify customer select exists
                customer_select = page.locator('select[name="ProjectCustomer.ExistingOrganizationContactIds"]')
                customer_select.wait_for(state='attached', timeout=10000)
                logger.info("Customer select element found")
                
                # Step 3: Use Select2 API to set the value
                logger.info(f"Setting customer using Select2 API: {contact.albiware_contact_id}")
                result = page.evaluate(f"""
                    (function() {{
                        try {{
                            const customerSelect = document.querySelector('select[name="ProjectCustomer.ExistingOrganizationContactIds"]');
                            if (!customerSelect || !window.jQuery) {{
                                return {{ success: false, error: 'Select element or jQuery not found' }};
                            }}
                            
                            const $select = jQuery(customerSelect);
                            const contactId = '{contact.albiware_contact_id}';
                            const contactName = '{contact.full_name}';
                            
                            // Add option and select it
                            if ($select.find(`option[value="${{contactId}}"]`).length === 0) {{
                                const newOption = new Option(contactName, contactId, true, true);
                                $select.append(newOption);
                            }} else {{
                                $select.val(contactId);
                            }}
                            
                            // Trigger Select2 change
                            $select.trigger('change.select2');
                            $select.trigger('change');
                            
                            return {{ success: true, value: contactId, name: contactName }};
                        }} catch (e) {{
                            return {{ success: false, error: e.toString() }};
                        }}
                    }})()
                """)
                
                logger.info(f"Customer selection result: {result}")
                if not result.get('success'):
                    raise Exception(f"Failed to set customer: {result.get('error')}")
                
                time.sleep(2)
                logger.info(f"Customer selected: {result.get('name')}")
                
                
                
            except Exception as e:
                logger.error(f"Failed to select customer: {e}")
                logger.error(f"Full error: {str(e)}")
                return False
            
            # 2. Project Type - Wait for Kendo widget then use API
            try:
                logger.info("Selecting Project Type")
                # Wait for Kendo widget to be initialized
                for attempt in range(10):
                    result = page.evaluate("""
                        (function() {
                            const projectType = document.querySelector('#ProjectTypeId');
                            if (!projectType || !window.jQuery) {
                                return {success: false, error: 'Element or jQuery not found', ready: false};
                            }
                            const kendoWidget = jQuery(projectType).data('kendoDropDownList');
                            if (!kendoWidget) {
                                return {success: false, error: 'Kendo widget not initialized yet', ready: false};
                            }
                            kendoWidget.value('1');  // Emergency Mitigation Services
                            kendoWidget.trigger('change');
                            return {success: true, value: kendoWidget.value(), ready: true};
                        })()
                    """)
                    if result.get('ready'):
                        break
                    time.sleep(0.5)
                    logger.info(f"Waiting for Project Type widget... attempt {attempt+1}")
                
                if not result.get('success'):
                    logger.error(f"✗ Failed to select Project Type: {result.get('error')}")
                    return False
                time.sleep(1)
                logger.info(f"✓ Project Type selected: {result.get('value')}")
            except Exception as e:
                logger.error(f"✗ Failed to select Project Type: {e}")
                return False
            
            # 3. Property Type - Wait for Kendo ComboBox widget then use API
            if contact.property_type:
                try:
                    logger.info(f"Selecting Property Type: {contact.property_type}")
                    # Wait for Kendo widget to be initialized
                    for attempt in range(10):
                        result = page.evaluate(f"""
                            (function() {{
                                const propertyType = document.querySelector('#PropertyType');
                                if (!propertyType || !window.jQuery) {{
                                    return {{success: false, error: 'Element or jQuery not found', ready: false}};
                                }}
                                const kendoWidget = jQuery(propertyType).data('kendoComboBox');
                                if (!kendoWidget) {{
                                    return {{success: false, error: 'Kendo widget not initialized yet', ready: false}};
                                }}
                                kendoWidget.value('{contact.property_type}');
                                kendoWidget.trigger('change');
                                return {{success: true, value: kendoWidget.value(), ready: true}};
                            }})()
                        """)
                        if result.get('ready'):
                            break
                        time.sleep(0.5)
                        logger.info(f"Waiting for Property Type widget... attempt {attempt+1}")
                    
                    if not result.get('success'):
                        logger.error(f"✗ Failed to select Property Type: {result.get('error')}")
                        return False
                    time.sleep(1)
                    logger.info(f"✓ Property Type selected: {result.get('value')}")
                except Exception as e:
                    logger.error(f"✗ Failed to select Property Type: {e}")
                    return False
            
            # 4. Location - Already defaulted to Main Office, skip
            
            # 5. Insurance - Use select element directly
            try:
                insurance_value = "Yes" if contact.has_insurance else "No"
                logger.info(f"Selecting Insurance: {insurance_value}")
                page.select_option('select#CoveredLoss', label=insurance_value)
                time.sleep(0.5)
                logger.info(f"✓ Insurance selected: {insurance_value}")
            except Exception as e:
                logger.error(f"✗ Failed to select Insurance: {e}")
            
            # 6. Referral Source - Skip for now, not required
            
            # 7. Assigned Staff - Use select element directly
            try:
                logger.info("Selecting Staff: Rodolfo Arceo")
                page.select_option('select#StaffId', label='Rodolfo Arceo')
                time.sleep(0.5)
                logger.info("✓ Staff selected: Rodolfo Arceo")
            except Exception as e:
                logger.error(f"✗ Failed to select Staff: {e}")
            
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
            
            # Log form state before submitting
            try:
                form_state = page.evaluate("""
                    (function() {
                        const state = {};
                        
                        // Check CustomerOption
                        const customerOption = document.querySelector('#CustomerOption');
                        if (customerOption) {
                            const kendoWidget = window.jQuery && jQuery(customerOption).data('kendoDropDownList');
                            state.customerOption = kendoWidget ? kendoWidget.value() : customerOption.value;
                        }
                        
                        // Check Customer select
                        const customerSelect = document.querySelector('select[name="ProjectCustomer.ExistingOrganizationContactIds"]');
                        state.customer = customerSelect ? customerSelect.value : null;
                        
                        // Check ProjectType
                        const projectType = document.querySelector('#ProjectTypeId');
                        if (projectType) {
                            const kendoWidget = window.jQuery && jQuery(projectType).data('kendoDropDownList');
                            state.projectType = kendoWidget ? kendoWidget.value() : projectType.value;
                        }
                        
                        // Check PropertyType
                        const propertyType = document.querySelector('#PropertyType');
                        if (propertyType) {
                            const kendoWidget = window.jQuery && jQuery(propertyType).data('kendoComboBox');
                            state.propertyType = kendoWidget ? kendoWidget.value() : propertyType.value;
                        }
                        
                        // Check Insurance
                        const insurance = document.querySelector('#CoveredLoss');
                        state.insurance = insurance ? insurance.value : null;
                        
                        // Check Staff
                        const staff = document.querySelector('#StaffId');
                        state.staff = staff ? staff.value : null;
                        
                        return state;
                    })()
                """)
                logger.info(f"Form state before submit: {form_state}")
            except Exception as e:
                logger.warning(f"Could not log form state: {e}")
            
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
            
            # Wait a moment for form submission
            time.sleep(2)
            
            # Check for validation errors
            try:
                validation_errors = page.locator('.field-validation-error, .validation-summary-errors li').all_text_contents()
                if validation_errors:
                    error_msg = f"Form validation errors: {validation_errors}"
                    logger.error(error_msg)
                    # Take screenshot for debugging
                    screenshot_path = f"/tmp/validation_error_{int(time.time())}.png"
                    page.screenshot(path=screenshot_path)
                    logger.error(f"Screenshot saved to {screenshot_path}")
                    raise Exception(error_msg)
            except Exception as e:
                if "validation" in str(e).lower():
                    raise e
                # No validation errors found, continue
                pass
            
            # Wait for redirect to project detail page
            logger.info("Waiting for redirect to project page...")
            logger.info(f"Current URL before wait: {page.url}")
            
            try:
                page.wait_for_url("**/Project/*", timeout=30000)
            except PlaywrightTimeout:
                logger.error(f"Timeout waiting for redirect. Current URL: {page.url}")
                # Check if we're still on /Project/New
                if '/Project/New' in page.url:
                    logger.error("Still on /Project/New - form may have validation errors")
                    # Check for any error messages
                    try:
                        errors = page.locator('.field-validation-error, .validation-summary-errors li, .alert-danger').all_text_contents()
                        if errors:
                            logger.error(f"Validation errors found: {errors}")
                        else:
                            logger.error("No visible validation errors found")
                        
                        # Log form field values for debugging
                        form_state = page.evaluate("""
                            () => {
                                return {
                                    customerOption: document.querySelector('#CustomerOption')?.value,
                                    projectType: document.querySelector('#ProjectTypeId')?.value,
                                    propertyType: document.querySelector('#PropertyType')?.value,
                                    location: document.querySelector('#LocationId')?.value,
                                    insurance: document.querySelector('#CoveredLoss')?.value,
                                    staff: document.querySelector('#StaffId')?.value,
                                    customerSelectValue: document.querySelector('select[name="ProjectCustomer.ExistingOrganizationContactIds"]')?.value
                                };
                            }
                        """)
                        logger.error(f"Form state at timeout: {form_state}")
                    except Exception as e:
                        logger.error(f"Error checking validation: {e}")
                raise
            
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
