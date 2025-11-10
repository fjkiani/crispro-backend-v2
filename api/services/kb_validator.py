"""
Knowledge Base Validator
Handles JSON Schema validation for KB items
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging

try:
    import jsonschema
    from jsonschema import validate, ValidationError
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    logging.warning("jsonschema not available, validation disabled")

logger = logging.getLogger(__name__)

class KBValidator:
    """Validates KB items against JSON schemas"""
    
    def __init__(self, kb_root: str = None):
        self.kb_root = Path(kb_root or os.getenv("KB_ROOT", "knowledge_base"))
        self.schemas_dir = self.kb_root / "schemas"
        self._schemas: Dict[str, Dict] = {}
        self._load_schemas()
    
    def _load_schemas(self):
        """Load all JSON schemas from the schemas directory"""
        if not JSONSCHEMA_AVAILABLE:
            logger.warning("JSON Schema validation disabled - jsonschema not available")
            return
        
        if not self.schemas_dir.exists():
            logger.warning(f"Schemas directory not found: {self.schemas_dir}")
            return
        
        schema_files = {
            "gene": "gene.json",
            "variant": "variant.json", 
            "pathway": "pathway.json",
            "drug": "drug.json",
            "disease": "disease.json",
            "evidence_item": "evidence_item.json",
            "cohort_summary": "cohort_summary.json",
            "policy_profile": "policy_profile.json"
        }
        
        for schema_type, filename in schema_files.items():
            schema_path = self.schemas_dir / filename
            if schema_path.exists():
                try:
                    with open(schema_path, 'r', encoding='utf-8') as f:
                        schema = json.load(f)
                    self._schemas[schema_type] = schema
                    logger.info(f"Loaded schema for {schema_type}")
                except (json.JSONDecodeError, IOError) as e:
                    logger.error(f"Failed to load schema {schema_path}: {e}")
            else:
                logger.warning(f"Schema file not found: {schema_path}")
    
    def validate_item(self, item: Dict[str, Any], item_type: str) -> Tuple[bool, List[str]]:
        """
        Validate an item against its schema
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        if not JSONSCHEMA_AVAILABLE:
            return True, []  # Skip validation if jsonschema not available
        
        if item_type not in self._schemas:
            return False, [f"No schema found for type: {item_type}"]
        
        try:
            validate(instance=item, schema=self._schemas[item_type])
            return True, []
        except ValidationError as e:
            return False, [f"Validation error: {e.message}"]
        except Exception as e:
            return False, [f"Unexpected validation error: {str(e)}"]
    
    def validate_file(self, file_path: Path) -> Tuple[bool, List[str]]:
        """
        Validate a JSON file against its schema based on file path
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        try:
            # Determine item type from file path
            item_type = self._get_item_type_from_path(file_path)
            if not item_type:
                return False, [f"Could not determine item type from path: {file_path}"]
            
            # Load and validate the file
            with open(file_path, 'r', encoding='utf-8') as f:
                item = json.load(f)
            
            return self.validate_item(item, item_type)
            
        except (json.JSONDecodeError, IOError) as e:
            return False, [f"File error: {str(e)}"]
        except Exception as e:
            return False, [f"Unexpected error: {str(e)}"]
    
    def _get_item_type_from_path(self, file_path: Path) -> Optional[str]:
        """Determine item type from file path"""
        try:
            # Get relative path from kb_root
            rel_path = file_path.relative_to(self.kb_root)
            path_parts = rel_path.parts
            
            if len(path_parts) < 2:
                return None
            
            # Map directory structure to item types
            if path_parts[0] == "entities":
                if path_parts[1] == "genes":
                    return "gene"
                elif path_parts[1] == "variants":
                    return "variant"
                elif path_parts[1] == "pathways":
                    return "pathway"
                elif path_parts[1] == "drugs":
                    return "drug"
                elif path_parts[1] == "diseases":
                    return "disease"
            elif path_parts[0] == "facts":
                if path_parts[1] == "evidence":
                    return "evidence_item"
                elif path_parts[1] == "policies":
                    return "policy_profile"
            elif path_parts[0] == "cohorts":
                return "cohort_summary"
            
            return None
            
        except (ValueError, IndexError):
            return None
    
    def validate_all_files(self) -> Dict[str, List[Tuple[Path, bool, List[str]]]]:
        """
        Validate all JSON files in the KB
        
        Returns:
            Dict mapping item_type to list of (file_path, is_valid, errors)
        """
        results = {}
        
        if not self.kb_root.exists():
            logger.error(f"KB root directory not found: {self.kb_root}")
            return results
        
        # Find all JSON files
        json_files = list(self.kb_root.rglob("*.json"))
        
        for file_path in json_files:
            # Skip schema files and other non-item files
            if "schemas" in file_path.parts or "indexes" in file_path.parts:
                continue
            
            is_valid, errors = self.validate_file(file_path)
            item_type = self._get_item_type_from_path(file_path) or "unknown"
            
            if item_type not in results:
                results[item_type] = []
            
            results[item_type].append((file_path, is_valid, errors))
        
        return results
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get a summary of validation results"""
        results = self.validate_all_files()
        
        summary = {
            "total_files": 0,
            "valid_files": 0,
            "invalid_files": 0,
            "by_type": {},
            "errors": []
        }
        
        for item_type, file_results in results.items():
            type_summary = {
                "total": len(file_results),
                "valid": 0,
                "invalid": 0,
                "errors": []
            }
            
            for file_path, is_valid, errors in file_results:
                summary["total_files"] += 1
                if is_valid:
                    summary["valid_files"] += 1
                    type_summary["valid"] += 1
                else:
                    summary["invalid_files"] += 1
                    type_summary["invalid"] += 1
                    type_summary["errors"].extend([f"{file_path}: {error}" for error in errors])
                    summary["errors"].extend([f"{file_path}: {error}" for error in errors])
            
            summary["by_type"][item_type] = type_summary
        
        return summary

# Global instance
_kb_validator: Optional[KBValidator] = None

def get_kb_validator() -> KBValidator:
    """Get the global KB validator instance"""
    global _kb_validator
    if _kb_validator is None:
        _kb_validator = KBValidator()
    return _kb_validator
