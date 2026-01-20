"""
Neo4j Connection Service - Singleton pattern for graph database connection.
Part of Component 2: Neo4j Setup & Schema
"""
import os
from typing import Optional
import logging
from dotenv import load_dotenv

# Graceful degradation: Neo4j is optional
try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    GraphDatabase = None  # type: ignore

# Load .env file
load_dotenv()

logger = logging.getLogger(__name__)

class Neo4jConnection:
    """Singleton Neo4j database connection."""
    
    _driver: Optional[GraphDatabase] = None
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._driver is None:
            if not NEO4J_AVAILABLE:
                logger.warning("⚠️ neo4j module not installed - Neo4j features will be unavailable")
                self._driver = None
                return
                
            uri = os.getenv("NEO4J_URI")
            user = os.getenv("NEO4J_USER", "neo4j")
            password = os.getenv("NEO4J_PASSWORD")
            database = os.getenv("NEO4J_DATABASE", "neo4j")  # Use default neo4j database
            
            if not uri or not password:
                logger.warning("⚠️ NEO4J_URI and NEO4J_PASSWORD must be set (connection will fail until configured)")
                self._driver = None
                return
            
            try:
                self._driver = GraphDatabase.driver(uri, auth=(user, password))
                # Test connection
                self._driver.verify_connectivity()
                logger.info(f"✅ Neo4j connection established (database: {database})")
            except Exception as e:
                logger.error(f"❌ Neo4j connection failed: {e}")
                logger.warning("⚠️ Continuing without Neo4j - features requiring graph DB will be unavailable")
                self._driver = None
                # Don't raise - allow server to start without Neo4j
    
    @property
    def driver(self) -> Optional[GraphDatabase]:
        """Get Neo4j driver instance."""
        if self._driver is None:
            try:
                self.__init__()
            except:
                pass
        return self._driver
    
    def close(self):
        """Close Neo4j connection."""
        if self._driver:
            self._driver.close()
            self._driver = None

# Singleton instance
neo4j_connection = Neo4jConnection()

def get_neo4j_driver() -> Optional[GraphDatabase]:
    """Get Neo4j driver (for dependency injection)."""
    return neo4j_connection.driver

