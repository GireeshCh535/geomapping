"""
Utility module for making API calls with proper SSL error handling
Handles SSL handshake failures and provides retry logic

FOR OTHER SERVICES CALLING THIS API:
------------------------------------
If you're experiencing SSL handshake failures when calling layers.1acre.in API,
use one of these approaches:

Option 1: Disable SSL verification (for internal calls)
    import requests
    response = requests.get(url, verify=False)

Option 2: Use this utility module
    from maps.api_client import fetch_bounds_from_api
    data = fetch_bounds_from_api(state, city, layer, verify_ssl=False)

Option 3: Update your requests/urllib3
    pip install --upgrade requests urllib3

The API server supports TLS 1.2 and 1.3 with modern cipher suites.
If you're using older Python/requests versions, you may need to disable SSL verification.
"""

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging

logger = logging.getLogger(__name__)

# Disable SSL warnings for self-signed certificates or SSL issues
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def create_requests_session(verify_ssl=False, max_retries=3):
    """
    Create a requests session with proper SSL handling and retry logic
    Compatible with various SSL/TLS configurations for server-to-server calls
    
    Args:
        verify_ssl: Whether to verify SSL certificates (default: False for internal calls)
        max_retries: Maximum number of retries for failed requests
        
    Returns:
        requests.Session configured for API calls with SSL compatibility
    """
    session = requests.Session()
    
    # Configure retry strategy
    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    
    # Create HTTPAdapter with connection pooling
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,
        pool_maxsize=10
    )
    
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Configure SSL verification
    session.verify = verify_ssl
    
    # Set headers for better compatibility
    session.headers.update({
        'User-Agent': 'GeoMapping-API-Client/1.0',
        'Accept': 'application/json',
        'Connection': 'keep-alive',
    })
    
    return session


def fetch_bounds_from_api(state_slug, city_slug, layer_slug, base_url='https://layers.1acre.in', verify_ssl=False):
    """
    Fetch layer bounds from the API with proper SSL error handling
    
    Args:
        state_slug: State slug (e.g., 'telangana')
        city_slug: City slug (e.g., 'hyderabad')
        layer_slug: Layer slug (e.g., 'hyderabad_air_funnel_zones')
        base_url: Base URL for the API (default: 'https://layers.1acre.in')
        verify_ssl: Whether to verify SSL certificates (default: False)
        
    Returns:
        dict: Bounds data from API, or None if failed
    """
    url = f"{base_url}/api/layers/{state_slug}/{city_slug}/{layer_slug}/bounds/"
    
    max_attempts = 3
    
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"Attempt {attempt}: Trying to fetch bounds from {url}...")
            
            # Create session with SSL verification disabled
            session = create_requests_session(verify_ssl=verify_ssl, max_retries=1)
            
            response = session.get(url, timeout=10, verify=verify_ssl)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"✅ Successfully fetched bounds on attempt {attempt}")
            return data
            
        except requests.exceptions.SSLError as e:
            logger.warning(f"❌ Attempt {attempt} failed: SSLError: {e}")
            if attempt < max_attempts:
                logger.info(f"Retrying with SSL verification disabled...")
                verify_ssl = False
            else:
                logger.error(f"All SSL attempts failed")
                # Try urllib3 fallback with SSL disabled
                try:
                    logger.info("Trying urllib3 fallback...")
                    import urllib3
                    # Disable SSL warnings
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    
                    # Create pool manager without SSL verification
                    # Use cert_reqs parameter compatible with all urllib3 versions
                    http = urllib3.PoolManager(
                        cert_reqs='CERT_NONE',
                        ca_certs=None
                    )
                    
                    response = http.request('GET', url, timeout=10)
                    if response.status == 200:
                        import json
                        data = json.loads(response.data.decode('utf-8'))
                        logger.info("✅ urllib3 fallback succeeded")
                        return data
                    else:
                        logger.error(f"❌ urllib3 fallback failed with status {response.status}")
                except TypeError as e:
                    # Handle urllib3 version compatibility issues
                    logger.error(f"❌ urllib3 fallback failed: {e}")
                    logger.info("💡 Tip: Update urllib3 or use requests with verify=False")
                except Exception as fallback_error:
                    logger.error(f"❌ urllib3 fallback also failed: {fallback_error}")
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Attempt {attempt} failed: {e}")
            if attempt >= max_attempts:
                logger.error(f"All attempts failed")
                return None
                
        except Exception as e:
            logger.error(f"❌ Unexpected error on attempt {attempt}: {e}")
            if attempt >= max_attempts:
                return None
    
    return None


def check_coordinate_in_air_funnel(lat, lng, state_slug, city_slug, layer_slug, base_url='https://layers.1acre.in'):
    """
    Check if a coordinate is inside an air funnel zone by fetching bounds and checking
    
    Args:
        lat: Latitude
        lng: Longitude
        state_slug: State slug
        city_slug: City slug
        layer_slug: Layer slug (e.g., 'hyderabad_air_funnel_zones')
        base_url: Base URL for the API
        
    Returns:
        dict: Result with 'inside' boolean and 'data' from API, or None if failed
    """
    bounds_data = fetch_bounds_from_api(state_slug, city_slug, layer_slug, base_url)
    
    if not bounds_data:
        logger.warning("⚠️  Using hardcoded bounds as fallback")
        return None
    
    # Check if coordinate is within bounds
    bounds = bounds_data.get('bounds', {})
    if bounds:
        west = bounds.get('west')
        east = bounds.get('east')
        south = bounds.get('south')
        north = bounds.get('north')
        
        if west is not None and east is not None and south is not None and north is not None:
            inside = (west <= lng <= east) and (south <= lat <= north)
            return {
                'inside': inside,
                'bounds': bounds,
                'data': bounds_data
            }
    
    logger.warning("❌ OUTSIDE Air Funnel Zone (or calculation failed)")
    return None

