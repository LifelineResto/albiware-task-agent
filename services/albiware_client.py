"""
Albiware API Client
Handles all interactions with the Albiware API for retrieving project and task data.
"""

import requests
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AlbiwareClient:
    """Client for interacting with the Albiware API."""
    
    def __init__(self, api_key: str, base_url: str):
        """
        Initialize the Albiware client.
        
        Args:
            api_key: Albiware API key for authentication
            base_url: Base URL for the Albiware API
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "apikey": api_key,
            "accept": "application/json"
        }
    
    def get_all_projects(self, open_only: bool = True, page: int = 1, page_size: int = 100) -> List[Dict]:
        """
        Retrieve all projects from Albiware.
        
        Args:
            open_only: If True, only retrieve open projects
            page: Page number for pagination
            page_size: Number of results per page
            
        Returns:
            List of project dictionaries
        """
        url = f"{self.base_url}/Integrations/Projects"
        params = {
            "page": page,
            "pageSize": page_size,
            "openOnly": str(open_only).lower()
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            response_data = response.json()
            data = response_data.get('data', [])
            logger.info(f"Retrieved {len(data)} projects from Albiware")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving projects from Albiware: {e}")
            return []
    
    def get_project_by_id(self, project_id: int) -> Optional[Dict]:
        """
        Retrieve a specific project by ID.
        
        Args:
            project_id: The project ID
            
        Returns:
            Project dictionary or None if not found
        """
        url = f"{self.base_url}/Integrations/Projects/{project_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving project {project_id}: {e}")
            return None
    
    def get_all_tasks(self, project_id: Optional[int] = None, page: int = 1, page_size: int = 100) -> List[Dict]:
        """
        Retrieve all tasks from Albiware.
        
        Args:
            project_id: Optional project ID to filter tasks
            page: Page number for pagination
            page_size: Number of results per page
            
        Returns:
            List of task dictionaries
        """
        url = f"{self.base_url}/Integrations/Tasks"
        params = {
            "page": page,
            "pageSize": page_size
        }
        
        if project_id:
            params["projectId"] = project_id
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            response_data = response.json()
            data = response_data.get('data', [])
            logger.info(f"Retrieved {len(data)} tasks from Albiware")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving tasks from Albiware: {e}")
            return []
    
    def get_task_by_id(self, task_id: int) -> Optional[Dict]:
        """
        Retrieve a specific task by ID.
        
        Args:
            task_id: The task ID
            
        Returns:
            Task dictionary or None if not found
        """
        url = f"{self.base_url}/Integrations/Tasks/{task_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving task {task_id}: {e}")
            return None
    
    def get_project_timeline(self, project_id: int) -> List[Dict]:
        """
        Retrieve the timeline for a specific project.
        
        Args:
            project_id: The project ID
            
        Returns:
            List of timeline event dictionaries
        """
        url = f"{self.base_url}/Integrations/Projects/{project_id}/Timeline"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving timeline for project {project_id}: {e}")
            return []
    
    def get_project_staff(self, project_id: int) -> List[Dict]:
        """
        Retrieve staff assigned to a specific project.
        
        Args:
            project_id: The project ID
            
        Returns:
            List of staff dictionaries
        """
        url = f"{self.base_url}/Integrations/Projects/{project_id}/Staff"
        
        try:
            response = requests.post(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving staff for project {project_id}: {e}")
            return []
    
    def get_all_contacts(self, page: int = 1, page_size: int = 100) -> List[Dict]:
        """
        Retrieve all contacts from Albiware.
        
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
