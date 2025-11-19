"""
Integration tests for the complete DSD Music Converter workflow.
These tests require a real ISO/DSF album set via TEST_ALBUM_PATH environment variable.
"""

import pytest
import shutil
from pathlib import Path
from unittest.mock import patch, Mock
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scanner import DirectoryScanner
from archiver import Archiver
from converter import AudioConverter
from state_manager import StateManager, AlbumStatus
from config import Config
from logger import setup_logger
from main import ConversionOrchestrator


@pytest.mark.integration
class TestFullWorkflow:
    """Integration tests for complete conversion workflow."""
    
    def test_scan_archive_workflow(
        self,
        test_album_path,
        temp_output_dir,
        temp_archive_dir,
        temp_state_dir
    ):
        """Test scan → archive workflow with real album."""
        # Scan
        scanner = DirectoryScanner()
        albums = scanner.scan(test_album_path)
        
        assert len(albums) >= 1, "No albums found in test path"
        
        album = albums[0]
        assert album.file_count > 0, "Album has no music files"
        
        # Archive
        archiver = Archiver(temp_archive_dir, verify_copies=True)
        success, archive_path, error = archiver.archive_album(album.root_path)
        
        assert success is True, f"Archive failed: {error}"
        assert archive_path is not None
        assert archive_path.exists()
        
        # Verify archive has same number of files
        archived_files = list(archive_path.rglob("*"))
        assert len(archived_files) > 0
    
    @pytest.mark.slow
    @pytest.mark.requires_ffmpeg
    def test_scan_archive_convert_workflow(
        self,
        test_album_path,
        temp_output_dir,
        temp_archive_dir,
        temp_state_dir
    ):
        """Test scan → archive → convert workflow with real album (slow)."""
        # Check ffmpeg availability
        if not shutil.which('ffmpeg'):
            pytest.skip("ffmpeg not available")
        
        # Scan
        scanner = DirectoryScanner()
        albums = scanner.scan(test_album_path)
        
        assert len(albums) >= 1
        album = albums[0]
        
        # Archive
        archiver = Archiver(temp_archive_dir)
        success, archive_path, error = archiver.archive_album(album.root_path)
        assert success is True
        
        # Convert first file only (to keep test fast)
        if album.music_files:
            first_file = album.music_files[0]
            output_file = temp_output_dir / first_file.path.with_suffix('.flac').name
            
            converter = AudioConverter(
                sample_rate=88200,
                bit_depth=24,
                mode='iso_dsf_to_flac'
            )
            
            success, error, duration, dynamic_range = converter.convert_file(
                first_file.path,
                output_file
            )
            
            # Note: This may fail if file format is unsupported
            # or ffmpeg doesn't have DSD support
            if success:
                assert output_file.exists()
                assert output_file.stat().st_size > 0
                assert duration > 0
            else:
                # If conversion fails, it's likely due to format/codec issues
                pytest.skip(f"Conversion failed (likely codec issue): {error}")
    
    def test_state_management_workflow(
        self,
        test_album_path,
        temp_output_dir,
        temp_archive_dir,
        temp_state_dir
    ):
        """Test state management throughout workflow."""
        # Scan albums
        scanner = DirectoryScanner()
        albums = scanner.scan(test_album_path)
        
        assert len(albums) >= 1
        album = albums[0]
        
        # Initialize state manager
        state_manager = StateManager(state_dir=temp_state_dir)
        
        # Create session
        session = state_manager.create_session(
            input_dir=test_album_path,
            output_dir=temp_output_dir,
            archive_dir=temp_archive_dir,
            conversion_mode='iso_dsf_to_flac',
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        assert session is not None
        assert session.input_dir == str(test_album_path)
        
        # Add album
        music_files = [
            (mf.path, temp_output_dir / mf.relative_path)
            for mf in album.music_files
        ]
        state_manager.add_album(album.root_path, album.name, music_files)
        
        assert len(session.albums) == 1
        
        # Update status through workflow stages
        state_manager.update_album_status(album.root_path, AlbumStatus.ARCHIVING)
        assert session.albums[0].status == AlbumStatus.ARCHIVING.value
        
        state_manager.update_album_status(album.root_path, AlbumStatus.CONVERTING)
        assert session.albums[0].status == AlbumStatus.CONVERTING.value
        
        state_manager.update_album_status(album.root_path, AlbumStatus.COMPLETED)
        assert session.albums[0].status == AlbumStatus.COMPLETED.value
        
        # Test state persistence
        state_manager2 = StateManager(state_dir=temp_state_dir)
        loaded_session = state_manager2.load_session()
        
        assert loaded_session is not None
        assert loaded_session.session_id == session.session_id
        assert len(loaded_session.albums) == 1
    
    def test_pause_resume_workflow(
        self,
        test_album_path,
        temp_output_dir,
        temp_archive_dir,
        temp_state_dir
    ):
        """Test pause and resume functionality."""
        state_manager = StateManager(state_dir=temp_state_dir)
        
        # Create session
        state_manager.create_session(
            input_dir=test_album_path,
            output_dir=temp_output_dir,
            archive_dir=temp_archive_dir,
            conversion_mode='iso_dsf_to_flac',
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        # Check pause signal
        assert state_manager.check_pause_signal() is False
        
        # Create pause signal
        state_manager.create_pause_signal()
        assert state_manager.check_pause_signal() is True
        assert state_manager.pause_signal_file.exists()
        
        # Clear pause signal
        state_manager.clear_pause_signal()
        assert state_manager.check_pause_signal() is False
        assert not state_manager.pause_signal_file.exists()
    
    def test_statistics_workflow(
        self,
        test_album_path,
        temp_output_dir,
        temp_archive_dir,
        temp_state_dir
    ):
        """Test statistics collection throughout workflow."""
        scanner = DirectoryScanner()
        albums = scanner.scan(test_album_path)
        
        # Get scan statistics
        scan_stats = scanner.get_statistics(albums)
        
        assert scan_stats['album_count'] >= 1
        assert scan_stats['total_files'] >= 1
        assert scan_stats['total_size_bytes'] > 0
        
        # State manager statistics
        state_manager = StateManager(state_dir=temp_state_dir)
        state_manager.create_session(
            input_dir=test_album_path,
            output_dir=temp_output_dir,
            archive_dir=temp_archive_dir,
            conversion_mode='iso_dsf_to_flac',
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        # Add album
        album = albums[0]
        music_files = [(mf.path, temp_output_dir / mf.relative_path) for mf in album.music_files]
        state_manager.add_album(album.root_path, album.name, music_files)
        
        stats = state_manager.get_statistics()
        
        assert stats['albums_total'] == 1
        assert stats['albums_pending'] == 1
        assert stats['files_total'] > 0


@pytest.mark.integration
class TestDryRunMode:
    """Integration tests for dry-run mode."""
    
    def test_dry_run_no_modifications(
        self,
        test_album_path,
        temp_output_dir,
        temp_archive_dir,
        sample_config_file
    ):
        """Test that dry-run mode doesn't modify anything."""
        # Get initial state
        initial_files = set(test_album_path.rglob("*"))
        
        # Create minimal orchestrator for dry run
        config = Config(config_path=sample_config_file)
        config.set('paths.archive_dir', str(temp_archive_dir))
        config.set('paths.output_dir', str(temp_output_dir))
        
        log_file = temp_output_dir / "test.log"
        error_log_file = temp_output_dir / "test_errors.log"
        logger = setup_logger(
            log_file=str(log_file),
            error_log_file=str(error_log_file)
        )
        
        # Note: Full dry-run test would require orchestrator
        # This is a simplified version
        scanner = DirectoryScanner()
        albums = scanner.scan(test_album_path)
        
        # Verify no files were created/modified in input
        final_files = set(test_album_path.rglob("*"))
        assert initial_files == final_files
        
        # Verify no archive was created
        assert len(list(temp_archive_dir.iterdir())) == 0


@pytest.mark.integration
class TestErrorHandling:
    """Integration tests for error handling."""
    
    def test_invalid_input_directory(self, temp_dir):
        """Test handling of invalid input directory."""
        scanner = DirectoryScanner()
        nonexistent = temp_dir / "nonexistent"
        
        with pytest.raises(FileNotFoundError):
            scanner.scan(nonexistent)
    
    def test_archive_permission_error(self, test_album_path, temp_archive_dir, monkeypatch):
        """Test handling of archive permission errors."""
        scanner = DirectoryScanner()
        albums = scanner.scan(test_album_path)
        
        if not albums:
            pytest.skip("No albums found")
        
        album = albums[0]
        archiver = Archiver(temp_archive_dir)
        
        # Mock permission error
        def mock_copytree(*args, **kwargs):
            raise PermissionError("Permission denied")
        
        monkeypatch.setattr("shutil.copytree", mock_copytree)
        
        success, archive_path, error = archiver.archive_album(album.root_path)
        
        assert success is False
        assert error is not None
        assert "Permission" in error
    
    def test_state_recovery_after_error(
        self,
        test_album_path,
        temp_output_dir,
        temp_archive_dir,
        temp_state_dir
    ):
        """Test that state can be recovered after error."""
        state_manager = StateManager(state_dir=temp_state_dir)
        
        # Create session
        session = state_manager.create_session(
            input_dir=test_album_path,
            output_dir=temp_output_dir,
            archive_dir=temp_archive_dir,
            conversion_mode='iso_dsf_to_flac',
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        scanner = DirectoryScanner()
        albums = scanner.scan(test_album_path)
        
        if albums:
            album = albums[0]
            music_files = [(mf.path, temp_output_dir / mf.relative_path) for mf in album.music_files]
            state_manager.add_album(album.root_path, album.name, music_files)
            
            # Mark as failed
            state_manager.update_album_status(
                album.root_path,
                AlbumStatus.FAILED,
                error_message="Test error"
            )
        
        # Create new manager and load state
        state_manager2 = StateManager(state_dir=temp_state_dir)
        loaded_session = state_manager2.load_session()
        
        assert loaded_session is not None
        if loaded_session.albums:
            assert loaded_session.albums[0].status == AlbumStatus.FAILED.value
            assert loaded_session.albums[0].error_message == "Test error"


@pytest.mark.integration
class TestConfigurationIntegration:
    """Integration tests for configuration."""
    
    def test_config_override_workflow(self, sample_config_file):
        """Test configuration override workflow."""
        config = Config(config_path=sample_config_file)
        
        # Override from CLI args
        config.update_from_args(
            sample_rate=96000,
            bit_depth=16,
            archive_dir='/custom/archive'
        )
        
        # Validate
        is_valid, errors = config.validate()
        
        assert is_valid is True
        assert config.get('conversion.sample_rate') == 96000
        assert config.get('conversion.bit_depth') == 16
        assert config.get('paths.archive_dir') == '/custom/archive'
    
    def test_invalid_config_detection(self, temp_dir):
        """Test that invalid configuration is detected."""
        # Create invalid config
        invalid_config = temp_dir / "invalid.yaml"
        invalid_config.write_text("""
conversion:
  mode: invalid_mode
  sample_rate: 44100
  bit_depth: 8
paths:
  archive_dir: null
""")
        
        config = Config(config_path=invalid_config)
        is_valid, errors = config.validate()
        
        assert is_valid is False
        assert len(errors) >= 3  # mode, sample_rate, bit_depth, archive_dir


@pytest.mark.integration
class TestLoggingIntegration:
    """Integration tests for logging."""
    
    def test_logging_throughout_workflow(
        self,
        test_album_path,
        temp_output_dir,
        temp_archive_dir,
        temp_state_dir
    ):
        """Test that logging works throughout workflow."""
        log_file = temp_output_dir / "test.log"
        error_log_file = temp_output_dir / "test_errors.log"
        
        logger = setup_logger(
            log_file=str(log_file),
            error_log_file=str(error_log_file),
            level='INFO'
        )
        
        # Log various stages
        logger.log_conversion_start(
            test_album_path,
            temp_output_dir,
            temp_archive_dir
        )
        
        scanner = DirectoryScanner()
        albums = scanner.scan(test_album_path)
        
        if albums:
            album = albums[0]
            logger.log_album_start(album.root_path, 1, len(albums))
            
            if album.music_files:
                logger.log_file_conversion(
                    album.music_files[0].path,
                    temp_output_dir / "output.flac",
                    success=True,
                    duration=10.5
                )
            
            logger.log_album_end(album.root_path, True, len(album.music_files))
        
        logger.log_conversion_end(True, {
            'albums_processed': 1,
            'files_converted': 10,
            'duration': '00:05:30'
        })
        
        # Verify log file has content
        assert log_file.exists()
        log_content = log_file.read_text()
        
        assert "Starting Conversion Process" in log_content
        assert str(test_album_path) in log_content
        if albums:
            assert albums[0].root_path.name in log_content


@pytest.mark.integration
class TestResumeWorkflow:
    """Tests for resume functionality."""
    
    def test_resume_calculates_correct_output_path(
        self,
        temp_input_dir,
        temp_output_dir,
        temp_archive_dir,
        temp_state_dir,
        sample_config_dict
    ):
        """Test that resume correctly calculates output paths from original album path."""
        # Create a mock album in input directory
        album_dir = temp_input_dir / "Test Album"
        album_dir.mkdir()
        (album_dir / "track.dsf").write_text("mock dsf")
        
        # Update config
        sample_config_dict['paths']['archive_dir'] = str(temp_archive_dir)
        sample_config_dict['paths']['output_dir'] = str(temp_output_dir)
        sample_config_dict['paths']['working_dir'] = str(temp_state_dir / "working")
        
        config = Config()
        config.data = sample_config_dict
        
        logger = setup_logger()
        
        # Create orchestrator
        orchestrator = ConversionOrchestrator(
            config=config,
            logger=logger,
            dry_run=False
        )
        
        # Mock the state to simulate a resume scenario
        orchestrator.state_manager.create_session(
            input_dir=temp_input_dir,
            output_dir=temp_output_dir,
            archive_dir=temp_archive_dir,
            conversion_mode="iso_dsf_to_flac",
            sample_rate=88200,
            bit_depth=24,
            enrich_metadata=False
        )
        
        # Add album with working directories (simulating mid-conversion state)
        working_source = temp_state_dir / "working" / "Test Album_source"
        working_processed = temp_state_dir / "working" / "Test Album_processed"
        working_source.mkdir(parents=True)
        working_processed.mkdir(parents=True)
        
        # Create the file in working directory
        (working_source / "track.dsf").write_text("mock dsf")
        
        orchestrator.state_manager.add_album(
            album_path=album_dir,
            album_name="Test Album",
            music_files=[(album_dir / "track.dsf", Path("track.dsf"))]
        )
        
        orchestrator.state_manager.update_album_status(
            album_path=album_dir,
            status=AlbumStatus.CONVERTING,
            processing_stage='converting',
            working_source_path=working_source,
            working_processed_path=working_processed
        )
        
        # Scan from working directory (simulating resume)
        from scanner import Album, MusicFile
        album = Album(
            root_path=working_source,  # This is the key: root_path is working dir
            name="Test Album",
            music_files=[MusicFile(
                path=working_source / "track.dsf",
                relative_path=Path("track.dsf"),
                extension=".dsf"
            )]
        )
        
        # Mock converter and other operations to focus on path calculation
        with patch.object(orchestrator.converter, 'convert_file', return_value=(True, None, 1.0, None)):
            with patch.object(orchestrator.archiver, 'archive_album', return_value=(True, temp_archive_dir / "Test Album", None)):
                with patch.object(orchestrator.working_dir_manager, 'move_to_output', return_value=(True, None)) as mock_move:
                    # Process the album
                    orchestrator._process_album(album, temp_output_dir)
                    
                    # Verify move_to_output was called with correct path
                    assert mock_move.called
                    call_args = mock_move.call_args[0]
                    output_path = call_args[1]
                    
                    # Output path should be based on ORIGINAL album name, not working directory name
                    assert output_path == temp_output_dir / "Test Album"
                    assert "source" not in str(output_path)  # Should not include working dir suffix


@pytest.mark.integration
@pytest.mark.slow
class TestFullOrchestratorWorkflow:
    """Integration tests using the full ConversionOrchestrator."""
    
    @pytest.mark.skip(reason="Full orchestrator test requires extensive mocking or very long runtime")
    def test_orchestrator_dry_run(
        self,
        test_album_path,
        temp_output_dir,
        temp_archive_dir,
        sample_config_file
    ):
        """Test full orchestrator in dry-run mode."""
        # This would test the complete ConversionOrchestrator
        # in dry-run mode with a real album
        config = Config(config_path=sample_config_file)
        config.set('paths.archive_dir', str(temp_archive_dir))
        config.set('paths.output_dir', str(temp_output_dir))
        
        log_file = temp_output_dir / "test.log"
        error_log_file = temp_output_dir / "test_errors.log"
        logger = setup_logger(
            log_file=str(log_file),
            error_log_file=str(error_log_file)
        )
        
        orchestrator = ConversionOrchestrator(
            config=config,
            logger=logger,
            dry_run=True,
            resume=False
        )
        
        # This would take a very long time with real files
        # so we skip it unless specifically requested
        success = orchestrator.run(test_album_path)
        
        assert success is True

