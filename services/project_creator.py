"""
Albiware Project Creator - Clean Version Based on Manual Test
This version replicates the EXACT steps that successfully created Robb Bay project (ID: 1633513)
"""

import os
import time
import logging
from playwright.sync_api import sync_playwright
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class AlbiwareProjectCreator:
    def __init__(self, albiware_email: str = None, albiware_password: str = None):
        self.email = albiware_email or os.getenv('ALBIWARE_EMAIL')
        self.password = albiware_password or os.getenv('ALBIWARE_PASSWORD')
        
    def _login(self, page):
        """Login to Albiware - EXACT steps that worked"""
        try:
            logger.info("Logging in to Albiware...")
            page.goto('https://app.albiware.com/Login', wait_until='domcontentloaded')
            time.sleep(2)
            
            # Fill login form
            page.fill('input#Email', self.email)
            page.fill('input#password', self.password)
            page.click('button#btn-login')
            
            # Wait for dashboard
            page.wait_for_url('**/TaskDashboard', timeout=30000)
            logger.info("✓ Login successful")
            return True
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
    
    def _fill_form_simple(self, page, contact):
        """Fill the project form using SIMPLE, RELIABLE methods"""
        try:
            logger.info(f"Filling form for {contact.full_name}...")
            
            # Navigate to new project form
            page.goto('https://app.albiware.com/Project/New', wait_until='domcontentloaded')
            time.sleep(3)
            
            # STEP 1: Customer - Show hidden field and select
            logger.info("Step 1: Customer...")
            # Show the customer field by manipulating the DOM
            page.evaluate("""
                const existingOrgField = document.getElementById('ExistingOrganizationId');
                const grandparent = existingOrgField.parentElement.parentElement;
                grandparent.style.display = 'block';
                document.getElementById('CustomerOption').value = 'AddExisting';
            """)
            time.sleep(1)
            
            # Click to open the dropdown
            page.click('span[role="listbox"]:has-text("Choose One")')
            time.sleep(1)
            
            # Type to search
            page.fill('#ExistingOrganizationId-list input[role="listbox"]', contact.full_name)
            time.sleep(1)
            
            # Select the result
            page.keyboard.press('ArrowDown')
            time.sleep(0.5)
            page.keyboard.press('Enter')
            time.sleep(2)
            logger.info("✓ Customer selected")
            
            # STEP 2: Project Type - Use jQuery (this worked in earlier code)
            logger.info("Step 2: Project Type...")
            page.evaluate("""
                $('#ProjectTypeId').val('12674').trigger('change');
            """)
            time.sleep(1)
            logger.info("✓ Project Type: EMS")
            
            # STEP 3: Property Type
            logger.info("Step 3: Property Type...")
            page.evaluate("""
                $('#PropertyType').val('residential').trigger('change');
            """)
            time.sleep(1)
            logger.info("✓ Property Type: Residential")
            
            # STEP 4: Insurance - Set to No
            logger.info("Step 4: Insurance...")
            page.evaluate("""
                $('#CoveredLoss').val('0').trigger('change');
            """)
            time.sleep(1)
            logger.info("✓ Insurance: No")
            
            # STEP 5: Referrer Option - Set to Choose One (skip referrer)
            logger.info("Step 5: Referrer Option...")
            page.evaluate("""
                $('#ReferrerOption').val('ChooseOne').trigger('change');
            """)
            time.sleep(1)
            logger.info("✓ Referrer: None")
            
            # STEP 6: Staff - Rodolfo Arceo
            logger.info("Step 6: Staff...")
            page.evaluate("""
                // Find Rodolfo Arceo's value in the dropdown
                const rodolfoOption = Array.from(document.querySelectorAll('#StaffId option'))
                    .find(opt => opt.text.includes('Rodolfo Arceo'));
                if (rodolfoOption) {
                    $('#StaffId').val(rodolfoOption.value).trigger('change');
                }
            """)
            time.sleep(2)
            logger.info("✓ Staff: Rodolfo Arceo")
            
            # STEP 7: Project Role - Estimator
            logger.info("Step 7: Project Role...")
            page.evaluate("""
                // Find Estimator's value in the dropdown
                const estimatorOption = Array.from(document.querySelectorAll('#ProjectRoleId option'))
                    .find(opt => opt.text.includes('Estimator'));
                if (estimatorOption) {
                    $('#ProjectRoleId').val(estimatorOption.value).trigger('change');
                }
            """)
            time.sleep(1)
            logger.info("✓ Project Role: Estimator")
            
            logger.info("✓ Form filled successfully")
            return True
            
        except Exception as e:
            logger.error(f"Form filling error: {e}")
            return False
    
    def create_project_for_contact(self, db: Session, contact):
        """Create a project for a single contact"""
        try:
            logger.info(f"Creating project for contact: {contact.full_name}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                
                # Login
                if not self._login(page):
                    raise Exception("Login failed")
                
                # Fill form
                if not self._fill_form_simple(page, contact):
                    raise Exception("Form filling failed")
                
                # Click Create button
                logger.info("Clicking Create button...")
                page.click('#SubmitButton')
                time.sleep(3)
                
                # Check if we're on a project page (success)
                current_url = page.url
                if '/Projects/' in current_url and '/Create' not in current_url:
                    logger.info(f"✓ Project created successfully! URL: {current_url}")
                    
                    # Update database
                    contact.project_creation_needed = False
                    contact.project_created_at = time.time()
                    db.commit()
                    
                    browser.close()
                    return True
                else:
                    logger.error(f"Project creation may have failed. Current URL: {current_url}")
                    browser.close()
                    return False
                    
        except Exception as e:
            logger.error(f"Error creating project: {e}")
            return False
    
    def process_pending_projects(self, db: Session):
        """Process all pending project creation requests"""
        from database.enhanced_models import Contact
        
        logger.info("Processing pending project creation requests...")
        
        # Get contacts that need projects
        contacts = db.query(Contact).filter(
            Contact.project_creation_needed == True
        ).limit(10).all()
        
        logger.info(f"Found {len(contacts)} contacts pending project creation")
        
        created_count = 0
        for contact in contacts:
            if self.create_project_for_contact(db, contact):
                created_count += 1
        
        logger.info(f"Project creation complete. Created {created_count}/{len(contacts)} projects")
        return created_count
