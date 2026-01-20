#!/usr/bin/env python3
"""Test Supabase client fallback for query persistence."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from api.services.research_intelligence.db_helper import save_query_with_fallback
import json

def test_fallback():
    print('🔍 Testing Supabase Client Fallback for Query Persistence...')
    
    test_query_data = {
        'user_id': '00000000-0000-0000-0000-000000000000',  # Test user
        'question': 'Test query for fallback',
        'context': {'test': True},
        'options': {},
        'result': {'test': 'result'},
        'provenance': None,
        'persona': 'patient'
    }
    
    query_id = save_query_with_fallback(test_query_data)
    
    if query_id:
        print(f'✅ Query saved successfully via fallback! Query ID: {query_id}')
        return True
    else:
        print('❌ Query save failed even with fallback')
        return False

if __name__ == '__main__':
    result = test_fallback()
    sys.exit(0 if result else 1)
