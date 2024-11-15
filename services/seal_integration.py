from typing import Dict, Any
import requests
from requests.exceptions import RequestException
import time

class SealSubscriptionService:
    def __init__(self, api_key: str, shop_url: str):
        self.api_key = api_key
        self.base_url = f"https://{shop_url}/apps/seal/api/v1"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })
    
    def create_subscription(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new subscription in Seal"""
        return self._make_request('POST', '/subscriptions', json=data)
    
    def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Fetch subscription details from Seal"""
        return self._make_request('GET', f'/subscriptions/{subscription_id}')
    
    def update_subscription(self, subscription_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update subscription in Seal based on calendar changes"""
        return self._make_request('PATCH', f'/subscriptions/{subscription_id}', json=data)
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Handle API requests with retry logic and error handling"""
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                response = self.session.request(
                    method,
                    f"{self.base_url}{endpoint}",
                    **kwargs
                )
                response.raise_for_status()
                return response.json()
            except RequestException as e:
                if attempt == max_retries - 1:
                    raise
                time.sleep(retry_delay * (attempt + 1)) 