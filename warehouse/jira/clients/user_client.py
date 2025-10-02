# ============================================
# jira/clients/user_client.py
# ============================================
import requests
from typing import List, Dict, Optional
from django.conf import settings
from django.core.cache import cache


class UserServiceClient:
    """Client to communicate with User Service API"""
    
    BASE_URL = getattr(settings, 'USER_SERVICE_URL', 'http://user-service:8000/api')
    CACHE_TTL = 300  # 5 minutes
    
    @classmethod
    def get_user(cls, user_id: str) -> Optional[Dict]:
        """Get single user by ID"""
        cache_key = f"user:{user_id}"
        cached = cache.get(cache_key)
        
        if cached:
            return cached
        
        try:
            response = requests.get(
                f"{cls.BASE_URL}/users/{user_id}",
                timeout=5
            )
            response.raise_for_status()
            user_data = response.json()
            cache.set(cache_key, user_data, cls.CACHE_TTL)
            return user_data
        except requests.RequestException as e:
            print(f"Error fetching user {user_id}: {e}")
            return None
    
    @classmethod
    def get_users_by_ids(cls, user_ids: List[str]) -> Dict[str, Dict]:
        """
        Batch get users by IDs
        Returns dict: {user_id: user_data}
        """
        if not user_ids:
            return {}
        
        user_ids = list(set(user_ids))  # Remove duplicates
        users_dict = {}
        ids_to_fetch = []
        
        # Check cache first
        for user_id in user_ids:
            cache_key = f"user:{user_id}"
            cached = cache.get(cache_key)
            if cached:
                users_dict[user_id] = cached
            else:
                ids_to_fetch.append(user_id)
        
        # Fetch remaining from API
        if ids_to_fetch:
            try:
                response = requests.post(
                    f"{cls.BASE_URL}/users/batch",
                    json={'ids': ids_to_fetch},
                    timeout=5
                )
                response.raise_for_status()
                fetched_users = response.json()
                
                for user in fetched_users:
                    user_id = str(user['id'])
                    users_dict[user_id] = user
                    cache_key = f"user:{user_id}"
                    cache.set(cache_key, user, cls.CACHE_TTL)
                    
            except requests.RequestException as e:
                print(f"Error batch fetching users: {e}")
        
        return users_dict
    
    @classmethod
    def verify_user_exists(cls, user_id: str) -> bool:
        """Check if user exists"""
        user = cls.get_user(user_id)
        return user is not None