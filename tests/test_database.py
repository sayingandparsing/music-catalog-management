"""
Tests for database module.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from src.database import MusicDatabase


def test_database_initialization(temp_db):
    """Test database initialization and table creation."""
    assert temp_db.conn is not None
    
    # Check that tables exist
    tables = temp_db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    
    table_names = [t[0] for t in tables]
    assert 'albums' in table_names
    assert 'tracks' in table_names
    assert 'metadata_candidates' in table_names
    assert 'processing_history' in table_names


def test_create_album(temp_db):
    """Test creating an album record."""
    album_id = "test-album-123"
    
    success = temp_db.create_album(
        album_id=album_id,
        album_name="Test Album",
        source_path="/test/path",
        audio_files_checksum="abc123",
        artist="Test Artist",
        release_year=2023
    )
    
    assert success
    
    # Verify album was created
    album = temp_db.get_album_by_id(album_id)
    assert album is not None
    assert album['album_name'] == "Test Album"
    assert album['artist'] == "Test Artist"
    assert album['release_year'] == 2023


def test_update_album(temp_db):
    """Test updating an album record."""
    album_id = "test-album-456"
    
    temp_db.create_album(
        album_id=album_id,
        album_name="Test Album",
        source_path="/test/path",
        audio_files_checksum="abc123"
    )
    
    success = temp_db.update_album(
        album_id=album_id,
        label="Test Label",
        catalog_number="CAT-001"
    )
    
    assert success
    
    album = temp_db.get_album_by_id(album_id)
    assert album['label'] == "Test Label"
    assert album['catalog_number'] == "CAT-001"


def test_get_album_by_checksum(temp_db):
    """Test finding album by checksum."""
    checksum = "unique-checksum-789"
    
    temp_db.create_album(
        album_id="test-789",
        album_name="Test Album",
        source_path="/test/path",
        audio_files_checksum=checksum
    )
    
    album = temp_db.get_album_by_checksum(checksum)
    assert album is not None
    assert album['audio_files_checksum'] == checksum


def test_create_track(temp_db):
    """Test creating a track record."""
    album_id = "test-album-001"
    track_id = "test-track-001"
    
    # Create album first
    temp_db.create_album(
        album_id=album_id,
        album_name="Test Album",
        source_path="/test/path",
        audio_files_checksum="abc123"
    )
    
    success = temp_db.create_track(
        track_id=track_id,
        album_id=album_id,
        track_number=1,
        title="Test Track",
        file_path="/test/track.flac",
        file_size=1000000,
        file_format=".flac",
        dynamic_range_crest=12.5,
        dynamic_range_r128=8.3
    )
    
    assert success
    
    tracks = temp_db.get_tracks_by_album(album_id)
    assert len(tracks) == 1
    assert tracks[0]['title'] == "Test Track"
    assert tracks[0]['dynamic_range_crest'] == 12.5


def test_create_metadata_candidate(temp_db):
    """Test creating metadata candidate records."""
    album_id = "test-album-002"
    candidate_id = "test-candidate-001"
    
    temp_db.create_album(
        album_id=album_id,
        album_name="Test Album",
        source_path="/test/path",
        audio_files_checksum="abc123"
    )
    
    metadata = {
        'artist': 'Test Artist',
        'album': 'Test Album',
        'year': 2023
    }
    
    success = temp_db.create_metadata_candidate(
        candidate_id=candidate_id,
        album_id=album_id,
        source='musicbrainz',
        source_id='mb-123',
        rank=1,
        metadata_dict=metadata,
        confidence_score=0.95
    )
    
    assert success
    
    candidates = temp_db.get_metadata_candidates(album_id)
    assert len(candidates) == 1
    assert candidates[0]['source'] == 'musicbrainz'
    assert candidates[0]['rank'] == 1
    assert float(candidates[0]['confidence_score']) == 0.95


def test_add_processing_history(temp_db):
    """Test adding processing history records."""
    album_id = "test-album-003"
    
    temp_db.create_album(
        album_id=album_id,
        album_name="Test Album",
        source_path="/test/path",
        audio_files_checksum="abc123"
    )
    
    success = temp_db.add_processing_history(
        album_id=album_id,
        operation_type='convert',
        status='success',
        duration_seconds=123.45
    )
    
    assert success
    
    history = temp_db.get_processing_history(album_id)
    assert len(history) == 1
    assert history[0]['operation_type'] == 'convert'
    assert history[0]['status'] == 'success'
    assert float(history[0]['duration_seconds']) == 123.45


def test_search_albums(temp_db):
    """Test searching for albums."""
    temp_db.create_album(
        album_id="album-1",
        album_name="Jazz Masters",
        source_path="/path1",
        audio_files_checksum="check1",
        artist="Miles Davis",
        label="Columbia"
    )
    
    temp_db.create_album(
        album_id="album-2",
        album_name="Blue Note Collection",
        source_path="/path2",
        audio_files_checksum="check2",
        artist="John Coltrane",
        label="Blue Note"
    )
    
    # Search by artist
    results = temp_db.search_albums(artist="Miles")
    assert len(results) == 1
    assert results[0]['artist'] == "Miles Davis"
    
    # Search by label
    results = temp_db.search_albums(label="Blue")
    assert len(results) == 1
    assert results[0]['label'] == "Blue Note"


def test_get_statistics(temp_db):
    """Test getting database statistics."""
    # Create some test data
    temp_db.create_album(
        album_id="album-1",
        album_name="Album 1",
        source_path="/path1",
        audio_files_checksum="check1",
        artist="Artist 1"
    )
    
    temp_db.create_album(
        album_id="album-2",
        album_name="Album 2",
        source_path="/path2",
        audio_files_checksum="check2",
        artist="Artist 2"
    )
    
    temp_db.create_track(
        track_id="track-1",
        album_id="album-1",
        track_number=1,
        title="Track 1",
        file_path="/path/track1.flac"
    )
    
    stats = temp_db.get_statistics()
    
    assert stats['total_albums'] == 2
    assert stats['total_tracks'] == 1
    assert stats['total_artists'] == 2


def test_create_album_with_processed_id(temp_db):
    """Test creating album with processed_album_id."""
    album_id = "original-id-123"
    processed_id = "processed-id-456"
    
    success = temp_db.create_album(
        album_id=album_id,
        album_name="Test Album",
        source_path="/test/path",
        audio_files_checksum="abc123",
        processed_album_id=processed_id
    )
    
    assert success
    
    # Verify both IDs are stored
    album = temp_db.get_album_by_id(album_id)
    assert album is not None
    assert album['album_id'] == album_id
    assert album['processed_album_id'] == processed_id


def test_update_album_with_processed_id(temp_db):
    """Test updating album with processed_album_id."""
    album_id = "original-id-789"
    
    # Create album without processed ID
    temp_db.create_album(
        album_id=album_id,
        album_name="Test Album",
        source_path="/test/path",
        audio_files_checksum="abc123"
    )
    
    # Verify no processed ID initially
    album = temp_db.get_album_by_id(album_id)
    assert album['processed_album_id'] is None
    
    # Update with processed ID
    processed_id = "processed-id-updated"
    success = temp_db.update_album(
        album_id=album_id,
        processed_album_id=processed_id
    )
    
    assert success
    
    # Verify processed ID is now set
    album = temp_db.get_album_by_id(album_id)
    assert album['processed_album_id'] == processed_id

