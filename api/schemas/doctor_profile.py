"""
Doctor/Clinician Profile Pydantic Models
Data models for doctor/clinician profile CRUD operations.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import date


class DoctorProfileBase(BaseModel):
    """Base doctor profile model with common fields."""
    full_name: Optional[str] = Field(None, max_length=255, description="Doctor's full name")
    specialty: Optional[str] = Field(None, max_length=100, description="Medical specialty (e.g., 'Medical Oncology', 'Gynecologic Oncology')")
    sub_specialty: Optional[str] = Field(None, max_length=100, description="Sub-specialty if applicable")
    
    # Professional Information
    npi: Optional[str] = Field(None, max_length=10, description="National Provider Identifier (10 digits)")
    license_number: Optional[str] = Field(None, max_length=50, description="State medical license number")
    license_state: Optional[str] = Field(None, max_length=2, description="State abbreviation (e.g., 'NY', 'CA')")
    
    # Institution/Organization
    institution_name: Optional[str] = Field(None, max_length=255, description="Hospital or clinic name")
    institution_type: Optional[str] = Field(None, max_length=50, description="Type: 'Academic', 'Community', 'Private Practice', etc.")
    institution_city: Optional[str] = Field(None, max_length=100, description="City where institution is located")
    institution_state: Optional[str] = Field(None, max_length=2, description="State abbreviation")
    
    # Clinical Focus Areas
    primary_cancer_types: Optional[List[str]] = Field(
        default_factory=list,
        description="List of primary cancer types treated (e.g., ['ovarian', 'breast', 'lung'])"
    )
    clinical_trials_enrollment: Optional[bool] = Field(None, description="Whether doctor enrolls patients in clinical trials")
    research_interests: Optional[List[str]] = Field(
        default_factory=list,
        description="Research interests or areas (e.g., ['PARP inhibitors', 'IO therapy', 'precision medicine'])"
    )
    
    # Preferences
    preferred_communication: Optional[str] = Field(None, max_length=50, description="Preferred communication method")
    notification_preferences: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Notification preferences (email, sms, etc.)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "full_name": "Dr. Jane Smith",
                "specialty": "Medical Oncology",
                "sub_specialty": "Gynecologic Oncology",
                "npi": "1234567890",
                "license_number": "MD12345",
                "license_state": "NY",
                "institution_name": "Memorial Sloan Kettering Cancer Center",
                "institution_type": "Academic",
                "institution_city": "New York",
                "institution_state": "NY",
                "primary_cancer_types": ["ovarian", "breast"],
                "clinical_trials_enrollment": True,
                "research_interests": ["PARP inhibitors", "precision medicine"]
            }
        }
    }


class DoctorProfileCreate(DoctorProfileBase):
    """Model for creating a new doctor profile."""
    user_id: str = Field(..., description="User ID (from auth.users)")


class DoctorProfileUpdate(BaseModel):
    """Model for updating doctor profile (all fields optional)."""
    full_name: Optional[str] = None
    specialty: Optional[str] = None
    sub_specialty: Optional[str] = None
    npi: Optional[str] = None
    license_number: Optional[str] = None
    license_state: Optional[str] = None
    institution_name: Optional[str] = None
    institution_type: Optional[str] = None
    institution_city: Optional[str] = None
    institution_state: Optional[str] = None
    primary_cancer_types: Optional[List[str]] = None
    clinical_trials_enrollment: Optional[bool] = None
    research_interests: Optional[List[str]] = None
    preferred_communication: Optional[str] = None
    notification_preferences: Optional[Dict[str, Any]] = None

    @field_validator('npi')
    @classmethod
    def validate_npi(cls, v):
        """Validate NPI is 10 digits if provided."""
        if v and (not v.isdigit() or len(v) != 10):
            raise ValueError("NPI must be 10 digits")
        return v


class DoctorProfileResponse(DoctorProfileBase):
    """Model for doctor profile API responses."""
    user_id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
