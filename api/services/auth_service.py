"""
Authentication Service
Handles user profile operations and Supabase Auth integration.
"""
import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Try to import supabase, but handle gracefully if not installed
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None

load_dotenv()

logger = logging.getLogger(__name__)

# Initialize Supabase client for Auth operations
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")

_supabase_client: Optional[Client] = None

def get_supabase_auth_client() -> Optional[Client]:
    """Get Supabase Auth client (singleton)."""
    global _supabase_client
    
    if not SUPABASE_AVAILABLE:
        logger.warning("⚠️ supabase package not installed. Run: pip install supabase")
        return None
    
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            logger.warning("⚠️ Supabase Auth not configured (SUPABASE_URL or SUPABASE_ANON_KEY missing)")
            return None
        
        try:
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            logger.info("✅ Supabase Auth client initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Supabase Auth client: {e}")
            return None
    
    return _supabase_client


class AuthService:
    """Service for authentication and user profile operations."""
    
    def __init__(self):
        self.supabase = get_supabase_auth_client()
        # Use existing supabase_service for database operations
        from api.services.supabase_service import supabase as db_service
        self.db = db_service
    
    async def signup(self, email: str, password: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Sign up a new user via Supabase Auth.
        
        Args:
            email: User email
            password: User password
            metadata: Optional user metadata (full_name, institution, role)
            
        Returns:
            {
                "user_id": "uuid",
                "email": "user@example.com",
                "session": {...},
                "profile_created": True
            }
        """
        if not self.supabase:
            raise ValueError("Supabase Auth not configured")
        
        try:
            # Sign up via Supabase Auth
            response = self.supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": metadata or {}
                }
            })
            
            if not response.user:
                raise ValueError("Signup failed: no user returned")
            
            user_id = response.user.id
            user_email = response.user.email
            
            # Create user profile in database
            profile_created = await self.create_user_profile(
                user_id=user_id,
                email=user_email,
                metadata=metadata
            )
            
            return {
                "user_id": user_id,
                "email": user_email,
                "session": {
                    "access_token": response.session.access_token if response.session else None,
                    "refresh_token": response.session.refresh_token if response.session else None,
                    "expires_at": response.session.expires_at if response.session else None,
                },
                "profile_created": profile_created,
                "email_confirmed": response.user.email_confirmed_at is not None
            }
            
        except Exception as e:
            logger.error(f"Signup error: {e}")
            raise ValueError(f"Signup failed: {str(e)}")
    
    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """
        Log in user via Supabase Auth.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            {
                "user_id": "uuid",
                "email": "user@example.com",
                "session": {...},
                "profile": {...}
            }
        """
        if not self.supabase:
            raise ValueError("Supabase Auth not configured")
        
        try:
            # Sign in via Supabase Auth
            response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if not response.user:
                raise ValueError("Login failed: no user returned")
            
            user_id = response.user.id
            
            # Get user profile
            profile = await self.get_user_profile(user_id)
            
            return {
                "user_id": user_id,
                "email": response.user.email,
                "session": {
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_at": response.session.expires_at,
                },
                "profile": profile
            }
            
        except Exception as e:
            logger.error(f"Login error: {e}")
            raise ValueError(f"Login failed: {str(e)}")
    
    async def logout(self, access_token: str) -> bool:
        """
        Log out user (revoke session).
        
        Args:
            access_token: Current access token
            
        Returns:
            True if logout successful
        """
        if not self.supabase:
            return False
        
        try:
            # Set session for logout
            self.supabase.auth.set_session(access_token, "")
            self.supabase.auth.sign_out()
            return True
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile from database.
        
        Args:
            user_id: User UUID
            
        Returns:
            User profile dict or None
        """
        if not self.db.enabled:
            return None
        
        try:
            profiles = await self.db.select("user_profiles", {"id": user_id}, limit=1)
            if profiles and len(profiles) > 0:
                return profiles[0]
            return None
        except Exception as e:
            logger.error(f"Failed to get user profile: {e}")
            return None
    
    async def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update user profile.
        
        Args:
            user_id: User UUID
            updates: Dictionary of fields to update
            
        Returns:
            True if update successful
        """
        if not self.db.enabled:
            return False
        
        try:
            # Remove None values
            updates = {k: v for k, v in updates.items() if v is not None}
            
            if not updates:
                return True
            
            success = await self.db.update("user_profiles", updates, {"id": user_id})
            if not success:
                logger.warning(f"Failed to update user profile {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update user profile: {e}")
            return False
    
    async def create_user_profile(self, user_id: str, email: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Create user profile and default quotas on signup.
        
        Args:
            user_id: User UUID from Supabase Auth
            email: User email
            metadata: Optional metadata (full_name, institution, role)
            
        Returns:
            True if profile created successfully
        """
        if not self.db.enabled:
            logger.warning("Supabase not enabled, skipping profile creation")
            return False
        
        try:
            # Create user profile
            profile_data = {
                "id": user_id,
                "email": email,
                "tier": "free",
                "role": metadata.get("role", "researcher") if metadata else "researcher",
                "institution": metadata.get("institution") if metadata else None,
                "full_name": metadata.get("full_name") if metadata else None,
            }
            
            await self.db.insert("user_profiles", [profile_data])
            
            # Create default quotas
            quota_data = {
                "user_id": user_id,
                "tier": "free",
                "variant_analyses_limit": 10,
                "variant_analyses_used": 0,
                "drug_queries_limit": 5,
                "drug_queries_used": 0,
                "food_queries_limit": 3,
                "food_queries_used": 0,
                "clinical_trials_limit": 0,
                "clinical_trials_used": 0,
            }
            
            await self.db.insert("user_quotas", [quota_data])
            
            logger.info(f"✅ Created profile and quotas for user {user_id[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create user profile: {e}")
            # Check if profile already exists (might be created by trigger)
            existing = await self.get_user_profile(user_id)
            return existing is not None

