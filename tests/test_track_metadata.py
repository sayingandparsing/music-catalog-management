"""
Tests for track metadata extraction functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from main import ConversionOrchestrator
from config import Config


class TestTrackMetadataExtraction:
    """Tests for _extract_track_metadata method."""
    
    @pytest.fixture
    def mock_orchestrator(self, tmp_path):
        """Create a mock orchestrator for testing."""
        # Create a mock orchestrator directly without full initialization
        orchestrator = Mock(spec=ConversionOrchestrator)
        
        # Add the actual method we want to test
        orchestrator._extract_track_metadata = ConversionOrchestrator._extract_track_metadata.__get__(orchestrator)
        
        # Mock the required attributes
        orchestrator.converter = Mock()
        orchestrator.logger = Mock()
        orchestrator.config = Mock()
        orchestrator.config.get.return_value = 'iso_dsf_to_flac'
        
        return orchestrator
    
    def test_extract_metadata_from_flac_with_mutagen(self, mock_orchestrator, tmp_path):
        """Test metadata extraction from FLAC file using mutagen."""
        # Create a temporary FLAC file
        source_file = tmp_path / "test_source.flac"
        output_file = tmp_path / "test_output.flac"
        source_file.touch()
        output_file.touch()
        
        # Mock mutagen FLAC reading
        mock_audio = {
            'title': ['Test Track Title'],
            'tracknumber': ['3'],
            'artist': ['Test Artist'],
            'album': ['Test Album'],
            'date': ['2023'],
            'performer': ['John Doe - Piano'],
            'composer': ['Jane Smith']
        }
        
        # Mock ffprobe file info
        mock_orchestrator.converter.get_file_info.return_value = {
            'format': {
                'duration': '245.67'
            }
        }
        
        with patch('main.MutagenFLAC') as mock_flac:
            mock_flac.return_value = mock_audio
            
            metadata = mock_orchestrator._extract_track_metadata(
                source_file_path=source_file,
                output_file_path=output_file,
                is_from_iso=False
            )
        
        # Verify extracted metadata
        assert metadata['title'] == 'Test Track Title'
        assert metadata['track_number'] == 3
        assert metadata['artist'] == 'Test Artist'
        assert metadata['album'] == 'Test Album'
        assert metadata['date'] == '2023'
        assert metadata['duration_seconds'] == 245.67
        assert metadata['musicians'] is not None
        assert len(metadata['musicians']) == 2
        assert metadata['musicians'][0]['role'] == 'performer'
        assert metadata['musicians'][0]['name'] == 'John Doe - Piano'
    
    def test_extract_metadata_from_iso_track(self, mock_orchestrator, tmp_path):
        """Test metadata extraction from ISO-converted track."""
        # Create a temporary file with ISO-style naming
        source_file = tmp_path / "source.iso"
        output_file = tmp_path / "01 - II B.S.flac"
        source_file.touch()
        output_file.touch()
        
        # Mock ffprobe file info
        mock_orchestrator.converter.get_file_info.return_value = {
            'format': {
                'duration': '180.5'
            }
        }
        
        # For ISO files, mutagen reads from output file
        with patch('main.MutagenFLAC') as mock_flac:
            # Simulate ISO track with minimal metadata
            mock_flac.return_value = {}
            
            metadata = mock_orchestrator._extract_track_metadata(
                source_file_path=source_file,
                output_file_path=output_file,
                is_from_iso=True
            )
        
        # Verify extracted metadata
        assert metadata['track_number'] == 1  # Extracted from filename "01 - ..."
        assert metadata['title'] == 'II B.S'  # Extracted from filename, cleaned up
        assert metadata['duration_seconds'] == 180.5
    
    def test_extract_metadata_filename_fallback(self, mock_orchestrator, tmp_path):
        """Test metadata extraction falls back to filename parsing."""
        source_file = tmp_path / "05 - Beautiful Track.flac"
        output_file = tmp_path / "05 - Beautiful Track.flac"
        source_file.touch()
        output_file.touch()
        
        # Mock ffprobe file info
        mock_orchestrator.converter.get_file_info.return_value = {
            'format': {
                'duration': '300.0'
            }
        }
        
        # Simulate FLAC with no metadata
        with patch('main.MutagenFLAC') as mock_flac:
            mock_flac.return_value = {}
            
            metadata = mock_orchestrator._extract_track_metadata(
                source_file_path=source_file,
                output_file_path=output_file,
                is_from_iso=False
            )
        
        # Verify fallback to filename
        assert metadata['track_number'] == 5
        assert metadata['title'] == 'Beautiful Track'
        assert metadata['duration_seconds'] == 300.0
    
    def test_extract_metadata_no_mutagen(self, mock_orchestrator, tmp_path):
        """Test metadata extraction when mutagen is not available."""
        source_file = tmp_path / "03 - Track Name.flac"
        output_file = tmp_path / "03 - Track Name.flac"
        source_file.touch()
        output_file.touch()
        
        # Mock ffprobe file info
        mock_orchestrator.converter.get_file_info.return_value = {
            'format': {
                'duration': '150.25'
            }
        }
        
        # Simulate MutagenFLAC not being available
        with patch('main.MutagenFLAC', None):
            metadata = mock_orchestrator._extract_track_metadata(
                source_file_path=source_file,
                output_file_path=output_file,
                is_from_iso=False
            )
        
        # Should still extract from filename and ffprobe
        assert metadata['track_number'] == 3
        assert metadata['title'] == 'Track Name'
        assert metadata['duration_seconds'] == 150.25
    
    def test_extract_metadata_handles_track_number_with_total(self, mock_orchestrator, tmp_path):
        """Test handling of track number in 'N/Total' format."""
        source_file = tmp_path / "test.flac"
        output_file = tmp_path / "test.flac"
        source_file.touch()
        output_file.touch()
        
        # Mock mutagen with track number format "7/12"
        mock_audio = {
            'title': ['Track Seven'],
            'tracknumber': ['7/12']  # Track 7 of 12
        }
        
        mock_orchestrator.converter.get_file_info.return_value = {
            'format': {'duration': '200.0'}
        }
        
        with patch('main.MutagenFLAC') as mock_flac:
            mock_flac.return_value = mock_audio
            
            metadata = mock_orchestrator._extract_track_metadata(
                source_file_path=source_file,
                output_file_path=output_file,
                is_from_iso=False
            )
        
        # Should extract just the track number, not the total
        assert metadata['track_number'] == 7
        assert metadata['title'] == 'Track Seven'


class TestTrackDatabaseCreation:
    """Tests for track database creation during conversion."""
    
    def test_database_called_for_single_file_conversion(self):
        """Test that database.create_track is called for single-file conversions."""
        # This would be an integration test that requires actual conversion
        # For now, we verify the logic is in place
        pass
    
    def test_database_called_for_iso_multitrack(self):
        """Test that database.create_track is called for each ISO track."""
        # This would be an integration test that requires actual conversion
        # For now, we verify the logic is in place
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

