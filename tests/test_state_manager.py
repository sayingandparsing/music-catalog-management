"""
Unit tests for state_manager module (StateManager, AlbumStatus, etc.).
"""

import pytest
import json
import time
from pathlib import Path
from datetime import datetime
from state_manager import (
    StateManager,
    AlbumStatus,
    FileConversionState,
    AlbumConversionState,
    ConversionSession
)


class TestAlbumStatus:
    """Tests for AlbumStatus enum."""
    
    def test_album_status_values(self):
        """Test AlbumStatus enum values."""
        assert AlbumStatus.PENDING.value == "pending"
        assert AlbumStatus.ARCHIVING.value == "archiving"
        assert AlbumStatus.CONVERTING.value == "converting"
        assert AlbumStatus.COMPLETED.value == "completed"
        assert AlbumStatus.FAILED.value == "failed"
        assert AlbumStatus.SKIPPED.value == "skipped"


class TestDataclasses:
    """Tests for state dataclasses."""
    
    def test_file_conversion_state(self):
        """Test FileConversionState dataclass."""
        file_state = FileConversionState(
            source_path="/path/to/source.dsf",
            output_path="/path/to/output.flac",
            status="pending"
        )
        
        assert file_state.source_path == "/path/to/source.dsf"
        assert file_state.output_path == "/path/to/output.flac"
        assert file_state.status == "pending"
        assert file_state.attempts == 0
        assert file_state.error_message is None
        assert file_state.completed_at is None
    
    def test_album_conversion_state(self):
        """Test AlbumConversionState dataclass."""
        album_state = AlbumConversionState(
            album_path="/path/to/album",
            album_name="Test Album",
            status="pending"
        )
        
        assert album_state.album_path == "/path/to/album"
        assert album_state.album_name == "Test Album"
        assert album_state.status == "pending"
        assert album_state.archive_path is None
        assert album_state.files == []
    
    def test_conversion_session(self):
        """Test ConversionSession dataclass."""
        session = ConversionSession(
            session_id="20250101_120000",
            input_dir="/input",
            output_dir="/output",
            archive_dir="/archive",
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False,
            started_at="2025-01-01T12:00:00"
        )
        
        assert session.session_id == "20250101_120000"
        assert session.input_dir == "/input"
        assert session.conversion_mode == "iso_dsf_to_flac"
        assert session.sample_rate == 88200
        assert session.bit_depth == 24
        assert session.enrich_metadata is False
        assert session.albums == []
        assert session.paused is False


class TestStateManagerInitialization:
    """Tests for StateManager initialization."""
    
    def test_state_manager_init_default(self, temp_state_dir):
        """Test StateManager initialization with custom directory."""
        manager = StateManager(state_dir=temp_state_dir)
        
        assert manager.state_dir == temp_state_dir
        assert manager.state_file == temp_state_dir / "conversion_state.json"
        assert manager.pause_signal_file == temp_state_dir / "PAUSE"
        assert temp_state_dir.exists()
        assert manager.session is None
    
    def test_state_manager_creates_directory(self, temp_dir):
        """Test that StateManager creates state directory if it doesn't exist."""
        state_dir = temp_dir / "new_state"
        assert not state_dir.exists()
        
        manager = StateManager(state_dir=state_dir)
        
        assert state_dir.exists()
        assert state_dir.is_dir()


