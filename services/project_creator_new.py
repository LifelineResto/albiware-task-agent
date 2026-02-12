"""
Updated Project Creator with correct Albiware selectors
"""

import logging
import time
from datetime import datetime
from typing import Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from database.enhanced_models import Contact

logger = logging.getLogger(__name__)


def navigate_to_create_project(page: Page) -> bool:
    """Navigate to the project creation page"""
    try:
        logger.info("Navigating to project creation...")
        
        # Direct navigation to project creation URL
        page.goto("https://app.albiware.com/Project/New", wait_until="domcontentloaded", timeout=30000)
        
        # Wait for form to load
        page.wait_for_selector('#NewProjectForm', timeout=15000)
        
        logger.info("Project creation form loaded")
        return True
        
    except Exception as e:
        logger.error(f"Navigation error: {e}")
        return False


def fill_project_form(page: Page, contact: Contact) -> bool:
    """Fill out the project creation form with contact details"""
    try:
        logger.info(f"Filling project form for {contact.full_name}...")
        
        # 1. Customer Information - Select "Add Existing" and search for contact
        logger.info("Selecting customer...")
        
        # Click on the customer dropdown
        page.click('span[role="listbox"]:has-text("John Smith")')  # This opens the search
        time.sleep(0.5)
        
        # Type contact name in search box
        page.fill('input[role="searchbox"]', contact.full_name)
        time.sleep(1)
        
        # Click on the matching result
        page.click(f'li:has-text("{contact.full_name}")')
        time.sleep(0.5)
        
        logger.info(f"Selected customer: {contact.full_name}")
        
        # 2. Project Type - Map from collected data
        logger.info(f"Setting project type: {contact.project_type}")
        project_type_mapping = {
            'Water Damage': 'Emergency Mitigation Services (EMS)',
            'Fire Damage': 'Emergency Mitigation Services (EMS)',
            'Mold': 'Emergency Mitigation Services (EMS)',
            'Other': 'Emergency Mitigation Services (EMS)'
        }
        
        albiware_project_type = project_type_mapping.get(contact.project_type, 'Emergency Mitigation Services (EMS)')
        
        # Click project type dropdown
        page.click('label[id="ProjectTypeId_label"]')
        time.sleep(0.5)
        page.click(f'li:has-text("{albiware_project_type}")')
        time.sleep(0.5)
        
        # 3. Property Type
        logger.info(f"Setting property type: {contact.property_type}")
        # The property type dropdown is already visible, just need to click it
        property_type_selector = 'span[role="combobox"]:has-text("Residential"), span[role="combobox"]:has-text("Commercial")'
        page.click(property_type_selector)
        time.sleep(0.5)
        page.click(f'li:has-text("{contact.property_type}")')
        time.sleep(0.5)
        
        # 4. Location - Default to "Main Office"
        logger.info("Setting location to Main Office")
        # Location dropdown
        page.evaluate('''
            document.querySelectorAll('span[role="combobox"]').forEach(el => {
                if (el.textContent.includes('Main Office') || el.textContent.includes('Choose One')) {
                    el.click();
                }
            });
        ''')
        time.sleep(0.5)
        page.click('li:has-text("Main Office")')
        time.sleep(0.5)
        
        # 5. Insurance Info
        logger.info(f"Setting insurance: {contact.has_insurance}")
        insurance_value = "Yes" if contact.has_insurance else "No"
        
        # Find and click insurance dropdown
        page.evaluate(f'''
            document.querySelectorAll('span[role="combobox"]').forEach(el => {{
                if (el.textContent.includes('Yes') || el.textContent.includes('No')) {{
                    el.click();
                }}
            }});
        ''')
        time.sleep(0.5)
        page.click(f'li:has-text("{insurance_value}")')
        time.sleep(0.5)
        
        # 6. Referral Source
        logger.info(f"Setting referral source: {contact.referral_source}")
        referral_mapping = {
            'Google': 'Lead Gen',
            'Yelp': 'Lead Gen',
            'Referral': 'Lead Gen',
            'Other': 'Lead Gen'
        }
        
        albiware_referral = referral_mapping.get(contact.referral_source, 'Lead Gen')
        
        # Click referral source dropdown (in Referrer Information section)
        page.click('span[role="listbox"]:has-text("Lead Gen"), span[role="listbox"]:has-text("Choose One")')
        time.sleep(0.5)
        page.click(f'li:has-text("{albiware_referral}")')
        time.sleep(0.5)
        
        # 7. Assigned Staff - Rodolfo Arceo
        logger.info("Assigning staff: Rodolfo Arceo")
        # Staff dropdown should already show Rodolfo Arceo, but let's ensure it
        page.click('span[role="combobox"]:has-text("Rodolfo Arceo")')
        time.sleep(0.5)
        page.click('li:has-text("Rodolfo Arceo")')
        time.sleep(0.5)
        
        # 8. Project Roles - Estimator
        logger.info("Setting project role: Estimator")
        # Project roles multi-select
        page.click('span[role="combobox"]:has-text("Estimator")')
        time.sleep(0.5)
        # Select Estimator if not already selected
        if page.locator('option:has-text("Estimator")').count() > 0:
            page.click('option:has-text("Estimator")')
        time.sleep(0.5)
        
        # 9. Internal Details - Add automation note
        logger.info("Adding internal details...")
        notes = (
            f"Project created automatically via AI agent\\n"
            f"Contact outcome: Appointment Set\\n"
            f"Project Type: {contact.project_type}\\n"
            f"Property Type: {contact.property_type}\\n"
            f"Insurance: {'Yes - ' + contact.insurance_company if contact.has_insurance else 'No'}\\n"
            f"Referral Source: {contact.referral_source}\\n"
            f"Created: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )
        
        try:
            page.fill('textarea[id="Sandbox"]', notes)
        except:
            logger.warning("Could not fill internal details")
        
        logger.info("Project form filled successfully")
        return True
        
    except Exception as e:
        logger.error(f"Form filling error: {e}")
        logger.error(f"Current URL: {page.url}")
        return False


def submit_and_verify(page: Page) -> Optional[int]:
    """Submit the form and verify project was created"""
    try:
        logger.info("Submitting project form...")
        
        # Click the Create button
        page.click('input[id="SubmitButton"]')
        
        # Wait for navigation (project creation redirects to project detail page)
        page.wait_for_url("**/Project/*", timeout=30000)
        
        # Extract project ID from URL
        current_url = page.url
        logger.info(f"Redirected to: {current_url}")
        
        # URL format: https://app.albiware.com/Project/1617650?tab=BasicInfo
        if '/Project/' in current_url:
            project_id_str = current_url.split('/Project/')[-1].split('?')[0]
            try:
                project_id = int(project_id_str)
                logger.info(f"Project created with ID: {project_id}")
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
