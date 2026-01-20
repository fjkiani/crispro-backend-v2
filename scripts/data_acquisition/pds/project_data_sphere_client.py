#!/usr/bin/env python3
"""
Project Data Sphere API Client
==============================
Client for accessing Project Data Sphere via SAS CAS API.

Project Data Sphere provides access to clinical trial data including:
- Patient-level clinical data
- Biomarker data (potentially including CA-125)
- Survival outcomes
- Treatment response data

Author: Agent
Date: January 28, 2025
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any
import json

try:
    import swat
    SWAT_AVAILABLE = True
except ImportError:
    SWAT_AVAILABLE = False
    print("⚠️  swat library not installed. Install with: pip install swat")


class ProjectDataSphereClient:
    """Client for accessing Project Data Sphere via SAS CAS API."""
    
    def __init__(self, 
                 cas_url: Optional[str] = None,
                 ssl_cert_path: Optional[str] = None,
                 port: int = 443):
        """
        Initialize Project Data Sphere client.
        
        Args:
            cas_url: CAS server URL (e.g., "https://mpmprodvdmml.ondemand.sas.com/cas-shared-default-http/")
            ssl_cert_path: Path to SSL certificate file
            port: CAS server port (default 443)
        """
        if not SWAT_AVAILABLE:
            raise ImportError("swat library is required. Install with: pip install swat")
        
        self.cas_url = cas_url
        self.ssl_cert_path = ssl_cert_path
        self.port = port
        self.conn = None
        
        # Set SSL certificate if provided
        if ssl_cert_path and os.path.exists(ssl_cert_path):
            os.environ["CAS_CLIENT_SSL_CA_LIST"] = ssl_cert_path
            print(f"✅ SSL certificate set: {ssl_cert_path}")
        elif ssl_cert_path:
            print(f"⚠️  SSL certificate not found at: {ssl_cert_path}")
    
    def connect(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        Connect to Project Data Sphere CAS server.
        
        Args:
            username: CAS username (if required)
            password: CAS password (if required)
        
        Returns:
            True if connection successful, False otherwise
        """
        if not self.cas_url:
            print("❌ CAS URL not set. Please provide cas_url in __init__")
            return False
        
        try:
            print(f"🔌 Connecting to CAS server: {self.cas_url}:{self.port}")
            
            # Connect to CAS
            if username and password:
                self.conn = swat.CAS(self.cas_url, self.port, username=username, password=password)
            else:
                self.conn = swat.CAS(self.cas_url, self.port)
            
            # Test connection
            status = self.conn.serverstatus()
            print(f"✅ Connected successfully!")
            print(f"   Server status: {status}")
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def list_caslibs(self) -> List[Dict[str, Any]]:
        """List all available caslibs (data libraries)."""
        if not self.conn:
            print("❌ Not connected. Call connect() first.")
            return []
        
        try:
            result = self.conn.table.caslibInfo()
            caslibs = []
            
            # Parse result (structure depends on CAS response)
            if hasattr(result, 'CASLibInfo'):
                for caslib in result.CASLibInfo:
                    caslibs.append({
                        'name': caslib.get('Name', ''),
                        'description': caslib.get('Description', ''),
                        'path': caslib.get('Path', '')
                    })
            
            return caslibs
            
        except Exception as e:
            print(f"❌ Error listing caslibs: {e}")
            return []
    
    def list_files_in_caslib(self, caslib_name: str, path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List files in a caslib.
        
        Args:
            caslib_name: Name of the caslib
            path: Optional subdirectory path
        
        Returns:
            List of file information dictionaries
        """
        if not self.conn:
            print("❌ Not connected. Call connect() first.")
            return []
        
        try:
            params = {'allFiles': True, 'caslib': caslib_name}
            if path:
                params['path'] = path
            
            result = self.conn.table.fileInfo(**params)
            
            files = []
            if hasattr(result, 'FileInfo'):
                for file_info in result.FileInfo:
                    files.append({
                        'name': file_info.get('Name', ''),
                        'path': file_info.get('Path', ''),
                        'size': file_info.get('Size', 0),
                        'type': file_info.get('Type', '')
                    })
            
            return files
            
        except Exception as e:
            print(f"❌ Error listing files: {e}")
            return []
    
    def search_for_ovarian_cancer_data(self) -> List[Dict[str, Any]]:
        """
        Search for ovarian cancer related datasets.
        
        Returns:
            List of datasets that might contain ovarian cancer data
        """
        if not self.conn:
            print("❌ Not connected. Call connect() first.")
            return []
        
        ovarian_datasets = []
        
        # List all caslibs
        caslibs = self.list_caslibs()
        print(f"\n🔍 Searching {len(caslibs)} caslibs for ovarian cancer data...")
        
        # Search keywords
        ovarian_keywords = [
            'ovarian', 'ovary', 'ov', 'ca125', 'ca-125', 'ca_125',
            'platinum', 'carboplatin', 'cisplatin', 'pfi', 'pfi',
            'serous', 'hgsc', 'high grade serous'
        ]
        
        for caslib in caslibs:
            caslib_name = caslib.get('name', '')
            print(f"\n📁 Checking caslib: {caslib_name}")
            
            # List files in caslib
            files = self.list_files_in_caslib(caslib_name)
            
            for file_info in files:
                file_name = file_info.get('name', '').lower()
                file_path = file_info.get('path', '').lower()
                
                # Check if file name or path contains ovarian keywords
                for keyword in ovarian_keywords:
                    if keyword in file_name or keyword in file_path:
                        ovarian_datasets.append({
                            'caslib': caslib_name,
                            'file_name': file_info.get('name', ''),
                            'file_path': file_info.get('path', ''),
                            'matched_keyword': keyword
                        })
                        print(f"   ✅ Found potential match: {file_info.get('name', '')} (keyword: {keyword})")
                        break
        
        return ovarian_datasets
    
    def load_table(self, caslib_name: str, file_path: str, table_name: str = 'loaded_table') -> Optional[Any]:
        """
        Load a table from a caslib into CAS memory.
        
        Args:
            caslib_name: Source caslib name
            file_path: Path to file within caslib
            table_name: Name for the loaded CAS table
        
        Returns:
            CAS table object or None
        """
        if not self.conn:
            print("❌ Not connected. Call connect() first.")
            return None
        
        try:
            print(f"📥 Loading table: {caslib_name}/{file_path}")
            
            # Create output table
            cas_table = self.conn.CASTable(table_name, replace=True, caslib='CASUSER')
            
            # Load the file
            self.conn.table.loadTable(
                sourceCaslib=caslib_name,
                casOut=cas_table,
                path=file_path
            )
            
            print(f"✅ Table loaded: {table_name}")
            return cas_table
            
        except Exception as e:
            print(f"❌ Error loading table: {e}")
            return None
    
    def disconnect(self):
        """Disconnect from CAS server."""
        if self.conn:
            try:
                self.conn.close()
                print("✅ Disconnected from CAS server")
            except Exception as e:
                print(f"⚠️  Error disconnecting: {e}")
            finally:
                self.conn = None


def test_connection(cas_url: Optional[str] = None, 
                   ssl_cert_path: Optional[str] = None,
                   username: Optional[str] = None,
                   password: Optional[str] = None):
    """
    Test connection to Project Data Sphere.
    
    Args:
        cas_url: CAS server URL
        ssl_cert_path: Path to SSL certificate
        username: CAS username (if required)
        password: CAS password (if required)
    """
    if not SWAT_AVAILABLE:
        print("❌ swat library not available. Install with: pip install swat")
        return
    
    print("=" * 80)
    print("Project Data Sphere Connection Test")
    print("=" * 80)
    
    # Use default URL if not provided
    if not cas_url:
        cas_url = "https://mpmprodvdmml.ondemand.sas.com/cas-shared-default-http/"
        print(f"ℹ️  Using default CAS URL: {cas_url}")
    
    client = ProjectDataSphereClient(cas_url=cas_url, ssl_cert_path=ssl_cert_path)
    
    # Try to connect
    if client.connect(username=username, password=password):
        # List caslibs
        print("\n" + "=" * 80)
        print("Available Caslibs:")
        print("=" * 80)
        caslibs = client.list_caslibs()
        for caslib in caslibs[:10]:  # Show first 10
            print(f"  - {caslib.get('name', 'N/A')}: {caslib.get('description', 'N/A')}")
        
        # Search for ovarian cancer data
        print("\n" + "=" * 80)
        print("Searching for Ovarian Cancer Data:")
        print("=" * 80)
        ovarian_data = client.search_for_ovarian_cancer_data()
        
        if ovarian_data:
            print(f"\n✅ Found {len(ovarian_data)} potential ovarian cancer datasets:")
            for dataset in ovarian_data:
                print(f"   - {dataset['caslib']}/{dataset['file_name']} (matched: {dataset['matched_keyword']})")
        else:
            print("\n⚠️  No ovarian cancer datasets found in initial search")
        
        # Disconnect
        client.disconnect()
    else:
        print("\n❌ Failed to connect. Please check:")
        print("   1. CAS URL is correct")
        print("   2. SSL certificate path is correct (if required)")
        print("   3. Credentials are correct (if required)")
        print("   4. Network connectivity")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Project Data Sphere connection")
    parser.add_argument("--cas-url", help="CAS server URL")
    parser.add_argument("--ssl-cert", help="Path to SSL certificate file")
    parser.add_argument("--username", help="CAS username")
    parser.add_argument("--password", help="CAS password")
    
    args = parser.parse_args()
    
    test_connection(
        cas_url=args.cas_url,
        ssl_cert_path=args.ssl_cert,
        username=args.username,
        password=args.password
    )