class TestSessionManagement:
    """Tests for session creation and management."""
    
    def test_create_session(self, temp_state_dir):
        """Test creating a new session."""
        manager = StateManager(state_dir=temp_state_dir)
        
        session = manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        assert session is not None
        assert manager.session == session
        assert session.input_dir == "/input"
        assert session.output_dir == "/output"
        assert session.conversion_mode == "iso_dsf_to_flac"
        assert session.sample_rate == 88200
        assert session.bit_depth == 24
        
        # State file should be created
        assert manager.state_file.exists()
    
    def test_session_id_format(self, temp_state_dir):
        """Test that session ID has correct format (timestamp)."""
        manager = StateManager(state_dir=temp_state_dir)
        
        session = manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        # Session ID should be in format YYYYMMDD_HHMMSS
        assert len(session.session_id) == 15
        assert "_" in session.session_id
    
    def test_load_nonexistent_session(self, temp_state_dir):
        """Test loading session when no state file exists."""
        manager = StateManager(state_dir=temp_state_dir)
        
        session = manager.load_session()
        
        assert session is None
    
    def test_save_and_load_session(self, temp_state_dir):
        """Test saving and loading a session."""
        manager = StateManager(state_dir=temp_state_dir)
        
        # Create session
        original_session = manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=True
        )
        
        # Create new manager and load session
        manager2 = StateManager(state_dir=temp_state_dir)
        loaded_session = manager2.load_session()
        
        assert loaded_session is not None
        assert loaded_session.session_id == original_session.session_id
        assert loaded_session.input_dir == original_session.input_dir
        assert loaded_session.conversion_mode == original_session.conversion_mode
        assert loaded_session.enrich_metadata == original_session.enrich_metadata
    
    def test_mark_completed(self, temp_state_dir):
        """Test marking session as completed."""
        manager = StateManager(state_dir=temp_state_dir)
        
        session = manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        assert session.completed_at is None
        
        manager.mark_completed()
        
        assert manager.session.completed_at is not None
    
    def test_clear_state(self, temp_state_dir):
        """Test clearing state."""
        manager = StateManager(state_dir=temp_state_dir)
        
        manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        assert manager.state_file.exists()
        assert manager.session is not None
        
        manager.clear_state()
        
        assert not manager.state_file.exists()
        assert manager.session is None


class TestAlbumManagement:
    """Tests for album management."""
    
    def test_add_album(self, temp_state_dir, temp_dir):
        """Test adding an album to session."""
        manager = StateManager(state_dir=temp_state_dir)
        
        manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        album_path = temp_dir / "Test Album"
        music_files = [
            (album_path / "01.dsf", album_path / "01.flac"),
            (album_path / "02.dsf", album_path / "02.flac")
        ]
        
        manager.add_album(album_path, "Test Album", music_files)
        
        assert len(manager.session.albums) == 1
        album = manager.session.albums[0]
        assert album.album_name == "Test Album"
        assert album.status == AlbumStatus.PENDING.value
        assert len(album.files) == 2
    
    def test_add_album_without_session(self, temp_state_dir):
        """Test that adding album without active session raises error."""
        manager = StateManager(state_dir=temp_state_dir)
        
        with pytest.raises(RuntimeError, match="No active session"):
            manager.add_album(Path("/album"), "Album", [])
    
    def test_update_album_status(self, temp_state_dir, temp_dir):
        """Test updating album status."""
        manager = StateManager(state_dir=temp_state_dir)
        
        manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        album_path = temp_dir / "Test Album"
        manager.add_album(album_path, "Test Album", [])
        
        # Update status
        manager.update_album_status(
            album_path,
            AlbumStatus.CONVERTING
        )
        
        album = manager.session.albums[0]
        assert album.status == AlbumStatus.CONVERTING.value
    
    def test_update_album_with_archive_path(self, temp_state_dir, temp_dir):
        """Test updating album with archive path."""
        manager = StateManager(state_dir=temp_state_dir)
        
        manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        album_path = temp_dir / "Test Album"
        manager.add_album(album_path, "Test Album", [])
        
        archive_path = Path("/archive/Test_Album_20250101")
        manager.update_album_status(
            album_path,
            AlbumStatus.CONVERTING,
            archive_path=archive_path
        )
        
        album = manager.session.albums[0]
        assert album.archive_path == str(archive_path)
    
    def test_update_album_with_error(self, temp_state_dir, temp_dir):
        """Test updating album status with error message."""
        manager = StateManager(state_dir=temp_state_dir)
        
        manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        album_path = temp_dir / "Test Album"
        manager.add_album(album_path, "Test Album", [])
        
        manager.update_album_status(
            album_path,
            AlbumStatus.FAILED,
            error_message="Conversion failed"
        )
        
        album = manager.session.albums[0]
        assert album.status == AlbumStatus.FAILED.value
        assert album.error_message == "Conversion failed"
        assert album.completed_at is not None
    
    def test_get_pending_albums(self, temp_state_dir, temp_dir):
        """Test getting pending albums."""
        manager = StateManager(state_dir=temp_state_dir)
        
        manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        # Add albums with different statuses
        album1 = temp_dir / "Album1"
        album2 = temp_dir / "Album2"
        album3 = temp_dir / "Album3"
        
        manager.add_album(album1, "Album1", [])
        manager.add_album(album2, "Album2", [])
        manager.add_album(album3, "Album3", [])
        
        manager.update_album_status(album2, AlbumStatus.COMPLETED)
        
        pending = manager.get_pending_albums()
        
        assert len(pending) == 2
        pending_names = {a.album_name for a in pending}
        assert "Album1" in pending_names
        assert "Album3" in pending_names


