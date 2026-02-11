"""
Extended Albiware Client for Contacts Management
"""

import requests
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class AlbiwareContactsClient:
    """Extended client for Albiware Contacts API"""
    
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "apikey": api_key,
            "accept": "application/json",
            "content-type": "application/json"
        }
    
    def get_all_contacts(self, page: int = 1, page_size: int = 100) -> List[Dict]:
        """
        Retrieve all contacts from Albiware
        
        Args:
            page: Page number for pagination
            page_size: Number of results per page
            
        Returns:
            List of contact dictionaries
        """
        url = f"{self.base_url}/Integrations/Contacts"
        params = {
            "page": page,
            "pageSize": page_size
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            response_data = response.json()
            data = response_data.get('data', [])
            logger.info(f"Retrieved {len(data)} contacts from Albiware")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving contacts from Albiware: {e}")
            return []
    
    def get_contact_by_id(self, contact_id: int) -> Optional[Dict]:
        """
        Retrieve a specific contact by ID
        
        Args:
            contact_id: The contact ID
            
        Returns:
            Contact dictionary or None if not found
        """
        url = f"{self.base_url}/Integrations/Contacts/{contact_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving contact {contact_id}: {e}")
            return None
    
    def create_contact(self, contact_data: Dict) -> Optional[Dict]:
        """
        Create a new contact in Albiware
        
        Args:
            contact_data: Dictionary with contact information
            
        Returns:
            Created contact data or None if failed
        """
        url = f"{self.base_url}/Integrations/Contacts/Create"
        
        try:
            response = requests.post(url, headers=self.headers, json=contact_data)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Created contact in Albiware: {result}")
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating contact in Albiware: {e}")
            return None
