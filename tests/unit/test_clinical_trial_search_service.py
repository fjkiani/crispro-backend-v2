"""
Unit tests for ClinicalTrialSearchService.

Tests cover:
- Embedding generation
- Vector search functionality
- State filtering
- Error handling
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
import json

from api.services.clinical_trial_search_service import ClinicalTrialSearchService

class TestClinicalTrialSearchService:
    
    @pytest.fixture
    def mock_db_connections(self):
        """Mock database connections."""
        with patch('api.services.clinical_trial_search_service.get_db_connections') as mock:
            mock_db = Mock()
            mock_db.get_vector_db_collection = Mock(return_value=Mock())
            mock_db.get_sqlite_connection = Mock(return_value=Mock())
            mock.return_value = mock_db
            yield mock_db
    
    @pytest.fixture
    def mock_llm_provider(self):
        """Mock LLM provider for embeddings."""
        with patch('api.services.clinical_trial_search_service.get_llm_provider') as mock:
            mock_provider = Mock()
            mock_provider.embed = Mock(return_value=[0.1] * 768)  # Mock embedding vector
            mock_provider.is_available = Mock(return_value=True)
            mock_provider.__class__.__name__ = 'CohereProvider'
            mock.return_value = mock_provider
            yield mock_provider
    
    @pytest.fixture
    def service(self, mock_db_connections, mock_llm_provider):
        """Create service instance with mocked dependencies."""
        with patch.dict('os.environ', {'COHERE_API_KEY': 'test_key', 'ASTRA_COLLECTION_NAME': 'test_collection'}):
            return ClinicalTrialSearchService()
    
    def test_initialization(self, service):
        """Test service initializes correctly."""
        assert service is not None
        assert service.collection_name == 'test_collection'
    
    def test_generate_embedding(self, service, mock_llm_provider):
        """Test embedding generation."""
        embedding = service._generate_embedding("test query")

        assert len(embedding) == 768
        mock_llm_provider.embed.assert_called_once()
        call_args = mock_llm_provider.embed.call_args
        assert call_args[1]['text'] == 'test query'
        assert call_args[1]['task_type'] == 'retrieval_query'
    
    @pytest.mark.asyncio
    async def test_search_trials_success(self, service, mock_db_connections):
        """Test successful trial search."""
        # Mock collection.find
        mock_collection = mock_db_connections.get_vector_db_collection.return_value
        mock_collection.find = Mock(return_value=[
            {
                '$similarity': 0.85,
                'nct_id': 'NCT12345',
                'title': 'Test Trial',
                'status': 'RECRUITING',
                'source_url': 'https://clinicaltrials.gov/study/NCT12345',
                'disease_category': 'gynecologic_oncology',
                'metadata_json': json.dumps({'phase': 'PHASE2'}),
                'biomarker_requirements': json.dumps(['BRCA1']),
                'locations_data': json.dumps([{'facility': 'Test Hospital', 'state': 'NY'}]),
                'eligibility_text': 'Test eligibility',
                'description_text': 'Test description'
            }
        ])
        
        result = await service.search_trials(
            query="ovarian cancer BRCA1",
            disease_category="gynecologic_oncology",
            top_k=10,
            min_score=0.5
        )
        
        assert result['success'] is True
        assert len(result['data']['found_trials']) == 1
        assert result['data']['found_trials'][0]['nct_id'] == 'NCT12345'
        assert result['data']['found_trials'][0]['similarity_score'] == 0.85
        assert result['provenance']['service'] == 'ClinicalTrialSearchService'
    
    @pytest.mark.asyncio
    async def test_search_trials_filters_by_min_score(self, service, mock_db_connections):
        """Test that trials below min_score are filtered out."""
        mock_collection = mock_db_connections.get_vector_db_collection.return_value
        mock_collection.find = Mock(return_value=[
            {
                '$similarity': 0.85,  # Above threshold
                'nct_id': 'NCT11111',
                'title': 'High Match',
                'status': 'RECRUITING',
                'source_url': 'url1',
                'eligibility_text': 'text1',
                'description_text': 'desc1'
            },
            {
                '$similarity': 0.35,  # Below threshold
                'nct_id': 'NCT22222',
                'title': 'Low Match',
                'status': 'RECRUITING',
                'source_url': 'url2',
                'eligibility_text': 'text2',
                'description_text': 'desc2'
            }
        ])
        
        result = await service.search_trials(
            query="test query",
            min_score=0.5
        )
        
        assert result['success'] is True
        assert len(result['data']['found_trials']) == 1
        assert result['data']['found_trials'][0]['nct_id'] == 'NCT11111'
    
    @pytest.mark.asyncio
    async def test_search_trials_handles_missing_collection(self, service, mock_db_connections):
        """Test graceful handling when AstraDB collection unavailable."""
        mock_db_connections.get_vector_db_collection.return_value = None
        
        result = await service.search_trials(query="test query")
        
        assert result['success'] is False
        assert 'error' in result
        assert result['data']['found_trials'] == []
    
    @pytest.mark.asyncio
    async def test_search_trials_handles_exception(self, service, mock_db_connections):
        """Test exception handling during search."""
        mock_collection = mock_db_connections.get_vector_db_collection.return_value
        mock_collection.find = Mock(side_effect=Exception("Database error"))
        
        result = await service.search_trials(query="test query")
        
        assert result['success'] is False
        assert 'error' in result
        assert "Database error" in result['error']
    
    @pytest.mark.asyncio
    async def test_get_trial_details_success(self, service, mock_db_connections):
        """Test retrieving trial details by NCT ID."""
        mock_conn = mock_db_connections.get_sqlite_connection.return_value
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock Row object
        mock_row = {
            'nct_id': 'NCT12345',
            'title': 'Test Trial',
            'status': 'RECRUITING'
        }
        mock_cursor.fetchone.return_value = mock_row
        
        result = await service.get_trial_details('NCT12345')
        
        assert result == mock_row
        mock_cursor.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_trial_details_not_found(self, service, mock_db_connections):
        """Test handling when trial not found."""
        mock_conn = mock_db_connections.get_sqlite_connection.return_value
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None
        
        result = await service.get_trial_details('NCT99999')
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_filter_by_state(self, service):
        """Test state filtering."""
        trials = [
            {
                'nct_id': 'NCT11111',
                'locations_data': json.dumps([
                    {'facility': 'Hospital 1', 'state': 'NY'},
                    {'facility': 'Hospital 2', 'state': 'CA'}
                ])
            },
            {
                'nct_id': 'NCT22222',
                'locations_data': json.dumps([
                    {'facility': 'Hospital 3', 'state': 'TX'}
                ])
            },
            {
                'nct_id': 'NCT33333',
                'locations_data': json.dumps([
                    {'facility': 'Hospital 4', 'state': 'NY'}
                ])
            }
        ]
        
        filtered = await service.filter_by_state(trials, 'NY')
        
        assert len(filtered) == 2
        assert filtered[0]['nct_id'] == 'NCT11111'
        assert filtered[1]['nct_id'] == 'NCT33333'
    
    def test_parse_biomarkers(self, service):
        """Test biomarker parsing."""
        doc = {'biomarker_requirements': json.dumps(['BRCA1', 'BRCA2'])}
        result = service._parse_biomarkers(doc)
        assert result == ['BRCA1', 'BRCA2']
        
        # Test with empty/missing field
        doc_empty = {}
        result_empty = service._parse_biomarkers(doc_empty)
        assert result_empty == []
    
    def test_parse_locations(self, service):
        """Test locations parsing."""
        locations = [
            {'facility': 'Hospital 1', 'state': 'NY'},
            {'facility': 'Hospital 2', 'state': 'CA'}
        ]
        doc = {'locations_data': json.dumps(locations)}
        result = service._parse_locations(doc)
        assert result == locations
        
        # Test with empty/missing field
        doc_empty = {}
        result_empty = service._parse_locations(doc_empty)
        assert result_empty == []

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

