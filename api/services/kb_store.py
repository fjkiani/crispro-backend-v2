"""
Knowledge Base Store Service
Handles file loading, caching, and search functionality for the KB
"""
import os
import json
import time
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from functools import lru_cache
import logging

try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False
    logging.warning("rapidfuzz not available, using basic string matching")

logger = logging.getLogger(__name__)

class KBStore:
    """Knowledge Base store with file caching and search capabilities"""
    
    def __init__(self, kb_root: str = None):
        self.kb_root = Path(kb_root or os.getenv("KB_ROOT", "knowledge_base"))
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._cache_ttl = 300  # 5 minutes
        self._file_mtimes: Dict[str, float] = {}
        
        # Type mappings
        self.type_mappings = {
            "gene": "entities/genes",
            "genes": "entities/genes",  # Support both singular and plural
            "variant": "entities/variants",
            "variants": "entities/variants",  # Support both singular and plural
            "pathway": "entities/pathways",
            "pathways": "entities/pathways",  # Support both singular and plural
            "drug": "entities/drugs",
            "drugs": "entities/drugs",  # Support both singular and plural
            "disease": "entities/diseases",
            "diseases": "entities/diseases",  # Support both singular and plural
            "evidence": "facts/evidence",
            "policy": "facts/policies",
            "cohort": "cohorts",
            "cohorts": "cohorts"  # Support both singular and plural
        }
        
        logger.info(f"KB Store initialized with root: {self.kb_root}")
    
    def _get_file_path(self, item_id: str) -> Optional[Path]:
        """Get file path for an item ID"""
        try:
            item_type, item_name = item_id.split("/", 1)
            if item_type not in self.type_mappings:
                return None
            
            base_path = self.type_mappings[item_type]
            
            # Handle special cases
            if item_type == "cohort":
                # cohort/cbio_ov_tcga -> cohorts/cbio/ov_tcga.json
                if "_" in item_name:
                    provider, study = item_name.split("_", 1)
                    return self.kb_root / base_path / provider / f"{study}.json"
                else:
                    return self.kb_root / base_path / f"{item_name}.json"
            else:
                return self.kb_root / base_path / f"{item_name}.json"
        except (ValueError, IndexError):
            return None
    
    def _load_json_file(self, file_path: Path) -> Optional[Dict]:
        """Load and parse JSON file with caching"""
        try:
            # Check if file exists
            if not file_path.exists():
                return None
            
            # Check cache
            cache_key = str(file_path)
            current_mtime = file_path.stat().st_mtime
            
            if (cache_key in self._cache and 
                cache_key in self._file_mtimes and
                self._file_mtimes[cache_key] == current_mtime and
                time.time() - self._cache[cache_key][1] < self._cache_ttl):
                return self._cache[cache_key][0]
            
            # Load file
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Update cache
            self._cache[cache_key] = (data, time.time())
            self._file_mtimes[cache_key] = current_mtime
            
            return data
            
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading {file_path}: {e}")
            return None
    
    def get_item(self, item_id: str) -> Optional[Dict]:
        """Get a single item by ID"""
        file_path = self._get_file_path(item_id)
        if not file_path:
            return None
        
        data = self._load_json_file(file_path)
        if data:
            data["id"] = item_id
        return data
    
    def list_items(self, item_type: str, limit: int = 50, offset: int = 0) -> List[Dict]:
        """List items of a specific type with pagination"""
        if item_type not in self.type_mappings:
            return []
        
        base_path = self.kb_root / self.type_mappings[item_type]
        if not base_path.exists():
            return []
        
        items = []
        
        # Handle different directory structures
        if item_type == "cohort":
            # cohorts/cbio/, cohorts/gdc/
            for provider_dir in base_path.iterdir():
                if provider_dir.is_dir():
                    for json_file in provider_dir.glob("*.json"):
                        item_id = f"{item_type}/{provider_dir.name}_{json_file.stem}"
                        data = self._load_json_file(json_file)
                        if data:
                            data["id"] = item_id
                            items.append(data)
        else:
            # entities/genes/, entities/variants/, etc.
            for json_file in base_path.glob("*.json"):
                item_id = f"{item_type}/{json_file.stem}"
                data = self._load_json_file(json_file)
                if data:
                    data["id"] = item_id
                    items.append(data)
        
        # Sort by ID for consistent pagination
        items.sort(key=lambda x: x.get("id", ""))
        
        return items[offset:offset + limit]
    
    def search(self, query: str, types: List[str] = None, limit: int = 20) -> Dict[str, Any]:
        """Search across KB items using fuzzy matching"""
        if not query.strip():
            return {"query": query, "hits": []}
        
        types = types or list(self.type_mappings.keys())
        all_hits = []
        
        for item_type in types:
            items = self.list_items(item_type, limit=1000)  # Get all items for search
            
            for item in items:
                # Search in relevant fields
                searchable_text = []
                
                # Add common fields
                for field in ["name", "symbol", "description", "mechanism", "helper_copy"]:
                    if field in item and item[field]:
                        searchable_text.append(str(item[field]))
                
                # Add gene-specific fields
                if item_type == "gene" and "function" in item:
                    searchable_text.append(item["function"])
                
                # Add variant-specific fields
                if item_type == "variant":
                    if "hgvs_p" in item:
                        searchable_text.append(item["hgvs_p"])
                    if "consequence" in item:
                        searchable_text.append(item["consequence"])
                
                # Combine searchable text
                full_text = " ".join(searchable_text).lower()
                query_lower = query.lower()
                
                # Calculate relevance score
                if RAPIDFUZZ_AVAILABLE:
                    # Use rapidfuzz for better matching
                    score = fuzz.partial_ratio(query_lower, full_text) / 100.0
                else:
                    # Basic string matching - improved scoring
                    if query_lower in full_text:
                        # Higher score for exact matches, especially in symbol/name fields
                        if item.get("symbol", "").lower() == query_lower:
                            score = 0.95  # Exact symbol match
                        elif item.get("name", "").lower().find(query_lower) != -1:
                            score = 0.85  # Name contains query
                        else:
                            score = 0.7   # General text match
                    else:
                        # Check for partial matches
                        words = query_lower.split()
                        matches = sum(1 for word in words if word in full_text)
                        if matches > 0:
                            score = matches / len(words) * 0.6
                        else:
                            score = 0.0
                
                if score > 0.1:  # Minimum relevance threshold (lowered for testing)
                    hit = {
                        "id": item["id"],
                        "type": item_type,
                        "title": item.get("name", item.get("symbol", item["id"])),
                        "score": round(score, 3),
                        "snippet": self._extract_snippet(full_text, query_lower),
                        "item": item  # Include the full item data
                    }
                    all_hits.append(hit)
        
        # Sort by score and limit results
        all_hits.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "query": query,
            "hits": all_hits[:limit]
        }
    
    def _extract_snippet(self, text: str, query: str, max_length: int = 150) -> str:
        """Extract a relevant snippet around the query"""
        query_pos = text.find(query)
        if query_pos == -1:
            return text[:max_length] + "..." if len(text) > max_length else text
        
        start = max(0, query_pos - 50)
        end = min(len(text), query_pos + len(query) + 50)
        
        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        
        return snippet
    
    def get_etag(self, item_id: str) -> Optional[str]:
        """Get ETag for an item (based on file mtime and size)"""
        file_path = self._get_file_path(item_id)
        if not file_path or not file_path.exists():
            return None
        
        stat = file_path.stat()
        etag_data = f"{stat.st_mtime}-{stat.st_size}"
        return hashlib.md5(etag_data.encode()).hexdigest()
    
    def reload_cache(self) -> Dict[str, Any]:
        """Reload the file cache"""
        self._cache.clear()
        self._file_mtimes.clear()
        
        return {
            "status": "success",
            "message": "KB cache reloaded",
            "timestamp": time.time()
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get KB statistics"""
        stats = {
            "total_items": 0,
            "by_type": {},
            "cache_size": len(self._cache),
            "kb_root": str(self.kb_root)
        }
        
        for item_type in self.type_mappings:
            items = self.list_items(item_type, limit=1000)
            count = len(items)
            stats["by_type"][item_type] = count
            stats["total_items"] += count
        
        return stats

# Global instance
_kb_store: Optional[KBStore] = None

def get_kb_store() -> KBStore:
    """Get the global KB store instance"""
    global _kb_store
    if _kb_store is None:
        _kb_store = KBStore()
    return _kb_store
