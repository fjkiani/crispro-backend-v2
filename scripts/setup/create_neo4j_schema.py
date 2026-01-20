"""
Create Neo4j Graph Schema - Component 2: Neo4j Setup
Creates constraints and indexes for optimal query performance.
"""
import sys
import os
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from api.services.neo4j_connection import get_neo4j_driver
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_graph_schema():
    """Create Neo4j graph schema: constraints, indexes."""
    driver = get_neo4j_driver()
    
    if not driver:
        logger.error("❌ Neo4j driver not available. Check NEO4J_URI and NEO4J_PASSWORD in .env")
        return False
    
    # Use default database (neo4j) if trials doesn't exist
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    
    try:
        # Test if trials database exists, otherwise use default
        with driver.session() as session:
            try:
                # Try to list databases to see what's available
                db_list = session.run("SHOW DATABASES").data()
                available_dbs = [db['name'] for db in db_list]
                logger.info(f"Available databases: {available_dbs}")
                
                if "trials" not in available_dbs:
                    logger.warning(f"⚠️ Database 'trials' not found. Using default 'neo4j'")
                    database = "neo4j"
            except:
                # If SHOW DATABASES doesn't work, use default
                database = "neo4j"
                logger.info(f"Using default database: {database}")
        
        with driver.session(database=database) as session:
            # Constraints (uniqueness)
            constraints = [
                "CREATE CONSTRAINT trial_id IF NOT EXISTS FOR (t:Trial) REQUIRE t.nct_id IS UNIQUE",
                "CREATE CONSTRAINT pi_name_email IF NOT EXISTS FOR (p:PI) REQUIRE (p.name, p.email) IS UNIQUE",
                "CREATE CONSTRAINT org_name IF NOT EXISTS FOR (o:Organization) REQUIRE o.name IS UNIQUE",
                "CREATE CONSTRAINT condition_name IF NOT EXISTS FOR (c:Condition) REQUIRE c.name IS UNIQUE",
                "CREATE CONSTRAINT site_id IF NOT EXISTS FOR (s:Site) REQUIRE (s.facility, s.city, s.state) IS UNIQUE"
            ]
            
            logger.info("Creating constraints...")
            for constraint in constraints:
                try:
                    session.run(constraint)
                    logger.info(f"✅ {constraint[:60]}...")
                except Exception as e:
                    logger.warning(f"⚠️ Constraint may already exist: {e}")
            
            # Indexes (performance)
            indexes = [
                "CREATE INDEX trial_status IF NOT EXISTS FOR (t:Trial) ON (t.status)",
                "CREATE INDEX trial_phase IF NOT EXISTS FOR (t:Trial) ON (t.phase)",
                "CREATE INDEX site_state IF NOT EXISTS FOR (s:Site) ON (s.state)",
                "CREATE INDEX org_type IF NOT EXISTS FOR (o:Organization) ON (o.type)"
            ]
            
            logger.info("Creating indexes...")
            for index in indexes:
                try:
                    session.run(index)
                    logger.info(f"✅ {index[:60]}...")
                except Exception as e:
                    logger.warning(f"⚠️ Index may already exist: {e}")
            
            logger.info("🎉 Neo4j schema creation complete")
            return True
            
    except Exception as e:
        logger.error(f"❌ Schema creation failed: {e}", exc_info=True)
        return False
    finally:
        driver.close()

if __name__ == "__main__":
    success = create_graph_schema()
    sys.exit(0 if success else 1)

