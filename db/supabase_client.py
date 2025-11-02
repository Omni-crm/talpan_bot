"""
Supabase Client Wrapper
עבודה ישירה עם Supabase באמצעות HTTP Requests
"""
import os
import requests
from typing import Optional, List, Dict, Any, Union
from datetime import datetime


class SupabaseClient:
    """Client עבור Supabase דרך HTTP Requests ישירים"""
    
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_ANON_KEY")
        self.secret_key = os.getenv("SUPABASE_SECRET_KEY")
        
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env")
        
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        print(f"✅ Supabase Client initialized: {self.url}")
    
    def select(self, table: str, filters: Optional[Dict] = None) -> List[Dict]:
        """SELECT query - מבוסס על HTTP GET request"""
        try:
            url = f"{self.url}/rest/v1/{table}"
            
            # בניית query parameters
            params = {}
            if filters:
                for key, value in filters.items():
                    params[key] = f"eq.{value}" if not str(value).startswith('eq.') else value
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            # Handle empty or None response
            if not response.text:
                return []
            
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            print(f"❌ SELECT error: {e}")
            return []
        except ValueError as e:
            # Handle JSON decode errors
            print(f"❌ JSON decode error: {e}")
            return []
    
    def insert(self, table: str, data: Dict) -> Dict:
        """INSERT query - מבוסס על HTTP POST request"""
        try:
            url = f"{self.url}/rest/v1/{table}"
            
            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            
            # Handle empty or None response
            if not response.text:
                return {}
            
            result = response.json()
            return result[0] if isinstance(result, list) else result
        
        except requests.exceptions.HTTPError as e:
            print(f"❌ INSERT error: {e}")
            print(f"   Response: {response.text}")
            raise
        except ValueError as e:
            # Handle JSON decode errors
            print(f"❌ JSON decode error: {e}")
            print(f"   Response text length: {len(response.text) if response.text else 0}")
            return {}
    
    def update(self, table: str, data: Dict, filters: Optional[Dict] = None) -> List[Dict]:
        """
        UPDATE query - מבוסס על HTTP PATCH request
        
        CRITICAL: Supabase REST API behavior:
        - Returns 200/204 on success
        - Returns 204 (No Content) if update succeeded but no rows matched (this is actually an error condition!)
        - Returns 400+ on error
        
        IMPORTANT: Empty list return value can mean:
        1. Update succeeded but no rows matched (should be treated as error)
        2. Update succeeded and rows were updated (but representation not returned - unlikely with Prefer header)
        
        We use 'Prefer: return=representation' header, so successful updates should return updated rows.
        If response is empty, we need to check if it was 204 (no match) or 200 (success but empty).
        """
        try:
            url = f"{self.url}/rest/v1/{table}"
            
            # בניית query parameters
            params = {}
            if filters:
                for key, value in filters.items():
                    params[key] = f"eq.{value}" if not str(value).startswith('eq.') else value
            
            response = requests.patch(url, headers=self.headers, json=data, params=params)
            
            # CRITICAL: Check status code before processing
            status_code = response.status_code
            
            # 204 No Content = successful but NO ROWS MATCHED (error condition!)
            if status_code == 204:
                print(f"⚠️ UPDATE: No rows matched for table {table} with filters {filters}")
                return []  # Return empty to indicate no match (treated as error by callers)
            
            # Raise exception for any other non-2xx status
            response.raise_for_status()
            
            # Handle empty or None response
            if not response.text:
                # With Prefer: return=representation, empty response might mean no match
                print(f"⚠️ UPDATE: Empty response for table {table} with filters {filters}")
                return []
            
            result = response.json()
            # Return as list for consistency
            return result if isinstance(result, list) else [result]
        
        except requests.exceptions.HTTPError as e:
            print(f"❌ UPDATE error: {e}")
            print(f"   URL: {url}")
            print(f"   Filters: {filters}")
            print(f"   Status: {response.status_code if 'response' in locals() else 'N/A'}")
            return []  # Return empty to indicate failure
        except ValueError as e:
            # Handle JSON decode errors
            print(f"❌ JSON decode error: {e}")
            return []
    
    def delete(self, table: str, filters: Optional[Dict] = None) -> bool:
        """DELETE query - מבוסס על HTTP DELETE request"""
        try:
            url = f"{self.url}/rest/v1/{table}"
            
            # בניית query parameters
            params = {}
            if filters:
                for key, value in filters.items():
                    params[key] = f"eq.{value}" if not str(value).startswith('eq.') else value
            
            response = requests.delete(url, headers=self.headers, params=params)
            response.raise_for_status()
            return True
        
        except requests.exceptions.HTTPError as e:
            print(f"❌ DELETE error: {e}")
            return False
    
    def execute_sql(self, query: str) -> Any:
        """Execute raw SQL query"""
        try:
            url = f"{self.url}/rest/v1/rpc/execute_sql"
            
            # Note: Supabase REST API לא תומך ב-raw SQL ישירות
            # צריך להשתמש ב-PostgREST queries או ב-Supabase Edge Functions
            raise NotImplementedError("Use Supabase Edge Functions for raw SQL")
        
        except Exception as e:
            print(f"❌ SQL execution error: {e}")
            raise


def get_supabase_client() -> SupabaseClient:
    """קבל Supabase client instance"""
    return SupabaseClient()