class TestFileManagement:
    """Tests for file status management."""
    
    def test_update_file_status(self, temp_state_dir, temp_dir):
        """Test updating file conversion status."""
        manager = StateManager(state_dir=temp_state_dir)
        
        manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        album_path = temp_dir / "Album"
        file_path = album_path / "01.dsf"
        music_files = [(file_path, album_path / "01.flac")]
        
        manager.add_album(album_path, "Album", music_files)
        
        # Update file status
        manager.update_file_status(album_path, file_path, "converting")
        
        file_state = manager.session.albums[0].files[0]
        assert file_state.status == "converting"
        assert file_state.attempts == 1
    
    def test_update_file_status_multiple_attempts(self, temp_state_dir, temp_dir):
        """Test that attempts are incremented properly."""
        manager = StateManager(state_dir=temp_state_dir)
        
        manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        album_path = temp_dir / "Album"
        file_path = album_path / "01.dsf"
        music_files = [(file_path, album_path / "01.flac")]
        
        manager.add_album(album_path, "Album", music_files)
        
        # Multiple attempts
        manager.update_file_status(album_path, file_path, "converting")
        manager.update_file_status(album_path, file_path, "converting")
        manager.update_file_status(album_path, file_path, "converting")
        
        file_state = manager.session.albums[0].files[0]
        assert file_state.attempts == 3
    
    def test_update_file_status_with_error(self, temp_state_dir, temp_dir):
        """Test updating file status with error message."""
        manager = StateManager(state_dir=temp_state_dir)
        
        manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        album_path = temp_dir / "Album"
        file_path = album_path / "01.dsf"
        music_files = [(file_path, album_path / "01.flac")]
        
        manager.add_album(album_path, "Album", music_files)
        
        manager.update_file_status(
            album_path,
            file_path,
            "failed",
            error_message="ffmpeg error"
        )
        
        file_state = manager.session.albums[0].files[0]
        assert file_state.status == "failed"
        assert file_state.error_message == "ffmpeg error"
        assert file_state.completed_at is not None
    
    def test_update_file_status_completed(self, temp_state_dir, temp_dir):
        """Test updating file status to completed."""
        manager = StateManager(state_dir=temp_state_dir)
        
        manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        album_path = temp_dir / "Album"
        file_path = album_path / "01.dsf"
        music_files = [(file_path, album_path / "01.flac")]
        
        manager.add_album(album_path, "Album", music_files)
        
        manager.update_file_status(album_path, file_path, "completed")
        
        file_state = manager.session.albums[0].files[0]
        assert file_state.status == "completed"
        assert file_state.completed_at is not None


