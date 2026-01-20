"""
DatabaseConnections - Extracted from main backend for clinical trials.
Provides centralized access to SQLite and AstraDB vector store.
"""
import os
import sqlite3
import logging
from typing import Optional
from pathlib import Path

# Third-party imports
from dotenv import load_dotenv
from astrapy import DataAPIClient
from astrapy.database import Database

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseConnections:
    """
    Centralized database connection management for both SQLite and AstraDB vector database.
    Extracted from main backend, adapted for minimal backend production use.
    """
    
    def __init__(self):
        # Load environment variables from .env file
        load_dotenv()

        # Initialize paths (adjusted for minimal backend structure)
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.data_dir = self.project_root / "data"
        self.sqlite_db_path = self.data_dir / "clinical_trials.db"
        
        # Initialize connection holders
        self.sqlite_connection: Optional[sqlite3.Connection] = None
        self.vector_db_connection: Optional[Database] = None
        
    def init_sqlite(self) -> Optional[sqlite3.Connection]:
        """Initialize SQLite connection with proper configuration."""
        try:
            # Ensure the data directory exists
            self.data_dir.mkdir(parents=True, exist_ok=True)
            
            # Create connection with row factory for dict-like rows
            connection = sqlite3.connect(str(self.sqlite_db_path))
            connection.row_factory = sqlite3.Row
            
            logger.info(f"✅ SQLite connected: {self.sqlite_db_path}")
            return connection
            
        except sqlite3.Error as e:
            logger.error(f"❌ SQLite connection failed: {e}")
            return None
            
    def get_sqlite_connection(self) -> Optional[sqlite3.Connection]:
        """Get existing SQLite connection or create new one if needed."""
        if self.sqlite_connection is None:
            self.sqlite_connection = self.init_sqlite()
        return self.sqlite_connection
        
    def close_sqlite_connection(self):
        """Safely close SQLite connection if it exists."""
        if self.sqlite_connection:
            try:
                self.sqlite_connection.close()
                self.sqlite_connection = None
                logger.info("SQLite connection closed")
            except sqlite3.Error as e:
                logger.error(f"Error closing SQLite: {e}")

    # === AstraDB Vector Database Methods ===
    
    def init_vector_db(self) -> Optional[Database]:
        """
        Initializes connection to AstraDB vector database using credentials
        from environment variables.
        """
        if self.vector_db_connection:
            return self.vector_db_connection

        token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
        api_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
        keyspace = os.getenv("ASTRA_DB_KEYSPACE", "default_keyspace")  # Default to default_keyspace

        if not token or not api_endpoint:
            logger.error("❌ AstraDB credentials missing (ASTRA_DB_APPLICATION_TOKEN, ASTRA_DB_API_ENDPOINT)")
            return None
            
        try:
            # Initialize DataAPIClient (astrapy 2.x API)
            client = DataAPIClient(token)
            # Get Database object - astrapy 2.x: use get_database_by_api_endpoint (no namespace param)
            # Keyspace is specified when getting collections, not at database level
            self.vector_db_connection = client.get_database_by_api_endpoint(api_endpoint)
            logger.info(f"✅ AstraDB connected: {api_endpoint[:50]}... (keyspace: {keyspace})")
            return self.vector_db_connection
        except Exception as e:
            logger.error(f"❌ AstraDB connection failed: {e}", exc_info=True)
            return None
        
    def get_vector_db_collection(self, collection_name: str):
        """
        Retrieves a specific collection from AstraDB,
        initializing the database connection if necessary.
        """
        db = self.get_vector_db_connection()
        if db:
            try:
                collection = db.get_collection(collection_name)
                logger.info(f"✅ AstraDB collection retrieved: '{collection_name}'")
                return collection
            except Exception as e:
                logger.error(f"❌ Failed to get collection '{collection_name}': {e}", exc_info=True)
                return None
        return None
        
    def get_vector_db_connection(self) -> Optional[Database]:
        """
        Retrieves the active AstraDB connection, initializing it if necessary.
        """
        if not self.vector_db_connection:
            return self.init_vector_db()
        return self.vector_db_connection
        
    def close_vector_db_connection(self):
        """
        Closes the AstraDB connection.
        Note: astrapy's DataAPIClient does not require explicit close.
        """
        if self.vector_db_connection:
            logger.info("Closing AstraDB connection")
            self.vector_db_connection = None
        
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.close_sqlite_connection()
        self.close_vector_db_connection()

# Global singleton instance for reuse across services
_db_connections: Optional[DatabaseConnections] = None

def get_db_connections() -> DatabaseConnections:
    """
    Returns singleton DatabaseConnections instance for application-wide reuse.
    """
    global _db_connections
    if _db_connections is None:
        _db_connections = DatabaseConnections()
    return _db_connections



