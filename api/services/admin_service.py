"""
Admin Service
Handles admin operations: user management, analytics, activity tracking.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from ..services.supabase_service import supabase

logger = logging.getLogger(__name__)


class AdminService:
    """Service for admin operations."""
    
    def __init__(self):
        self.db = supabase
    
    # ==================== USER MANAGEMENT ====================
    
    async def get_users(
        self,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        tier: Optional[str] = None,
        role: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get paginated list of users with filters.
        
        Args:
            page: Page number (1-indexed)
            limit: Items per page
            search: Search term (email, name)
            tier: Filter by tier (free/pro/enterprise)
            role: Filter by role (researcher/clinician/admin)
            status: Filter by status (active/suspended)
            
        Returns:
            {
                "items": [...],
                "total": 123,
                "page": 1,
                "limit": 20,
                "pages": 7
            }
        """
        if not self.db.enabled:
            return {"items": [], "total": 0, "page": page, "limit": limit, "pages": 0}
        
        try:
            # Build query conditions
            conditions = {}
            if tier:
                conditions["tier"] = tier
            if role:
                conditions["role"] = role
            if status:
                conditions["status"] = status
            
            # Get users
            offset = (page - 1) * limit
            users = await self.db.select("user_profiles", conditions, limit=limit)
            
            # Apply search filter (client-side for now, can be optimized with SQL)
            if search:
                search_lower = search.lower()
                users = [
                    u for u in users
                    if search_lower in u.get("email", "").lower()
                    or search_lower in (u.get("full_name") or "").lower()
                ]
            
            # Get total count
            total = len(users)  # Simplified - should use COUNT query in production
            
            return {
                "items": users,
                "total": total,
                "page": page,
                "limit": limit,
                "pages": (total + limit - 1) // limit
            }
            
        except Exception as e:
            logger.error(f"Failed to get users: {e}")
            return {"items": [], "total": 0, "page": page, "limit": limit, "pages": 0}
    
    async def get_user_details(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get complete user details including usage stats.
        
        Returns:
            {
                "profile": {...},
                "subscription": {...},
                "quotas": {...},
                "usage_stats": {
                    "total_requests": 123,
                    "sessions_count": 45,
                    "analyses_count": 67,
                    "last_active": "2024-12-XX"
                }
            }
        """
        if not self.db.enabled:
            return None
        
        try:
            # Get user profile
            profiles = await self.db.select("user_profiles", {"id": user_id}, limit=1)
            if not profiles or len(profiles) == 0:
                return None
            
            profile = profiles[0]
            
            # Get subscription
            subscriptions = await self.db.select("user_subscriptions", {"user_id": user_id}, limit=1)
            subscription = subscriptions[0] if subscriptions else None
            
            # Get quotas
            quotas = await self.db.select("user_quotas", {"user_id": user_id}, limit=1)
            quota = quotas[0] if quotas else None
            
            # Get usage stats
            usage_stats = await self._get_user_usage_stats(user_id)
            
            return {
                "profile": profile,
                "subscription": subscription,
                "quotas": quota,
                "usage_stats": usage_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get user details: {e}")
            return None
    
    async def update_user(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update user profile, tier, role, or quotas.
        
        Args:
            user_id: User UUID
            updates: Dictionary of fields to update
                - profile fields (full_name, institution, etc.)
                - tier (free/pro/enterprise)
                - role (researcher/clinician/admin)
                - quotas (variant_analyses_limit, etc.)
        """
        if not self.db.enabled:
            return False
        
        try:
            # Separate profile updates from quota updates
            profile_updates = {}
            quota_updates = {}
            
            profile_fields = ["full_name", "institution", "role", "tier", "bio", "country", "timezone"]
            quota_fields = [
                "variant_analyses_limit", "variant_analyses_used",
                "drug_queries_limit", "drug_queries_used",
                "food_queries_limit", "food_queries_used",
                "clinical_trials_limit", "clinical_trials_used"
            ]
            
            for key, value in updates.items():
                if key in profile_fields:
                    profile_updates[key] = value
                elif key in quota_fields:
                    quota_updates[key] = value
            
            # Update profile
            if profile_updates:
                await self.db.update("user_profiles", profile_updates, {"id": user_id})
            
            # Update quotas
            if quota_updates:
                await self.db.update("user_quotas", quota_updates, {"user_id": user_id})
            
            # If tier changed, update quotas tier too
            if "tier" in profile_updates:
                await self.db.update("user_quotas", {"tier": profile_updates["tier"]}, {"user_id": user_id})
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update user: {e}")
            return False
    
    # ==================== ANALYTICS ====================
    
    async def get_analytics_overview(self, period: str = "7d") -> Dict[str, Any]:
        """
        Get dashboard overview analytics.
        
        Args:
            period: Time period (7d, 30d, 90d, all)
            
        Returns:
            {
                "total_users": 1234,
                "active_users": 856,
                "new_users": 45,
                "tier_breakdown": {"free": 1000, "pro": 200, "enterprise": 34},
                "total_requests": 45678,
                "requests_today": 1234,
                "quota_usage": {...}
            }
        """
        if not self.db.enabled:
            return {}
        
        try:
            # Get total users
            all_users = await self.db.select("user_profiles", {}, limit=10000)
            total_users = len(all_users)
            
            # Tier breakdown
            tier_breakdown = {"free": 0, "pro": 0, "enterprise": 0}
            for user in all_users:
                tier = user.get("tier", "free")
                tier_breakdown[tier] = tier_breakdown.get(tier, 0) + 1
            
            # Active users (users with activity in last 7 days)
            # This would require querying usage_logs - simplified for now
            active_users = total_users  # Placeholder
            
            # New users (in specified period)
            days = int(period.replace("d", "")) if period.endswith("d") else 7
            cutoff_date = datetime.now() - timedelta(days=days)
            # Simplified - would need to query created_at timestamps
            new_users = 0
            
            # Total requests (from usage_logs)
            usage_logs = await self.db.select("usage_logs", {}, limit=10000)
            total_requests = len(usage_logs)
            
            # Requests today (simplified)
            requests_today = 0
            
            return {
                "total_users": total_users,
                "active_users": active_users,
                "new_users": new_users,
                "tier_breakdown": tier_breakdown,
                "total_requests": total_requests,
                "requests_today": requests_today,
                "period": period
            }
            
        except Exception as e:
            logger.error(f"Failed to get analytics overview: {e}")
            return {}
    
    async def get_usage_trends(self, period: str = "7d") -> List[Dict[str, Any]]:
        """
        Get usage trends over time.
        
        Returns:
            [
                {"date": "2024-12-01", "requests": 1234},
                {"date": "2024-12-02", "requests": 1456},
                ...
            ]
        """
        if not self.db.enabled:
            return []
        
        try:
            # Get usage logs
            usage_logs = await self.db.select("usage_logs", {}, limit=10000)
            
            # Group by date (simplified - would need proper date grouping in SQL)
            # For now, return placeholder
            return []
            
        except Exception as e:
            logger.error(f"Failed to get usage trends: {e}")
            return []
    
    # ==================== ACTIVITY LOGS ====================
    
    async def get_usage_logs(
        self,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        date_from: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get usage logs with filters.
        
        Returns:
            List of usage log entries
        """
        if not self.db.enabled:
            return []
        
        try:
            conditions = {}
            if user_id:
                conditions["user_id"] = user_id
            if endpoint:
                conditions["endpoint"] = endpoint
            
            logs = await self.db.select("usage_logs", conditions, limit=limit)
            return logs
            
        except Exception as e:
            logger.error(f"Failed to get usage logs: {e}")
            return []
    
    async def get_session_activity(self, user_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent session activity."""
        if not self.db.enabled:
            return []
        
        try:
            conditions = {}
            if user_id:
                conditions["user_id"] = user_id
            
            sessions = await self.db.select("user_sessions", conditions, limit=limit)
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to get session activity: {e}")
            return []
    
    # ==================== HELPER METHODS ====================
    
    async def _get_user_usage_stats(self, user_id: str) -> Dict[str, Any]:
        """Get usage statistics for a user."""
        try:
            # Get usage logs count
            usage_logs = await self.db.select("usage_logs", {"user_id": user_id}, limit=10000)
            total_requests = len(usage_logs)
            
            # Get sessions count
            sessions = await self.db.select("user_sessions", {"user_id": user_id}, limit=10000)
            sessions_count = len(sessions)
            
            # Get analyses count
            analyses = await self.db.select("analysis_history", {"user_id": user_id}, limit=10000)
            analyses_count = len(analyses)
            
            # Get last active (from most recent session or usage log)
            last_active = None
            if sessions:
                last_session = max(sessions, key=lambda s: s.get("updated_at", ""))
                last_active = last_session.get("updated_at")
            
            return {
                "total_requests": total_requests,
                "sessions_count": sessions_count,
                "analyses_count": analyses_count,
                "last_active": last_active
            }
            
        except Exception as e:
            logger.error(f"Failed to get user usage stats: {e}")
            return {
                "total_requests": 0,
                "sessions_count": 0,
                "analyses_count": 0,
                "last_active": None
            }