class TestPauseResume:
    """Tests for pause/resume functionality."""
    
    def test_check_pause_signal_false(self, temp_state_dir):
        """Test checking pause signal when it doesn't exist."""
        manager = StateManager(state_dir=temp_state_dir)
        
        assert manager.check_pause_signal() is False
    
    def test_create_pause_signal(self, temp_state_dir):
        """Test creating pause signal."""
        manager = StateManager(state_dir=temp_state_dir)
        
        manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        manager.create_pause_signal()
        
        assert manager.pause_signal_file.exists()
        assert manager.check_pause_signal() is True
        assert manager.session.paused is True
    
    def test_clear_pause_signal(self, temp_state_dir):
        """Test clearing pause signal."""
        manager = StateManager(state_dir=temp_state_dir)
        
        manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        manager.create_pause_signal()
        assert manager.check_pause_signal() is True
        
        manager.clear_pause_signal()
        
        assert not manager.pause_signal_file.exists()
        assert manager.check_pause_signal() is False
        assert manager.session.paused is False


class TestStatistics:
    """Tests for get_statistics method."""
    
    def test_statistics_empty_session(self, temp_state_dir):
        """Test statistics with no albums."""
        manager = StateManager(state_dir=temp_state_dir)
        
        manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        stats = manager.get_statistics()
        
        assert stats['albums_total'] == 0
        assert stats['albums_completed'] == 0
        assert stats['files_total'] == 0
    
    def test_statistics_with_albums(self, temp_state_dir, temp_dir):
        """Test statistics calculation with albums."""
        manager = StateManager(state_dir=temp_state_dir)
        
        manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        # Add albums
        album1 = temp_dir / "Album1"
        album2 = temp_dir / "Album2"
        
        manager.add_album(album1, "Album1", [
            (album1 / "01.dsf", album1 / "01.flac"),
            (album1 / "02.dsf", album1 / "02.flac")
        ])
        manager.add_album(album2, "Album2", [
            (album2 / "01.dsf", album2 / "01.flac")
        ])
        
        # Update statuses
        manager.update_album_status(album1, AlbumStatus.COMPLETED)
        manager.update_file_status(album1, album1 / "01.dsf", "completed")
        manager.update_file_status(album1, album1 / "02.dsf", "completed")
        
        manager.update_album_status(album2, AlbumStatus.FAILED)
        manager.update_file_status(album2, album2 / "01.dsf", "failed")
        
        stats = manager.get_statistics()
        
        assert stats['albums_total'] == 2
        assert stats['albums_completed'] == 1
        assert stats['albums_failed'] == 1
        assert stats['files_total'] == 3
        assert stats['files_completed'] == 2
        assert stats['files_failed'] == 1
    
    def test_statistics_no_session(self, temp_state_dir):
        """Test statistics when no session exists."""
        manager = StateManager(state_dir=temp_state_dir)
        
        stats = manager.get_statistics()
        
        assert stats == {}


class TestStatePersistence:
    """Tests for state file persistence and recovery."""
    
    def test_state_file_json_format(self, temp_state_dir):
        """Test that state file is valid JSON."""
        manager = StateManager(state_dir=temp_state_dir)
        
        manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        # Read state file directly
        with open(manager.state_file, 'r') as f:
            data = json.load(f)
        
        assert 'session_id' in data
        assert 'input_dir' in data
        assert 'albums' in data
    
    def test_atomic_write(self, temp_state_dir):
        """Test that state saves use atomic write."""
        manager = StateManager(state_dir=temp_state_dir)
        
        manager.create_session(
            input_dir=Path("/input"),
            output_dir=Path("/output"),
            archive_dir=Path("/archive"),
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        # State file should exist
        assert manager.state_file.exists()
        
        # Temp file should not exist after save
        temp_file = manager.state_file.with_suffix('.tmp')
        assert not temp_file.exists()
    
    def test_load_corrupted_state(self, temp_state_dir):
        """Test loading corrupted state file."""
        manager = StateManager(state_dir=temp_state_dir)
        
        # Write corrupted JSON
        manager.state_file.write_text("{invalid json")
        
        # Should handle gracefully
        session = manager.load_session()
        
        assert session is None

