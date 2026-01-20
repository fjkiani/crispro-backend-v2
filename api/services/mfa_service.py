"""
MFA (Multi-Factor Authentication) Service

Purpose: Handle MFA enrollment, verification, and management for users.
HIPAA Requirement: MFA must be enabled for users accessing PHI.
"""

import os
import secrets
import io
import base64
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from supabase import create_client, Client

# Optional MFA dependencies - backend should work without MFA
try:
    import pyotp
    PYOTP_AVAILABLE = True
except ImportError:
    PYOTP_AVAILABLE = False
    pyotp = None

try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False
    qrcode = None

from ..services.auth_service import AuthService


class MFAService:
    """
    Service for managing Multi-Factor Authentication (MFA).
    
    Uses TOTP (Time-based One-Time Password) via pyotp library.
    Generates QR codes for authenticator app enrollment.
    """

    def __init__(self):
        self.supabase_url: str = os.environ.get("SUPABASE_URL")
        self.supabase_key: str = os.environ.get("SUPABASE_SERVICE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment variables.")
        
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        self.auth_service = AuthService()
        
        # Check if MFA dependencies are available
        if not PYOTP_AVAILABLE:
            import logging
            logging.warning("⚠️ pyotp not installed - MFA features will be disabled. Install with: pip install pyotp")
        if not QRCODE_AVAILABLE:
            import logging
            logging.warning("⚠️ qrcode not installed - MFA QR codes will be disabled. Install with: pip install qrcode[pil]")

    def generate_mfa_secret(self, user_id: str, user_email: str) -> Dict[str, Any]:
        """
        Generate a new MFA secret for a user.
        
        Args:
            user_id: User's unique identifier
            user_email: User's email address (for QR code label)
            
        Returns:
            Dict with:
                "secret": "BASE32_SECRET",
                "qr_code_url": "data:image/png;base64,...",
                "backup_codes": ["code1", "code2", ...]
        
        Raises:
            RuntimeError: If pyotp is not installed
        """
        if not PYOTP_AVAILABLE:
            raise RuntimeError("MFA not available: pyotp is not installed. Install with: pip install pyotp")
        # Generate a random secret (32 characters, base32 encoded)
        secret = pyotp.random_base32()
        
        # Create TOTP object
        totp = pyotp.TOTP(secret)
        
        # Generate provisioning URI for QR code
        issuer = "CrisPRO.ai"  # Your app name
        provisioning_uri = totp.provisioning_uri(
            name=user_email,
            issuer_name=issuer
        )
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
        qr_code_url = f"data:image/png;base64,{qr_code_base64}"
        
        # Generate backup codes (10 codes, 8 characters each)
        backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]
        
        # Store secret and backup codes in database (encrypted at application level in production)
        # For now, we'll store them directly (in production, encrypt before storing)
        try:
            self.supabase.table("user_profiles").update({
                "mfa_secret": secret,  # TODO: Encrypt this in production
                "mfa_backup_codes": backup_codes
            }).eq("id", user_id).execute()
        except Exception as e:
            raise ValueError(f"Failed to store MFA secret: {e}")
        
        return {
            "secret": secret,
            "qr_code_url": qr_code_url,
            "backup_codes": backup_codes,
            "provisioning_uri": provisioning_uri
        }

    def verify_mfa_code(self, user_id: str, code: str, use_backup: bool = False) -> bool:
        """
        Verify an MFA code (TOTP or backup code) for a user.
        
        Args:
            user_id: User's unique identifier
            code: 6-digit TOTP code or backup code
            use_backup: Whether to check backup codes instead of TOTP
            
        Returns:
            True if code is valid, False otherwise
        """
        try:
            # Get user's MFA secret
            user_response = self.supabase.table("user_profiles").select("mfa_secret, mfa_backup_codes").eq("id", user_id).execute()
            
            if not user_response.data:
                return False
            
            user_data = user_response.data[0]
            mfa_secret = user_data.get("mfa_secret")
            backup_codes = user_data.get("mfa_backup_codes", [])
            
            if not mfa_secret:
                return False
            
            if use_backup:
                # Verify backup code
                if code in backup_codes:
                    # Remove used backup code
                    backup_codes.remove(code)
                    self.supabase.table("user_profiles").update({
                        "mfa_backup_codes": backup_codes
                    }).eq("id", user_id).execute()
                    return True
                return False
            else:
                # Verify TOTP code
                totp = pyotp.TOTP(mfa_secret)
                is_valid = totp.verify(code, valid_window=1)  # Allow 1 time step tolerance
                
                if is_valid:
                    # Update mfa_verified_at timestamp
                    self.supabase.table("user_profiles").update({
                        "mfa_verified_at": datetime.utcnow().isoformat()
                    }).eq("id", user_id).execute()
                
                return is_valid
                
        except Exception as e:
            print(f"Error verifying MFA code: {e}")
            return False

    async def enable_mfa(self, user_id: str, code: str) -> Dict[str, Any]:
        """
        Enable MFA for a user after verifying the initial code.
        
        Args:
            user_id: User's unique identifier
            code: 6-digit TOTP code from authenticator app
            
        Returns:
            {
                "success": True/False,
                "message": "MFA enabled successfully" or error message
            }
        """
        # Verify the code
        if not self.verify_mfa_code(user_id, code):
            return {
                "success": False,
                "message": "Invalid MFA code. Please check your authenticator app and try again."
            }
        
        # Enable MFA
        try:
            self.supabase.table("user_profiles").update({
                "mfa_enabled": True,
                "mfa_verified_at": datetime.utcnow().isoformat()
            }).eq("id", user_id).execute()
            
            return {
                "success": True,
                "message": "MFA enabled successfully."
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to enable MFA: {e}"
            }

    async def disable_mfa(self, user_id: str) -> Dict[str, Any]:
        """
        Disable MFA for a user.
        
        Args:
            user_id: User's unique identifier
            
        Returns:
            {
                "success": True/False,
                "message": "MFA disabled successfully" or error message
            }
        """
        try:
            self.supabase.table("user_profiles").update({
                "mfa_enabled": False,
                "mfa_secret": None,
                "mfa_backup_codes": None,
                "mfa_verified_at": None
            }).eq("id", user_id).execute()
            
            return {
                "success": True,
                "message": "MFA disabled successfully."
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to disable MFA: {e}"
            }

    def is_mfa_enabled(self, user_id: str) -> bool:
        """
        Check if MFA is enabled for a user.
        
        Args:
            user_id: User's unique identifier
            
        Returns:
            True if MFA is enabled, False otherwise
        """
        try:
            user_response = self.supabase.table("user_profiles").select("mfa_enabled").eq("id", user_id).execute()
            
            if not user_response.data:
                return False
            
            return user_response.data[0].get("mfa_enabled", False)
        except Exception as e:
            print(f"Error checking MFA status: {e}")
            return False

    def is_mfa_verified_recently(self, user_id: str, max_age_minutes: int = 30) -> bool:
        """
        Check if MFA was verified recently (within max_age_minutes).
        
        Args:
            user_id: User's unique identifier
            max_age_minutes: Maximum age of verification in minutes (default: 30)
            
        Returns:
            True if MFA was verified within max_age_minutes, False otherwise
        """
        try:
            user_response = self.supabase.table("user_profiles").select("mfa_verified_at").eq("id", user_id).execute()
            
            if not user_response.data:
                return False
            
            mfa_verified_at_str = user_response.data[0].get("mfa_verified_at")
            
            if not mfa_verified_at_str:
                return False
            
            mfa_verified_at = datetime.fromisoformat(mfa_verified_at_str.replace("Z", "+00:00"))
            age = datetime.utcnow() - mfa_verified_at.replace(tzinfo=None)
            
            return age.total_seconds() < (max_age_minutes * 60)
        except Exception as e:
            print(f"Error checking MFA verification recency: {e}")
            return False


# Dependency for FastAPI
_mfa_service: Optional[MFAService] = None

def get_mfa_service() -> MFAService:
    """Get MFA service singleton."""
    global _mfa_service
    if _mfa_service is None:
        _mfa_service = MFAService()
    return _mfa_service
