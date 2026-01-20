"""Export top 50 vector search candidates for JR2 analysis."""
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from api.services.clinical_trial_search_service import ClinicalTrialSearchService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info("🔍 Querying AstraDB for top 50 candidates...")
    service = ClinicalTrialSearchService()
    
    # Vector search (no hard filters)
    response = await service.search_trials(
        query="frontline ovarian cancer high-grade serous stage IV treatment",
        disease_category="gynecologic_oncology",
        top_k=50
    )
    
    candidates = response.get("data", {}).get("found_trials", [])
    logger.info(f"✅ Found {len(candidates)} candidates")
    
    # Export
    output = {
        "generated_at": datetime.now().isoformat(),
        "total_candidates": len(candidates),
        "patient": "AK (Stage IVB, First-line, Germline-negative)",
        "candidates": candidates
    }
    
    output_path = Path("../../.cursor/ayesha/50_vector_candidates_for_jr2.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    logger.info(f"✅ Exported to {output_path}")
    print(f"\n🎯 TOP 10 CANDIDATES:")
    for i, t in enumerate(candidates[:10], 1):
        print(f"{i}. {t.get('nct_id')} - {t.get('title', 'N/A')[:60]}")

if __name__ == "__main__":
    asyncio.run(main())
