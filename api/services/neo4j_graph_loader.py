"""
Neo4j Graph Loader Service - Component 3
Loads clinical trials from SQLite into Neo4j graph database.

Creates nodes and relationships:
- Trial nodes
- PI nodes + (PI)->[LEADS]->(Trial) relationships
- Organization nodes + (Org)->[SPONSORS]->(Trial) relationships
- Site nodes + (Trial)->[CONDUCTED_AT]->(Site) relationships
- Condition nodes + (Trial)->[TARGETS]->(Condition) relationships
- Intervention nodes + (Trial)->[USES]->(Intervention) relationships
"""
import json
import logging
from typing import Dict, List, Any, Optional
from neo4j import GraphDatabase

from api.services.database_connections import get_db_connections
from api.services.neo4j_connection import get_neo4j_driver

logger = logging.getLogger(__name__)


class Neo4jGraphLoader:
    """Service to load clinical trials into Neo4j graph."""
    
    def __init__(self):
        self.neo4j_driver = get_neo4j_driver()
        if not self.neo4j_driver:
            raise ValueError("Neo4j driver not available")
    
    def load_trial_to_graph(self, trial_dict: Dict[str, Any], session) -> bool:
        """
        Load a single trial into Neo4j graph.
        
        Args:
            trial_dict: Trial data from SQLite (includes pis_json, orgs_json, sites_json)
            session: Neo4j session
            
        Returns:
            True if successful
        """
        nct_id = trial_dict.get('nct_id')
        if not nct_id:
            logger.warning("Trial missing NCT ID, skipping")
            return False
        
        try:
            # === Create Trial Node ===
            trial_query = """
            MERGE (t:Trial {nct_id: $nct_id})
            SET t.title = $title,
                t.status = $status,
                t.phase = $phase,
                t.description = $description,
                t.disease_category = $disease_category,
                t.source_url = $source_url
            """
            
            session.run(trial_query, {
                "nct_id": nct_id,
                "title": trial_dict.get('title', ''),
                "status": trial_dict.get('status', 'Unknown'),
                "phase": trial_dict.get('phase', 'N/A'),
                "description": trial_dict.get('description_text', '')[:500],  # Truncate long desc
                "disease_category": trial_dict.get('disease_category', ''),
                "source_url": trial_dict.get('source_url', '')
            })
            
            # === Parse and create PI nodes + relationships ===
            pis_json = trial_dict.get('pis_json')
            if pis_json:
                try:
                    pis = json.loads(pis_json) if isinstance(pis_json, str) else pis_json
                    for pi_data in pis:
                        self._create_pi_relationship(pi_data, nct_id, session)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse PIs JSON for {nct_id}: {e}")
            
            # === Parse and create Organization nodes + relationships ===
            orgs_json = trial_dict.get('orgs_json')
            if orgs_json:
                try:
                    orgs = json.loads(orgs_json) if isinstance(orgs_json, str) else orgs_json
                    
                    # Lead sponsor
                    lead_sponsor = orgs.get('lead_sponsor')
                    if lead_sponsor:
                        self._create_org_relationship(lead_sponsor, nct_id, 'LEAD_SPONSOR', session)
                    
                    # Collaborators
                    collaborators = orgs.get('collaborators', [])
                    for collab in collaborators:
                        self._create_org_relationship(collab, nct_id, 'COLLABORATOR', session)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse orgs JSON for {nct_id}: {e}")
            
            # === Parse and create Site nodes + relationships ===
            sites_json = trial_dict.get('sites_json')
            if sites_json:
                try:
                    sites = json.loads(sites_json) if isinstance(sites_json, str) else sites_json
                    for site_data in sites:
                        self._create_site_relationship(site_data, nct_id, session)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse sites JSON for {nct_id}: {e}")
            
            # === Create Condition nodes (from disease_category) ===
            disease_category = trial_dict.get('disease_category')
            if disease_category:
                self._create_condition_relationship(disease_category, nct_id, session)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load trial {nct_id}: {e}")
            return False
    
    def _create_pi_relationship(self, pi_data: Dict, nct_id: str, session):
        """Create PI node and LEADS relationship."""
        name = pi_data.get('name', '').strip()
        email = pi_data.get('email', '').strip()
        affiliation = pi_data.get('affiliation', '').strip()
        
        if not name:
            return
        
        # Create or merge PI node
        pi_query = """
        MERGE (p:PI {name: $name, email: $email})
        SET p.affiliation = $affiliation,
            p.last_seen_trial = $nct_id
        WITH p
        MATCH (t:Trial {nct_id: $nct_id})
        MERGE (p)-[r:LEADS]->(t)
        SET r.weight = 1.0
        """
        
        session.run(pi_query, {
            "name": name,
            "email": email or "",  # Empty string if None
            "affiliation": affiliation,
            "nct_id": nct_id
        })
    
    def _create_org_relationship(self, org_name: str, nct_id: str, rel_type: str, session):
        """Create Organization node and SPONSOR/COLLABORATOR relationship."""
        if not org_name or not org_name.strip():
            return
        
        org_name = org_name.strip()
        
        # Determine org type (heuristic)
        org_type = "ACADEMIC" if any(x in org_name.upper() for x in ["UNIVERSITY", "HOSPITAL", "MEDICAL CENTER"]) else "INDUSTRY"
        
        # Create or merge Organization node
        org_query = f"""
        MERGE (o:Organization {{name: $org_name}})
        SET o.type = $org_type,
            o.last_seen_trial = $nct_id
        WITH o
        MATCH (t:Trial {{nct_id: $nct_id}})
        MERGE (o)-[r:{rel_type}]->(t)
        SET r.weight = 2.0
        """
        
        session.run(org_query, {
            "org_name": org_name,
            "org_type": org_type,
            "nct_id": nct_id
        })
    
    def _create_site_relationship(self, site_data: Dict, nct_id: str, session):
        """Create Site node and CONDUCTED_AT relationship."""
        facility = site_data.get('facility', '').strip()
        city = site_data.get('city', '').strip()
        state = site_data.get('state', '').strip()
        country = site_data.get('country', 'United States').strip()
        
        if not facility:
            return
        
        # Create or merge Site node (unique by facility + city + state)
        site_query = """
        MERGE (s:Site {facility: $facility, city: $city, state: $state})
        SET s.country = $country,
            s.status = $status,
            s.last_seen_trial = $nct_id
        WITH s
        MATCH (t:Trial {nct_id: $nct_id})
        MERGE (t)-[r:CONDUCTED_AT]->(s)
        SET r.weight = 1.0
        """
        
        session.run(site_query, {
            "facility": facility,
            "city": city,
            "state": state,
            "country": country,
            "status": site_data.get('status', ''),
            "nct_id": nct_id
        })
    
    def _create_condition_relationship(self, condition: str, nct_id: str, session):
        """Create Condition node and TARGETS relationship."""
        if not condition or not condition.strip():
            return
        
        condition = condition.strip()
        
        cond_query = """
        MERGE (c:Condition {name: $condition})
        WITH c
        MATCH (t:Trial {nct_id: $nct_id})
        MERGE (t)-[r:TARGETS]->(c)
        SET r.weight = 1.0
        """
        
        session.run(cond_query, {
            "condition": condition,
            "nct_id": nct_id
        })
    
    def load_all_trials(self, limit: int = 0, batch_size: int = 100) -> Dict[str, Any]:
        """
        Load all trials from SQLite into Neo4j.
        
        Args:
            limit: Max trials to load (0 = all)
            batch_size: Trials per batch (for progress tracking)
            
        Returns:
            Statistics dict
        """
        # Direct connection to backend database (bypass DatabaseConnections)
        import sqlite3
        from pathlib import Path
        
        # Find database in backend directory
        script_path = Path(__file__).resolve()
        # Navigate: api/services/neo4j_graph_loader.py -> api -> oncology-backend-minimal -> oncology-coPilot -> oncology-backend
        project_root = script_path.parent.parent.parent.parent.parent
        db_path = project_root / "oncology-coPilot" / "oncology-backend" / "backend" / "data" / "clinical_trials.db"
        
        if not db_path.exists():
            # Try alternative paths
            alt_paths = [
                project_root / "oncology-backend" / "backend" / "data" / "clinical_trials.db",
                script_path.parent.parent.parent.parent / "oncology-backend" / "backend" / "data" / "clinical_trials.db",
            ]
            for alt_path in alt_paths:
                if alt_path.exists():
                    db_path = alt_path
                    break
        
        if not db_path.exists():
            raise ValueError(f"SQLite database not found. Expected: {db_path}")
        
        logger.info(f"Connecting to database: {db_path}")
        conn = sqlite3.connect(str(db_path))
        
        cursor = conn.cursor()
        
        # Get trial count
        cursor.execute("SELECT COUNT(*) FROM clinical_trials")
        total = cursor.fetchone()[0]
        
        # Apply limit
        query_limit = f"LIMIT {limit}" if limit > 0 else ""
        
        # Check which columns exist
        cursor.execute("PRAGMA table_info(clinical_trials)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        # Build query with available columns
        available_cols = []
        for col in ['nct_id', 'title', 'status', 'phase', 'description_text', 
                    'disease_category', 'source_url', 'source', 'pis_json', 'orgs_json', 'sites_json']:
            if col in columns:
                available_cols.append(col)
        
        query = f"""
        SELECT {', '.join(available_cols)}
        FROM clinical_trials
        {query_limit}
        """
        
        cursor.execute(query)
        trials = cursor.fetchall()
        
        stats = {
            "total_trials": len(trials),
            "loaded": 0,
            "failed": 0,
            "pis_created": 0,
            "orgs_created": 0,
            "sites_created": 0
        }
        
        logger.info(f"🚀 Loading {len(trials)} trials into Neo4j graph...")
        
        with self.neo4j_driver.session(database="neo4j") as session:
            for i, row in enumerate(trials, 1):
                # Map row to dict using column positions
                row_dict = dict(zip(available_cols, row))
                
                trial_dict = {
                    'nct_id': row_dict.get('nct_id', ''),
                    'title': row_dict.get('title', ''),
                    'status': row_dict.get('status', 'Unknown'),
                    'phase': row_dict.get('phase', 'N/A'),
                    'description_text': row_dict.get('description_text', ''),
                    'disease_category': row_dict.get('disease_category', ''),
                    'source_url': row_dict.get('source_url') or row_dict.get('source', ''),
                    'pis_json': row_dict.get('pis_json'),
                    'orgs_json': row_dict.get('orgs_json'),
                    'sites_json': row_dict.get('sites_json')
                }
                
                if self.load_trial_to_graph(trial_dict, session):
                    stats["loaded"] += 1
                    
                    # Count relationships created
                    if trial_dict.get('pis_json'):
                        try:
                            pis = json.loads(trial_dict['pis_json']) if isinstance(trial_dict['pis_json'], str) else trial_dict['pis_json']
                            stats["pis_created"] += len(pis)
                        except:
                            pass
                    
                    if trial_dict.get('orgs_json'):
                        try:
                            orgs = json.loads(trial_dict['orgs_json']) if isinstance(trial_dict['orgs_json'], str) else trial_dict['orgs_json']
                            stats["orgs_created"] += 1 if orgs.get('lead_sponsor') else 0
                            stats["orgs_created"] += len(orgs.get('collaborators', []))
                        except:
                            pass
                    
                    if trial_dict.get('sites_json'):
                        try:
                            sites = json.loads(trial_dict['sites_json']) if isinstance(trial_dict['sites_json'], str) else trial_dict['sites_json']
                            stats["sites_created"] += len(sites)
                        except:
                            pass
                else:
                    stats["failed"] += 1
                
                if i % batch_size == 0:
                    logger.info(f"Progress: {i}/{len(trials)} trials loaded...")
        
        conn.close()
        
        logger.info(f"✅ Graph loading complete!")
        logger.info(f"   Loaded: {stats['loaded']} trials")
        logger.info(f"   Failed: {stats['failed']} trials")
        logger.info(f"   Relationships: {stats['pis_created']} PIs, {stats['orgs_created']} Orgs, {stats['sites_created']} Sites")
        
        return stats

