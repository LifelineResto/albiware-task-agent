import os
import requests
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Feature flag - set to False for testing to avoid using API credits
ENABLE_PROPERTY_LOOKUP = os.getenv('ENABLE_PROPERTY_LOOKUP', 'false').lower() == 'true'

# RapidAPI credentials
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', '6f5f7bf2ddmsha07dd01ac88dee3p127f46jsn46a46ee09c85')
RAPIDAPI_HOST = 'real-time-real-estate-data.p.rapidapi.com'


def get_property_data(address: str) -> Optional[Dict]:
    """
    Lookup property data by address using Real-Time Real-Estate Data API.
    
    Args:
        address: Full property address (e.g., "7151 S Durango Dr Unit 303 Las Vegas NV 89113")
    
    Returns:
        Dictionary with property data or None if lookup fails or is disabled
    """
    if not ENABLE_PROPERTY_LOOKUP:
        logger.info(f"Property lookup DISABLED (feature flag). Would have looked up: {address}")
        return None
    
    if not address:
        logger.warning("No address provided for property lookup")
        return None
    
    try:
        url = f"https://{RAPIDAPI_HOST}/property-details-address"
        headers = {
            'x-rapidapi-host': RAPIDAPI_HOST,
            'x-rapidapi-key': RAPIDAPI_KEY
        }
        params = {'address': address}
        
        logger.info(f"Looking up property data for address: {address}")
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                logger.info(f"Successfully retrieved property data for {address}")
                return data['data']
            else:
                logger.warning(f"No property data found in API response for {address}")
                return None
        else:
            logger.error(f"Property API returned status {response.status_code}: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error(f"Property API timeout for address: {address}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Property API request failed: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in property lookup: {str(e)}")
        return None


def get_year_built(address: str) -> Optional[int]:
    """
    Get the year built for a property address.
    
    Args:
        address: Full property address
    
    Returns:
        Year built as integer or None if not found
    """
    property_data = get_property_data(address)
    if property_data and 'yearBuilt' in property_data:
        year = property_data['yearBuilt']
        logger.info(f"Year built for {address}: {year}")
        return year
    return None


def format_address_for_lookup(street: str, city: str, state: str, zip_code: str) -> str:
    """
    Format address components into a single string for API lookup.
    
    Args:
        street: Street address
        city: City name
        state: State code (e.g., "NV")
        zip_code: ZIP code
    
    Returns:
        Formatted address string
    """
    parts = [p.strip() for p in [street, city, state, zip_code] if p and p.strip()]
    return ' '.join(parts)
