"""
Feature Flag Service
Manages tier-based feature flags and user feature access.
"""
import logging
from typing import Dict, List, Optional
from ..services.supabase_service import supabase

logger = logging.getLogger(__name__)


class FeatureFlagService:
    """
    Service for managing feature flags based on user tiers.
    
    Tier-based features:
    - Free: variant_analysis, drug_efficacy, food_validator
    - Pro: All free features + sae_features, clinical_trials, fusion_engine, pdf_export
    - Enterprise: All pro features + cohort_lab, crispr_design, api_access
    """
    
    TIER_FEATURES = {
        "free": [
            "variant_analysis",
            "drug_efficacy",
            "food_validator"
        ],
        "pro": [
            "variant_analysis",
            "drug_efficacy",
            "food_validator",
            "sae_features",
            "clinical_trials",
            "fusion_engine",
            "pdf_export"
        ],
        "enterprise": [
            "variant_analysis",
            "drug_efficacy",
            "food_validator",
            "sae_features",
            "clinical_trials",
            "fusion_engine",
            "pdf_export",
            "cohort_lab",
            "crispr_design",
            "api_access"
        ]
    }
    
    def __init__(self):
        self.db = supabase
    
    async def get_user_features(self, user_id: str) -> Dict[str, bool]:
        """
        Get all features enabled for a user.
        
        Returns:
            {
                "variant_analysis": True,
                "drug_efficacy": True,
                "sae_features": False,
                ...
            }
        """
        if not self.db.enabled:
            # Return free tier features if Supabase not enabled
            return {f: True for f in self.TIER_FEATURES["free"]}
        
        try:
            # Get user tier
            profiles = await self.db.select("user_profiles", {"id": user_id}, limit=1)
            
            if not profiles or len(profiles) == 0:
                logger.warning(f"User {user_id} not found, using free tier")
                tier = "free"
            else:
                tier = profiles[0].get("tier", "free")
            
            # Get tier-based features
            tier_features = self.TIER_FEATURES.get(tier, self.TIER_FEATURES["free"])
            features = {f: True for f in tier_features}
            
            # Get custom overrides from user_feature_flags table
            flags = await self.db.select("user_feature_flags", {"user_id": user_id}, limit=1000)
            
            for flag in flags:
                feature_name = flag.get("feature_name")
                enabled = flag.get("enabled", False)
                features[feature_name] = enabled
            
            return features
            
        except Exception as e:
            logger.error(f"Failed to get user features: {e}")
            # Return free tier features on error
            return {f: True for f in self.TIER_FEATURES["free"]}
    
    async def has_feature(self, user_id: str, feature_name: str) -> bool:
        """
        Check if user has access to a specific feature.
        
        Args:
            user_id: User UUID
            feature_name: Feature name to check
            
        Returns:
            True if user has feature, False otherwise
        """
        features = await self.get_user_features(user_id)
        return features.get(feature_name, False)
    
    async def enable_feature(self, user_id: str, feature_name: str) -> bool:
        """
        Enable a feature for a user (custom override).
        
        Args:
            user_id: User UUID
            feature_name: Feature name to enable
            
        Returns:
            True if successful, False otherwise
        """
        if not self.db.enabled:
            return False
        
        try:
            flag_data = {
                "user_id": user_id,
                "feature_name": feature_name,
                "enabled": True
            }
            
            # Use upsert (insert or update)
            existing = await self.db.select("user_feature_flags", {"user_id": user_id, "feature_name": feature_name}, limit=1)
            
            if existing and len(existing) > 0:
                # Update existing
                success = await self.db.update("user_feature_flags", {"enabled": True}, {"user_id": user_id, "feature_name": feature_name})
            else:
                # Insert new
                await self.db.insert("user_feature_flags", [flag_data])
                success = True
            
            return success
            
        except Exception as e:
            logger.error(f"Error enabling feature: {e}")
            return False
    
    async def disable_feature(self, user_id: str, feature_name: str) -> bool:
        """
        Disable a feature for a user (custom override).
        
        Args:
            user_id: User UUID
            feature_name: Feature name to disable
            
        Returns:
            True if successful, False otherwise
        """
        if not self.db.enabled:
            return False
        
        try:
            existing = await self.db.select("user_feature_flags", {"user_id": user_id, "feature_name": feature_name}, limit=1)
            
            if existing and len(existing) > 0:
                # Update existing
                success = await self.db.update("user_feature_flags", {"enabled": False}, {"user_id": user_id, "feature_name": feature_name})
            else:
                # Insert new with enabled=False
                flag_data = {
                    "user_id": user_id,
                    "feature_name": feature_name,
                    "enabled": False
                }
                await self.db.insert("user_feature_flags", [flag_data])
                success = True
            
            return success
            
        except Exception as e:
            logger.error(f"Error disabling feature: {e}")
            return False



































