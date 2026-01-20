"""
Component 3: Load Trials into Neo4j Graph
Script to migrate clinical trials from SQLite to Neo4j graph database.

Usage:
    cd oncology-coPilot/oncology-backend-minimal
    venv/bin/python scripts/load_trials_to_neo4j.py [--limit 100] [--batch-size 50]
"""
import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from api.services.neo4j_graph_loader import Neo4jGraphLoader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Load clinical trials into Neo4j graph')
    parser.add_argument('--limit', type=int, default=0, help='Max trials to load (0 = all)')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for progress updates')
    
    args = parser.parse_args()
    
    try:
        loader = Neo4jGraphLoader()
        stats = loader.load_all_trials(limit=args.limit, batch_size=args.batch_size)
        
        print()
        print("=" * 60)
        print("🎉 GRAPH LOADING COMPLETE")
        print("=" * 60)
        print(f"Total trials processed: {stats['total_trials']}")
        print(f"Successfully loaded: {stats['loaded']}")
        print(f"Failed: {stats['failed']}")
        print(f"Relationships created:")
        print(f"  - PIs: {stats['pis_created']}")
        print(f"  - Organizations: {stats['orgs_created']}")
        print(f"  - Sites: {stats['sites_created']}")
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Graph loading failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())










