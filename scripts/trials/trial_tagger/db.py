"""
Database Operations for Trial Tagging
======================================
Clean, focused database operations.
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Set
from dataclasses import dataclass

from .config import DB_PATH, OUTPUT_PATH


@dataclass
class Trial:
    """Clean trial data structure."""
    nct_id: str
    title: str
    interventions: str
    conditions: str
    summary: str
    status: str = ""
    
    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "Trial":
        """Create Trial from database row."""
        return cls(
            nct_id=row.get("nct_id", row.get("id", "")),
            title=row.get("title", "Unknown"),
            interventions=_extract_interventions(row),
            conditions=row.get("conditions", "Unknown"),
            summary=(row.get("summary", "") or "")[:500],
            status=row.get("status", ""),
        )


def _extract_interventions(row: Dict[str, Any]) -> str:
    """Extract intervention text from trial row."""
    interventions = []
    
    # Try interventions_json first
    if row.get("interventions_json"):
        try:
            data = json.loads(row["interventions_json"]) if isinstance(row["interventions_json"], str) else row["interventions_json"]
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        name = item.get("name", item.get("intervention_name", ""))
                        if name:
                            interventions.append(name)
                    elif isinstance(item, str):
                        interventions.append(item)
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Fallback to interventions field
    if not interventions and row.get("interventions"):
        text = row["interventions"]
        if isinstance(text, str):
            try:
                data = json.loads(text)
                interventions = [str(i) for i in (data if isinstance(data, list) else [data])]
            except (json.JSONDecodeError, TypeError):
                interventions = [i.strip() for i in text.replace(";", ",").split(",") if i.strip()]
    
    return ", ".join(interventions) if interventions else "Not specified"


def load_existing_vectors() -> Dict[str, Any]:
    """Load existing MoA vectors from JSON file."""
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, "r") as f:
            return json.load(f)
    return {}


def save_vectors(vectors: Dict[str, Any]) -> None:
    """Save MoA vectors to JSON file."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(vectors, f, indent=2)


def get_tagged_nct_ids() -> Set[str]:
    """Get set of already-tagged NCT IDs."""
    return set(load_existing_vectors().keys())


def get_untagged_trials(limit: int = 200, exclude_ids: Set[str] = None) -> List[Trial]:
    """
    Get untagged trials from database.
    
    Prioritizes: RECRUITING > ACTIVE > ENROLLING > COMPLETED
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    
    exclude_ids = exclude_ids or get_tagged_nct_ids()
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Build query
    if exclude_ids:
        placeholders = ",".join(["?" for _ in exclude_ids])
        query = f"""
        SELECT id as nct_id, title, status, interventions, interventions_json, conditions, summary
        FROM trials
        WHERE id NOT IN ({placeholders})
          AND status IN ('RECRUITING', 'ACTIVE_NOT_RECRUITING', 'ENROLLING_BY_INVITATION', 'COMPLETED')
          AND (interventions IS NOT NULL OR interventions_json IS NOT NULL)
        ORDER BY 
            CASE status
                WHEN 'RECRUITING' THEN 1
                WHEN 'ACTIVE_NOT_RECRUITING' THEN 2
                WHEN 'ENROLLING_BY_INVITATION' THEN 3
                ELSE 4
            END
        LIMIT ?
        """
        params = list(exclude_ids) + [limit]
    else:
        query = """
        SELECT id as nct_id, title, status, interventions, interventions_json, conditions, summary
        FROM trials
        WHERE status IN ('RECRUITING', 'ACTIVE_NOT_RECRUITING', 'ENROLLING_BY_INVITATION', 'COMPLETED')
          AND (interventions IS NOT NULL OR interventions_json IS NOT NULL)
        ORDER BY 
            CASE status
                WHEN 'RECRUITING' THEN 1
                WHEN 'ACTIVE_NOT_RECRUITING' THEN 2
                WHEN 'ENROLLING_BY_INVITATION' THEN 3
                ELSE 4
            END
        LIMIT ?
        """
        params = [limit]
    
    cursor.execute(query, params)
    trials = [Trial.from_row(dict(row)) for row in cursor.fetchall()]
    conn.close()
    
    return trials

