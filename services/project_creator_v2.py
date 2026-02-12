"""
Improved Project Creator - Uses direct navigation and robust selectors
Replaces the navigation and form filling methods in project_creator.py
"""

import logging
import time
from datetime import datetime
from typing import Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from database.enhanced_models import Contact

logger = logging.getLogger(__name__)


def navigate_to_create_project_v2(page: Page) -> bool:
    """Navigate directly to project creation URL"""
    try:
        logger.info("Navigating to project creation...")
        
        # Direct navigation - much more reliable than clicking through menus
        page.goto("https://app.albiware.com/Project/New", wait_until="networkidle", timeout=30000)
        
        # Wait for form to be ready
        page.wait_for_selector('#NewProjectForm', timeout=15000)
        logger.info("Project creation form loaded")
        
        return True
        
    except Exception as e:
        logger.error(f"Navigation error: {e}")
        return False


def fill_project_form_v2(page: Page, contact: Contact) -> bool:
    """
    Fill the Albiware project creation form
    Uses a combination of strategies to handle Kendo UI dropdowns
    """
    try:
        logger.info(f"Filling project form for {contact.full_name}...")
        
        # Helper function to select from Kendo dropdown
        def select_kendo_dropdown(page, label_text, value_text, timeout=5000):
            """Select a value from a Kendo UI dropdown"""
            try:
                # Find the dropdown by nearby label
                page.locator(f'label:has-text("{label_text}")').scroll_into_view_if_needed()
                time.sleep(0.3)
                
                # Click the dropdown to open it
                page.locator(f'label:has-text("{label_text}")').locator('..').locator('span[role="listbox"], span[role="combobox"]').first.click()
                time.sleep(0.5)
                
                # Click the desired option
                page.locator(f'li:has-text("{value_text}")').first.click(timeout=timeout)
                time.sleep(0.3)
                
                logger.info(f"Selected {label_text}: {value_text}")
                return True
            except Exception as e:
                logger.warning(f"Could not select {label_text}: {e}")
                return False
        
        # 1. Customer - Search and select existing contact
        logger.info(f"Selecting customer: {contact.full_name}")
        try:
            # The customer field is in "Customer Information" section
            # Click on the search input
            customer_input = page.locator('input[role="searchbox"]').first
            customer_input.click()
            customer_input.fill(contact.full_name)
            time.sleep(1)
            
            # Select from dropdown results
            page.locator(f'li:has-text("{contact.full_name}")').first.click()
            time.sleep(0.5)
            logger.info(f"Selected customer: {contact.full_name}")
        except Exception as e:
            logger.error(f"Failed to select customer: {e}")
            return False
        
        # 2. Project Type
        project_type_map = {
            'Water Damage': 'Emergency Mitigation Services (EMS)',
            'Fire Damage': 'Emergency Mitigation Services (EMS)',
            'Mold': 'Emergency Mitigation Services (EMS)',
            'Other': 'Emergency Mitigation Services (EMS)'
        }
        albiware_project_type = project_type_map.get(contact.project_type, 'Emergency Mitigation Services (EMS)')
        select_kendo_dropdown(page, "Project Type", albiware_project_type)
        
        # 3. Property Type
        if contact.property_type:
            select_kendo_dropdown(page, "Property Type", contact.property_type)
        
        # 4. Location - Default to Main Office
        select_kendo_dropdown(page, "Location", "Main Office")
        
        # 5. Insurance Info
        insurance_value = "Yes" if contact.has_insurance else "No"
        select_kendo_dropdown(page, "Insurance Info", insurance_value)
        
        # 6. Referral Source - Map to Albiware values
        referral_map = {
            'Google': 'Lead Gen',
            'Yelp': 'Lead Gen',
            'Referral': 'Lead Gen',
            'Other': 'Lead Gen'
        }
        albiware_referral = referral_map.get(contact.referral_source, 'Lead Gen')
        select_kendo_dropdown(page, "Referral Source", albiware_referral)
        
        # 7. Assigned Staff - Rodolfo Arceo
        select_kendo_dropdown(page, "Staff", "Rodolfo Arceo")
        
        # 8. Project Roles - Estimator
        try:
            # Project roles is a multi-select, need to click the option
            page.locator('option:has-text("Estimator")').click()
            logger.info("Selected project role: Estimator")
        except Exception as e:
            logger.warning(f"Could not select Estimator role: {e}")
        
        # 9. Internal Details - Add automation context
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
            logger.info("Added internal details")
        except Exception as e:
            logger.warning(f"Could not add internal details: {e}")
        
        logger.info("Project form filled successfully")
        return True
        
    except Exception as e:
        logger.error(f"Form filling error: {e}")
        return False


def submit_and_verify_v2(page: Page) -> Optional[int]:
    """Submit form and extract project ID"""
    try:
        logger.info("Submitting project form...")
        
        # Click Create button
        page.click('input#SubmitButton')
        
        # Wait for redirect to project page
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
        
        return None
        
    except PlaywrightTimeout:
        logger.error("Timeout waiting for project creation redirect")
        return None
    except Exception as e:
        logger.error(f"Submit error: {e}")
        return None
