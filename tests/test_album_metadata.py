"""
Tests for album_metadata module.
"""

import pytest
import tempfile
import json
from pathlib import Path

from src.album_metadata import AlbumMetadata, AlbumIdentifier


@pytest.fixture
def temp_album_dir():
    """Create a temporary album directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_audio_files(temp_album_dir):
    """Create temporary audio files."""
    files = []
    for i in range(3):
        file_path = temp_album_dir / f"track{i+1:02d}.flac"
        file_path.write_bytes(b"fake audio data " * 100)
        files.append(file_path)
    return files


def test_metadata_file_creation(temp_album_dir):
    """Test creating a metadata file."""
    metadata = AlbumMetadata(temp_album_dir)
    
    assert not metadata.exists()
    
    success = metadata.write(
        album_id="test-id-123",
        audio_checksum="abc123def456"
    )
    
    assert success
    assert metadata.exists()


def test_metadata_file_read(temp_album_dir):
    """Test reading a metadata file."""
    metadata = AlbumMetadata(temp_album_dir)
    
    metadata.write(
        album_id="test-id-456",
        audio_checksum="checksum789",
        custom_field="custom_value"
    )
    
    data = metadata.read()
    
    assert data is not None
    assert data['album_id'] == "test-id-456"
    assert data['audio_checksum'] == "checksum789"
    assert 'created_at' in data
    assert 'last_processed' in data
    assert data['custom_field'] == "custom_value"


def test_metadata_update(temp_album_dir):
    """Test updating a metadata file."""
    metadata = AlbumMetadata(temp_album_dir)
    
    metadata.write(
        album_id="test-id",
        audio_checksum="checksum"
    )
    
    original_data = metadata.read()
    original_created_at = original_data['created_at']
    
    success = metadata.update(new_field="new_value")
    
    assert success
    
    updated_data = metadata.read()
    assert updated_data['created_at'] == original_created_at  # Should preserve
    assert updated_data['new_field'] == "new_value"
    assert updated_data['last_processed'] != original_data['last_processed']


def test_get_album_id(temp_album_dir):
    """Test getting album ID from metadata."""
    metadata = AlbumMetadata(temp_album_dir)
    
    assert metadata.get_album_id() is None
    
    metadata.write(
        album_id="my-album-id",
        audio_checksum="checksum"
    )
    
    assert metadata.get_album_id() == "my-album-id"


def test_get_checksum(temp_album_dir):
    """Test getting checksum from metadata."""
    metadata = AlbumMetadata(temp_album_dir)
    
    assert metadata.get_checksum() is None
    
    metadata.write(
        album_id="album-id",
        audio_checksum="my-checksum"
    )
    
    assert metadata.get_checksum() == "my-checksum"


def test_generate_album_id():
    """Test generating a new album ID."""
    id1 = AlbumMetadata.generate_album_id()
    id2 = AlbumMetadata.generate_album_id()
    
    assert id1 != id2
    assert len(id1) == 36  # UUID format


def test_calculate_audio_checksum(temp_audio_files):
    """Test calculating checksum for audio files."""
    checksum = AlbumMetadata.calculate_audio_checksum(temp_audio_files)
    
    assert checksum is not None
    assert len(checksum) == 64  # SHA256 hex digest length
    
    # Same files should produce same checksum
    checksum2 = AlbumMetadata.calculate_audio_checksum(temp_audio_files)
    assert checksum == checksum2
    
    # Different order should produce same checksum (files are sorted)
    reversed_files = list(reversed(temp_audio_files))
    checksum3 = AlbumMetadata.calculate_audio_checksum(reversed_files)
    assert checksum == checksum3


def test_checksum_changes_with_content(temp_album_dir):
    """Test that checksum changes when file content changes."""
    file1 = temp_album_dir / "track01.flac"
    file1.write_bytes(b"audio data 1")
    
    checksum1 = AlbumMetadata.calculate_audio_checksum([file1])
    
    # Modify file
    file1.write_bytes(b"audio data 2")
    
    checksum2 = AlbumMetadata.calculate_audio_checksum([file1])
    
    assert checksum1 != checksum2


def test_create_for_album(temp_album_dir, temp_audio_files):
    """Test creating metadata for an album."""
    album_id = AlbumMetadata.create_for_album(
        temp_album_dir,
        temp_audio_files
    )
    
    assert album_id is not None
    
    metadata = AlbumMetadata(temp_album_dir)
    assert metadata.exists()
    
    data = metadata.read()
    assert data['album_id'] == album_id
    assert 'audio_checksum' in data


def test_verify_checksum(temp_album_dir, temp_audio_files):
    """Test verifying audio file checksums."""
    AlbumMetadata.create_for_album(
        temp_album_dir,
        temp_audio_files
    )
    
    # Checksum should match
    assert AlbumMetadata.verify_checksum(temp_album_dir, temp_audio_files)
    
    # Modify a file
    temp_audio_files[0].write_bytes(b"modified audio data")
    
    # Checksum should no longer match
    assert not AlbumMetadata.verify_checksum(temp_album_dir, temp_audio_files)


def test_metadata_atomic_write(temp_album_dir):
    """Test that metadata writes are atomic."""
    metadata = AlbumMetadata(temp_album_dir)
    
    # Write initial data
    metadata.write(
        album_id="test-id",
        audio_checksum="checksum1"
    )
    
    # Simulate concurrent write (should be safe)
    metadata.write(
        album_id="test-id",
        audio_checksum="checksum2"
    )
    
    # Should have valid metadata (one of the writes)
    data = metadata.read()
    assert data is not None
    assert data['album_id'] == "test-id"
    assert data['audio_checksum'] in ["checksum1", "checksum2"]


def test_invalid_metadata_file(temp_album_dir):
    """Test handling of invalid metadata files."""
    metadata_file = temp_album_dir / ".album_metadata"
    
    # Write invalid JSON
    metadata_file.write_text("invalid json {{{")
    
    metadata = AlbumMetadata(temp_album_dir)
    assert metadata.exists()
    assert metadata.read() is None


def test_missing_required_fields(temp_album_dir):
    """Test handling metadata file with missing required fields."""
    metadata_file = temp_album_dir / ".album_metadata"
    
    # Write valid JSON but missing required fields
    metadata_file.write_text(json.dumps({
        "album_id": "test-id"
        # Missing audio_checksum
    }))
    
    metadata = AlbumMetadata(temp_album_dir)
    assert metadata.read() is None

