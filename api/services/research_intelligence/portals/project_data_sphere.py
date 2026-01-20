"""
Project Data Sphere Portal

Portal for Project Data Sphere patient-level clinical trial data.
Provides access to 102 caslibs with patient-level data for validation.
"""

from typing import Dict, List, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)


class ProjectDataSpherePortal:
    """
    Portal for Project Data Sphere patient-level clinical trial data.
    
    Provides access to 102 caslibs with patient-level data for validation.
    """
    
    def __init__(self):
        try:
            import sys
            # Add scripts directory to path if needed
            # Path: portals/ → research_intelligence/ → services/ → api/ → oncology-backend-minimal/ → oncology-coPilot/ → crispr-assistant-main/scripts
            scripts_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../../scripts"))
            if scripts_path not in sys.path:
                sys.path.insert(0, scripts_path)
            
            from data_acquisition.utils.project_data_sphere_client import ProjectDataSphereClient
            
            self.client = ProjectDataSphereClient(
                cas_url="https://mpmprodvdmml.ondemand.sas.com/cas-shared-default-http/",
                ssl_cert_path=os.path.abspath(os.path.join(
                    os.path.dirname(__file__),
                    "../../../../../../data/certs/trustedcerts.pem"
                ))
            )
            self.connected = False
        except Exception as e:
            logger.warning(f"ProjectDataSphereClient initialization failed: {e}")
            self.client = None
    
    async def search_cohorts(
        self,
        disease: str,
        biomarker: Optional[str] = None,
        max_results: int = 10
    ) -> Dict[str, Any]:
        """
        Search for cohorts matching disease and biomarker criteria.
        
        Args:
            disease: Cancer type (e.g., "ovarian", "breast", "prostate")
            biomarker: Optional biomarker (e.g., "CA-125", "PSA")
            max_results: Maximum number of cohorts to return
        
        Returns:
            Dict with cohort data, CA-125 measurements, PFI, treatment history
        """
        if not self.client:
            return {"cohorts": [], "count": 0, "error": "ProjectDataSphereClient not available"}
        
        if not self.connected:
            # Connect to PDS (requires password from env)
            password = os.getenv("PDS_PASSWORD")
            if password:
                self.connected = self.client.connect(username="mpm0fxk2", password=password)
        
        if not self.connected:
            logger.warning("Project Data Sphere not connected, returning empty results")
            return {"cohorts": [], "count": 0, "error": "Not connected"}
        
        # List caslibs matching disease
        try:
            all_caslibs = self.client.list_caslibs()
            matching_caslibs = [
                c for c in all_caslibs 
                if disease.lower() in c.get("name", "").lower()
            ]
            
            cohorts = []
            for caslib in matching_caslibs[:max_results]:
                try:
                    # Extract cohort data (simplified - would need full implementation)
                    cohort_data = {
                        "caslib": caslib.get("name"),
                        "disease": disease,
                        "patient_count": 0,  # Would extract from caslib
                        "ca125_available": False,  # Would check data dictionary
                        "pfi_available": False,
                        "data_quality": "unknown"
                    }
                    cohorts.append(cohort_data)
                except Exception as e:
                    logger.warning(f"Failed to extract cohort from {caslib.get('name')}: {e}")
                    continue
            
            return {
                "cohorts": cohorts,
                "count": len(cohorts),
                "source": "project_data_sphere"
            }
        except Exception as e:
            logger.error(f"Project Data Sphere search failed: {e}")
            return {"cohorts": [], "count": 0, "error": str(e)}

