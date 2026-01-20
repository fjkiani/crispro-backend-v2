"""
Quota Service
Manages user quotas and usage tracking for tier-based limits.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from ..services.supabase_service import supabase

logger = logging.getLogger(__name__)


class QuotaService:
    """
    Service for managing user quotas and usage tracking.
    
    Tier-based quota limits:
    - Free: 10 variant analyses, 5 drug queries, 3 food queries, 0 clinical trials
    - Pro: 100 variant analyses, unlimited drug/food queries, 50 clinical trials
    - Enterprise: Unlimited for all
    """
    
    QUOTA_LIMITS = {
        "free": {
            "variant_analyses_limit": 10,
            "drug_queries_limit": 5,
            "food_queries_limit": 3,
            "clinical_trials_limit": 0
        },
        "pro": {
            "variant_analyses_limit": 100,
            "drug_queries_limit": -1,  # -1 = unlimited
            "food_queries_limit": -1,
            "clinical_trials_limit": 50
        },
        "enterprise": {
            "variant_analyses_limit": -1,
            "drug_queries_limit": -1,
            "food_queries_limit": -1,
            "clinical_trials_limit": -1
        }
    }
    
    def __init__(self):
        self.db = supabase
    
    async def get_user_quotas(self, user_id: str) -> Dict[str, Any]:
        """
        Get current quota usage for user.
        
        Returns:
            {
                "tier": "free",
                "variant_analyses": {"limit": 10, "used": 3, "remaining": 7},
                "drug_queries": {"limit": 5, "used": 2, "remaining": 3},
                "food_queries": {"limit": 3, "used": 1, "remaining": 2},
                "clinical_trials": {"limit": 0, "used": 0, "remaining": 0},
                "period_end": "2024-01-01T00:00:00Z"
            }
        """
        if not self.db.enabled:
            # Return default free tier quotas if Supabase not enabled
            return self._get_default_quotas("free")
        
        try:
            # Get user tier and quotas
            profiles = await self.db.select("user_profiles", {"id": user_id}, limit=1)
            if not profiles or len(profiles) == 0:
                return self._get_default_quotas("free")
            
            tier = profiles[0].get("tier", "free")
            
            quotas = await self.db.select("user_quotas", {"user_id": user_id}, limit=1)
            if not quotas or len(quotas) == 0:
                # Create default quotas
                await self._create_default_quotas(user_id, tier)
                quotas = await self.db.select("user_quotas", {"user_id": user_id}, limit=1)
            
            quota = quotas[0] if quotas else {}
            
            # Check if period has ended, reset if needed
            await self.reset_quotas_if_needed(user_id)
            
            # Re-fetch after potential reset
            quotas = await self.db.select("user_quotas", {"user_id": user_id}, limit=1)
            quota = quotas[0] if quotas else {}
            
            return {
                "tier": tier,
                "variant_analyses": {
                    "limit": quota.get("variant_analyses_limit", 10),
                    "used": quota.get("variant_analyses_used", 0),
                    "remaining": self._calculate_remaining(
                        quota.get("variant_analyses_limit", 10),
                        quota.get("variant_analyses_used", 0)
                    )
                },
                "drug_queries": {
                    "limit": quota.get("drug_queries_limit", 5),
                    "used": quota.get("drug_queries_used", 0),
                    "remaining": self._calculate_remaining(
                        quota.get("drug_queries_limit", 5),
                        quota.get("drug_queries_used", 0)
                    )
                },
                "food_queries": {
                    "limit": quota.get("food_queries_limit", 3),
                    "used": quota.get("food_queries_used", 0),
                    "remaining": self._calculate_remaining(
                        quota.get("food_queries_limit", 3),
                        quota.get("food_queries_used", 0)
                    )
                },
                "clinical_trials": {
                    "limit": quota.get("clinical_trials_limit", 0),
                    "used": quota.get("clinical_trials_used", 0),
                    "remaining": self._calculate_remaining(
                        quota.get("clinical_trials_limit", 0),
                        quota.get("clinical_trials_used", 0)
                    )
                },
                "period_end": quota.get("period_end")
            }
            
        except Exception as e:
            logger.error(f"Failed to get user quotas: {e}")
            return self._get_default_quotas("free")
    
    def _calculate_remaining(self, limit: int, used: int) -> int:
        """Calculate remaining quota (-1 means unlimited)."""
        if limit == -1:
            return -1
        return max(0, limit - used)
    
    def _get_default_quotas(self, tier: str) -> Dict[str, Any]:
        """Get default quota structure for a tier."""
        limits = self.QUOTA_LIMITS.get(tier, self.QUOTA_LIMITS["free"])
        return {
            "tier": tier,
            "variant_analyses": {"limit": limits["variant_analyses_limit"], "used": 0, "remaining": limits["variant_analyses_limit"] if limits["variant_analyses_limit"] != -1 else -1},
            "drug_queries": {"limit": limits["drug_queries_limit"], "used": 0, "remaining": limits["drug_queries_limit"] if limits["drug_queries_limit"] != -1 else -1},
            "food_queries": {"limit": limits["food_queries_limit"], "used": 0, "remaining": limits["food_queries_limit"] if limits["food_queries_limit"] != -1 else -1},
            "clinical_trials": {"limit": limits["clinical_trials_limit"], "used": 0, "remaining": limits["clinical_trials_limit"] if limits["clinical_trials_limit"] != -1 else -1},
            "period_end": None
        }
    
    async def _create_default_quotas(self, user_id: str, tier: str):
        """Create default quotas for a user."""
        if not self.db.enabled:
            return
        
        limits = self.QUOTA_LIMITS.get(tier, self.QUOTA_LIMITS["free"])
        period_end = datetime.now(timezone.utc) + timedelta(days=30)
        
        quota_data = {
            "user_id": user_id,
            "tier": tier,
            "variant_analyses_limit": limits["variant_analyses_limit"],
            "variant_analyses_used": 0,
            "drug_queries_limit": limits["drug_queries_limit"],
            "drug_queries_used": 0,
            "food_queries_limit": limits["food_queries_limit"],
            "food_queries_used": 0,
            "clinical_trials_limit": limits["clinical_trials_limit"],
            "clinical_trials_used": 0,
            "period_start": datetime.now(timezone.utc).isoformat(),
            "period_end": period_end.isoformat()
        }
        
        try:
            await self.db.insert("user_quotas", [quota_data])
        except Exception as e:
            logger.error(f"Failed to create default quotas: {e}")
    
    async def check_quota(self, user_id: str, quota_type: str) -> bool:
        """
        Check if user has quota remaining for an operation.
        
        Args:
            user_id: User UUID
            quota_type: One of 'variant_analyses', 'drug_queries', 'food_queries', 'clinical_trials'
            
        Returns:
            True if user has quota, False otherwise
        """
        quotas = await self.get_user_quotas(user_id)
        
        quota_map = {
            "variant_analyses": "variant_analyses",
            "drug_queries": "drug_queries",
            "food_queries": "food_queries",
            "clinical_trials": "clinical_trials"
        }
        
        quota_key = quota_map.get(quota_type)
        if not quota_key or quota_key not in quotas:
            return False
        
        quota = quotas[quota_key]
        
        # -1 means unlimited
        if quota["limit"] == -1:
            return True
        
        return quota["remaining"] > 0
    
    async def increment_usage(self, user_id: str, quota_type: str) -> bool:
        """Increment usage counter for a quota type."""
        if not self.db.enabled:
            return True  # Allow if Supabase not enabled
        
        column_map = {
            "variant_analyses": "variant_analyses_used",
            "drug_queries": "drug_queries_used",
            "food_queries": "food_queries_used",
            "clinical_trials": "clinical_trials_used"
        }
        
        column = column_map.get(quota_type)
        if not column:
            logger.error(f"Invalid quota type: {quota_type}")
            return False
        
        try:
            # Get current usage
            quotas = await self.db.select("user_quotas", {"user_id": user_id}, limit=1)
            if not quotas or len(quotas) == 0:
                # Create quotas if they don't exist
                profiles = await self.db.select("user_profiles", {"id": user_id}, limit=1)
                tier = profiles[0].get("tier", "free") if profiles else "free"
                await self._create_default_quotas(user_id, tier)
                quotas = await self.db.select("user_quotas", {"user_id": user_id}, limit=1)
            
            if not quotas:
                return False
            
            current_used = quotas[0].get(column, 0)
            
            # Increment
            update_data = {
                column: current_used + 1,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            success = await self.db.update("user_quotas", update_data, {"user_id": user_id})
            return success
            
        except Exception as e:
            logger.error(f"Error incrementing usage: {e}")
            return False
    
    async def reset_quotas_if_needed(self, user_id: str) -> bool:
        """Reset quotas if billing period has ended."""
        if not self.db.enabled:
            return False
        
        try:
            quotas = await self.db.select("user_quotas", {"user_id": user_id}, limit=1)
            if not quotas or len(quotas) == 0:
                return False
            
            quota = quotas[0]
            period_end_str = quota.get("period_end")
            
            if not period_end_str:
                return False
            
            # Parse period_end
            if isinstance(period_end_str, str):
                period_end = datetime.fromisoformat(period_end_str.replace("Z", "+00:00"))
            else:
                period_end = period_end_str
            
            # Check if period has ended
            now = datetime.now(timezone.utc)
            if period_end < now:
                # Reset quotas
                profiles = await self.db.select("user_profiles", {"id": user_id}, limit=1)
                tier = profiles[0].get("tier", "free") if profiles else "free"
                limits = self.QUOTA_LIMITS.get(tier, self.QUOTA_LIMITS["free"])
                
                new_period_end = now + timedelta(days=30)
                
                update_data = {
                    "variant_analyses_used": 0,
                    "drug_queries_used": 0,
                    "food_queries_used": 0,
                    "clinical_trials_used": 0,
                    "period_start": now.isoformat(),
                    "period_end": new_period_end.isoformat(),
                    "updated_at": now.isoformat()
                }
                
                # Update limits if tier changed
                if quota.get("tier") != tier:
                    update_data.update({
                        "tier": tier,
                        "variant_analyses_limit": limits["variant_analyses_limit"],
                        "drug_queries_limit": limits["drug_queries_limit"],
                        "food_queries_limit": limits["food_queries_limit"],
                        "clinical_trials_limit": limits["clinical_trials_limit"]
                    })
                
                success = await self.db.update("user_quotas", update_data, {"user_id": user_id})
                return success
            
            return False
            
        except Exception as e:
            logger.error(f"Error resetting quotas: {e}")
            return False



































