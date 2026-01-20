"""
JSON Parser - For structured mutation data
"""
from typing import BinaryIO, Union, Dict, Optional, List
import io
import json
import logging

logger = logging.getLogger(__name__)


class JSONParser:
    """Parse JSON files with structured mutation data."""
    
    async def parse(
        self,
        file: Union[BinaryIO, bytes, str],
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Parse JSON file and extract mutations.
        
        Expected JSON structure:
        {
            "mutations": [
                {
                    "gene": "BRAF",
                    "variant": "V600E",
                    "hgvs_p": "p.Val600Glu",
                    ...
                }
            ],
            "clinical_data": {...},
            "demographics": {...}
        }
        """
        try:
            if isinstance(file, bytes):
                data = json.loads(file.decode('utf-8'))
            elif isinstance(file, str):
                with open(file, 'r') as f:
                    data = json.load(f)
            else:
                # BinaryIO
                content = file.read()
                if isinstance(content, bytes):
                    content = content.decode('utf-8')
                data = json.loads(content)
            
            # Normalize structure
            if isinstance(data, list):
                # If root is a list, assume it's a list of mutations
                data = {'mutations': data}
            
            return data
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return {'mutations': [], 'error': 'json_parse_error'}
        except Exception as e:
            logger.error(f"Failed to read JSON file: {e}")
            return {'mutations': [], 'error': str(e)}


