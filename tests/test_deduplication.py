"""
Tests for deduplication module.
"""

import pytest
import tempfile
from pathlib import Path

from src.database import MusicDatabase
from src.deduplication import DeduplicationManager, ProcessingStatus
from src.album_metadata import AlbumMetadata


@pytest.fixture
def dedup_manager(temp_db):
    """Create a deduplication manager."""
    return DeduplicationManager(temp_db, verify_checksums=True)


@pytest.fixture
def temp_album_dir():
    """Create a temporary album directory with audio files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        album_path = Path(tmpdir)
        
        # Create fake audio files
        audio_files = []
        for i in range(3):
            file_path = album_path / f"track{i+1:02d}.flac"
            file_path.write_bytes(b"fake audio data " * 100)
            audio_files.append(file_path)
        
        yield album_path, audio_files


def test_check_album_status_no_metadata(dedup_manager, temp_album_dir):
    """Test checking status of album without metadata file."""
    album_path, audio_files = temp_album_dir
    
    status = dedup_manager.check_album_status(album_path, audio_files)
    
    assert not status.is_processed
    assert status.reason == "No metadata file found"


def test_check_album_status_with_metadata_no_db(dedup_manager, temp_album_dir):
    """Test checking status with metadata but no database record."""
    album_path, audio_files = temp_album_dir
    
    # Create metadata file
    album_id = AlbumMetadata.create_for_album(album_path, audio_files)
    
    status = dedup_manager.check_album_status(album_path, audio_files)
    
    assert not status.is_processed
    assert status.album_id == album_id
    assert status.checksum_matches
    assert not status.in_database
    assert "not found in database" in status.reason


def test_check_album_status_fully_processed(dedup_manager, temp_album_dir):
    """Test checking status of fully processed album."""
    album_path, audio_files = temp_album_dir
    
    # Create metadata file
    album_id = AlbumMetadata.create_for_album(album_path, audio_files)
    
    # Create database record
    checksum = AlbumMetadata.calculate_audio_checksum(audio_files)
    dedup_manager.database.create_album(
        album_id=album_id,
        album_name="Test Album",
        source_path=str(album_path),
        audio_files_checksum=checksum,
        archive_path="/archive/path",
        playback_path="/playback/path"
    )
    
    # Add successful conversion history
    dedup_manager.database.add_processing_history(
        album_id=album_id,
        operation_type='convert',
        status='success'
    )
    
    status = dedup_manager.check_album_status(album_path, audio_files)
    
    assert status.is_processed
    assert status.in_database
    assert status.checksum_matches


def test_check_album_status_checksum_mismatch(dedup_manager, temp_album_dir):
    """Test detecting when audio files have changed."""
    album_path, audio_files = temp_album_dir
    
    # Create metadata file
    album_id = AlbumMetadata.create_for_album(album_path, audio_files)
    
    # Modify an audio file
    audio_files[0].write_bytes(b"modified audio data")
    
    status = dedup_manager.check_album_status(album_path, audio_files)
    
    assert not status.is_processed
    assert not status.checksum_matches
    assert "checksum mismatch" in status.reason


def test_find_duplicate_by_checksum(dedup_manager, temp_album_dir):
    """Test finding duplicate albums by checksum."""
    album_path, audio_files = temp_album_dir
    
    # Create first album in database
    checksum = AlbumMetadata.calculate_audio_checksum(audio_files)
    dedup_manager.database.create_album(
        album_id="album-1",
        album_name="Original Album",
        source_path="/original/path",
        audio_files_checksum=checksum
    )
    
    # Try to find duplicate
    duplicate = dedup_manager.find_duplicate_by_checksum(audio_files)
    
    assert duplicate is not None
    assert duplicate['album_id'] == "album-1"
    assert duplicate['audio_files_checksum'] == checksum


def test_should_skip_album(dedup_manager, temp_album_dir):
    """Test should_skip_album decision making."""
    album_path, audio_files = temp_album_dir
    
    # Initially should not skip (not processed)
    should_skip, reason = dedup_manager.should_skip_album(album_path, audio_files)
    assert not should_skip
    
    # Process the album
    album_id = AlbumMetadata.create_for_album(album_path, audio_files)
    checksum = AlbumMetadata.calculate_audio_checksum(audio_files)
    
    dedup_manager.database.create_album(
        album_id=album_id,
        album_name="Test Album",
        source_path=str(album_path),
        audio_files_checksum=checksum,
        archive_path="/archive",
        playback_path="/playback"
    )
    
    dedup_manager.database.add_processing_history(
        album_id=album_id,
        operation_type='convert',
        status='success'
    )
    
    # Now should skip
    should_skip, reason = dedup_manager.should_skip_album(album_path, audio_files)
    assert should_skip
    assert "Already processed" in reason
    
    # Force reprocess should not skip
    should_skip, reason = dedup_manager.should_skip_album(
        album_path,
        audio_files,
        force_reprocess=True
    )
    assert not should_skip


def test_get_or_create_album_id(dedup_manager, temp_album_dir):
    """Test getting or creating deterministic album ID."""
    album_path, audio_files = temp_album_dir
    
    # First call should create new deterministic ID
    album_id1 = dedup_manager.get_or_create_album_id(album_path, audio_files)
    assert album_id1 is not None
    
    # Metadata file should exist
    metadata = AlbumMetadata(album_path)
    assert metadata.exists()
    assert metadata.get_album_id() == album_id1
    
    # Second call should return same ID (from metadata file)
    album_id2 = dedup_manager.get_or_create_album_id(album_path, audio_files)
    assert album_id2 == album_id1
    
    # ID should be deterministic - same files = same ID
    direct_id = AlbumMetadata.generate_album_id(audio_files)
    assert album_id1 == direct_id


def test_get_or_create_album_id_deterministic_across_locations(dedup_manager):
    """Test that same audio content in different locations produces same ID."""
    with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
        # Create same audio files in two different locations
        audio_files1 = []
        audio_files2 = []
        
        for i in range(3):
            # Location 1
            file1 = Path(tmpdir1) / f"track{i+1:02d}.flac"
            file1.write_bytes(b"fake audio data " * 100)
            audio_files1.append(file1)
            
            # Location 2 - SAME CONTENT
            file2 = Path(tmpdir2) / f"track{i+1:02d}.flac"
            file2.write_bytes(b"fake audio data " * 100)
            audio_files2.append(file2)
        
        # Generate IDs for both locations
        album_id1 = dedup_manager.get_or_create_album_id(Path(tmpdir1), audio_files1)
        album_id2 = dedup_manager.get_or_create_album_id(Path(tmpdir2), audio_files2)
        
        # Same content = same deterministic ID
        assert album_id1 == album_id2


def test_incomplete_processing(dedup_manager, temp_album_dir):
    """Test detecting incomplete processing."""
    album_path, audio_files = temp_album_dir
    
    album_id = AlbumMetadata.create_for_album(album_path, audio_files)
    checksum = AlbumMetadata.calculate_audio_checksum(audio_files)
    
    # Create album without playback_path (incomplete)
    dedup_manager.database.create_album(
        album_id=album_id,
        album_name="Test Album",
        source_path=str(album_path),
        audio_files_checksum=checksum,
        archive_path="/archive"
        # Missing playback_path
    )
    
    status = dedup_manager.check_album_status(album_path, audio_files)
    
    assert not status.is_processed
    assert status.in_database
    assert "incomplete" in status.reason.lower()

