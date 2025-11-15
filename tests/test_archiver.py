"""
Unit tests for archiver module (Archiver class).
"""

import pytest
import time
from pathlib import Path
from unittest.mock import patch, Mock
from archiver import Archiver


class TestArchiverInitialization:
    """Tests for Archiver initialization."""
    
    def test_archiver_init(self, temp_archive_dir):
        """Test basic archiver initialization."""
        archiver = Archiver(temp_archive_dir)
        
        assert archiver.archive_root == temp_archive_dir
        assert archiver.verify_copies is True
        assert temp_archive_dir.exists()
    
    def test_archiver_init_creates_directory(self, temp_dir):
        """Test that archiver creates archive directory if it doesn't exist."""
        archive_path = temp_dir / "new_archive"
        assert not archive_path.exists()
        
        archiver = Archiver(archive_path)
        
        assert archive_path.exists()
        assert archive_path.is_dir()
    
    def test_archiver_init_without_verification(self, temp_archive_dir):
        """Test archiver initialization with verification disabled."""
        archiver = Archiver(temp_archive_dir, verify_copies=False)
        
        assert archiver.verify_copies is False


class TestArchiveAlbum:
    """Tests for archive_album method."""
    
    def test_archive_simple_album(self, sample_album_structure, temp_archive_dir):
        """Test archiving a simple album."""
        archiver = Archiver(temp_archive_dir)
        
        success, archive_path, error = archiver.archive_album(sample_album_structure)
        
        assert success is True
        assert archive_path is not None
        assert error is None
        assert archive_path.exists()
        assert archive_path.is_dir()
    
    def test_archive_path_naming(self, sample_album_structure, temp_archive_dir):
        """Test that archive path includes album name and timestamp."""
        archiver = Archiver(temp_archive_dir)
        
        success, archive_path, error = archiver.archive_album(sample_album_structure)
        
        assert success is True
        # Archive name should contain original album name
        assert "Test Artist - Test Album" in archive_path.name
        # Archive name should contain timestamp (format: YYYYMMDD_HHMMSS)
        assert "_" in archive_path.name
    
    def test_archive_preserves_structure(self, sample_nested_album_structure, temp_archive_dir):
        """Test that archiving preserves directory structure."""
        archiver = Archiver(temp_archive_dir)
        
        success, archive_path, error = archiver.archive_album(sample_nested_album_structure)
        
        assert success is True
        
        # Check that subdirectories are preserved
        assert (archive_path / "CD1").exists()
        assert (archive_path / "CD2").exists()
        
        # Check that files are preserved
        assert (archive_path / "CD1" / "01 - Track.dsf").exists()
        assert (archive_path / "cover.jpg").exists()
    
    def test_archive_preserves_file_content(self, sample_album_structure, temp_archive_dir):
        """Test that archived files have same content as originals."""
        archiver = Archiver(temp_archive_dir)
        
        original_file = sample_album_structure / "01 - Track One.dsf"
        original_content = original_file.read_text()
        
        success, archive_path, error = archiver.archive_album(sample_album_structure)
        
        assert success is True
        archived_file = archive_path / "01 - Track One.dsf"
        archived_content = archived_file.read_text()
        
        assert archived_content == original_content
    
    def test_archive_existing_archive(self, sample_album_structure, temp_archive_dir):
        """Test that archiving same album twice returns existing archive."""
        archiver = Archiver(temp_archive_dir)
        
        # First archive
        success1, archive_path1, error1 = archiver.archive_album(sample_album_structure)
        assert success1 is True
        
        # Create a marker file to verify we get the same archive
        marker = archive_path1 / "marker.txt"
        marker.write_text("test")
        
        # Mock the archive path generation to return same path
        with patch.object(archiver, '_get_archive_path', return_value=archive_path1):
            success2, archive_path2, error2 = archiver.archive_album(sample_album_structure)
        
        assert success2 is True
        assert archive_path2 == archive_path1
        assert marker.exists()  # Verify it's the same archive
    
    def test_archive_without_verification(self, sample_album_structure, temp_archive_dir):
        """Test archiving without verification."""
        archiver = Archiver(temp_archive_dir, verify_copies=False)
        
        success, archive_path, error = archiver.archive_album(sample_album_structure)
        
        assert success is True
        assert archive_path is not None
        assert error is None
    
    def test_archive_nonexistent_album(self, temp_archive_dir, temp_dir):
        """Test archiving a non-existent album."""
        archiver = Archiver(temp_archive_dir)
        nonexistent = temp_dir / "nonexistent"
        
        success, archive_path, error = archiver.archive_album(nonexistent)
        
        assert success is False
        assert archive_path is None
        assert error is not None
    
    def test_archive_preserve_timestamps(self, sample_album_structure, temp_archive_dir):
        """Test that timestamps are preserved when requested."""
        archiver = Archiver(temp_archive_dir)
        
        original_file = sample_album_structure / "01 - Track One.dsf"
        original_mtime = original_file.stat().st_mtime
        
        success, archive_path, error = archiver.archive_album(
            sample_album_structure,
            preserve_timestamps=True
        )
        
        assert success is True
        archived_file = archive_path / "01 - Track One.dsf"
        archived_mtime = archived_file.stat().st_mtime
        
        # Timestamps should be very close (allow small floating point differences)
        assert abs(archived_mtime - original_mtime) < 1.0


class TestVerification:
    """Tests for copy verification methods."""
    
    def test_verify_copy_success(self, sample_album_structure, temp_archive_dir):
        """Test successful copy verification."""
        archiver = Archiver(temp_archive_dir, verify_copies=True)
        
        success, archive_path, error = archiver.archive_album(sample_album_structure)
        
        # If verification passes, archiving should succeed
        assert success is True
        assert error is None
    
    def test_verify_copy_file_count_mismatch(self, sample_album_structure, temp_archive_dir):
        """Test verification fails when file counts don't match."""
        archiver = Archiver(temp_archive_dir, verify_copies=True)
        
        # Mock _verify_copy to return failure
        with patch.object(archiver, '_verify_copy', return_value=(False, "File count mismatch")):
            success, archive_path, error = archiver.archive_album(sample_album_structure)
        
        assert success is False
        assert archive_path is None
        assert "File count mismatch" in error
    
    def test_get_all_files(self, sample_nested_album_structure, temp_archive_dir):
        """Test _get_all_files method."""
        archiver = Archiver(temp_archive_dir)
        
        files = archiver._get_all_files(sample_nested_album_structure)
        
        # Should find all files including those in subdirectories
        assert len(files) >= 4  # 3 DSF files + 1 JPG
        
        # Files should be sorted
        assert files == sorted(files)
    
    def test_calculate_checksum(self, sample_album_structure, temp_archive_dir):
        """Test checksum calculation."""
        archiver = Archiver(temp_archive_dir)
        
        file_path = sample_album_structure / "01 - Track One.dsf"
        checksum1 = archiver._calculate_checksum(file_path)
        checksum2 = archiver._calculate_checksum(file_path)
        
        # Same file should have same checksum
        assert checksum1 == checksum2
        assert len(checksum1) == 32  # MD5 produces 32 hex chars
    
    def test_calculate_checksum_different_files(self, sample_album_structure, temp_archive_dir):
        """Test that different files have different checksums."""
        archiver = Archiver(temp_archive_dir)
        
        file1 = sample_album_structure / "01 - Track One.dsf"
        file2 = sample_album_structure / "02 - Track Two.dsf"
        
        checksum1 = archiver._calculate_checksum(file1)
        checksum2 = archiver._calculate_checksum(file2)
        
        # Different files should have different checksums
        assert checksum1 != checksum2


class TestArchiveManagement:
    """Tests for archive management methods."""
    
    def test_list_archives_empty(self, temp_archive_dir):
        """Test listing archives when none exist."""
        archiver = Archiver(temp_archive_dir)
        
        archives = archiver.list_archives()
        
        assert archives == []
    
    def test_list_archives_multiple(self, sample_album_structure, temp_archive_dir):
        """Test listing multiple archives."""
        archiver = Archiver(temp_archive_dir)
        
        # Create multiple archives
        success1, archive_path1, _ = archiver.archive_album(sample_album_structure)
        
        # Wait a moment to ensure different timestamp
        time.sleep(0.1)
        
        success2, archive_path2, _ = archiver.archive_album(sample_album_structure)
        
        archives = archiver.list_archives()
        
        # Should have at least 2 archives
        assert len(archives) >= 2
        # Archives should be sorted
        assert archives == sorted(archives)
    
    def test_get_archive_size_empty(self, temp_archive_dir):
        """Test getting archive size when no archives exist."""
        archiver = Archiver(temp_archive_dir)
        
        size = archiver.get_archive_size()
        
        assert size == 0
    
    def test_get_archive_size_with_archives(self, sample_album_structure, temp_archive_dir):
        """Test getting total archive size."""
        archiver = Archiver(temp_archive_dir)
        
        success, archive_path, error = archiver.archive_album(sample_album_structure)
        assert success is True
        
        size = archiver.get_archive_size()
        
        # Size should be greater than 0
        assert size > 0
    
    def test_delete_archive_success(self, sample_album_structure, temp_archive_dir):
        """Test successful archive deletion."""
        archiver = Archiver(temp_archive_dir)
        
        # Create archive
        success, archive_path, error = archiver.archive_album(sample_album_structure)
        assert success is True
        assert archive_path.exists()
        
        # Delete archive
        success, error = archiver.delete_archive(archive_path)
        
        assert success is True
        assert error is None
        assert not archive_path.exists()
    
    def test_delete_nonexistent_archive(self, temp_archive_dir):
        """Test deleting non-existent archive."""
        archiver = Archiver(temp_archive_dir)
        nonexistent = temp_archive_dir / "nonexistent_archive"
        
        success, error = archiver.delete_archive(nonexistent)
        
        assert success is False
        assert error is not None
        assert "does not exist" in error.lower()
    
    def test_delete_archive_outside_root(self, temp_archive_dir, temp_dir):
        """Test that deleting archive outside archive root fails."""
        archiver = Archiver(temp_archive_dir)
        
        # Try to delete a directory outside archive root
        outside_dir = temp_dir / "outside"
        outside_dir.mkdir()
        
        success, error = archiver.delete_archive(outside_dir)
        
        assert success is False
        assert error is not None
        assert "not within archive root" in error.lower()


class TestArchivePath:
    """Tests for archive path generation."""
    
    def test_get_archive_path(self, sample_album_structure, temp_archive_dir):
        """Test archive path generation."""
        archiver = Archiver(temp_archive_dir)
        
        archive_path = archiver._get_archive_path(sample_album_structure)
        
        # Should be within archive root
        assert archive_path.parent == temp_archive_dir
        
        # Should contain album name
        assert "Test Artist - Test Album" in archive_path.name
        
        # Should contain timestamp
        assert "_" in archive_path.name
    
    def test_archive_path_unique_timestamps(self, sample_album_structure, temp_archive_dir):
        """Test that multiple archive paths have different timestamps."""
        archiver = Archiver(temp_archive_dir)
        
        path1 = archiver._get_archive_path(sample_album_structure)
        time.sleep(1.1)  # Wait more than a second for timestamp to change
        path2 = archiver._get_archive_path(sample_album_structure)
        
        # Paths should be different due to timestamps
        assert path1 != path2


class TestErrorHandling:
    """Tests for error handling."""
    
    def test_archive_permission_error(self, sample_album_structure, temp_archive_dir, monkeypatch):
        """Test handling of permission errors."""
        archiver = Archiver(temp_archive_dir)
        
        # Mock copytree to raise PermissionError
        def mock_copytree(*args, **kwargs):
            raise PermissionError("Permission denied")
        
        monkeypatch.setattr("shutil.copytree", mock_copytree)
        
        success, archive_path, error = archiver.archive_album(sample_album_structure)
        
        assert success is False
        assert archive_path is None
        assert "Permission denied" in error
    
    def test_archive_os_error(self, sample_album_structure, temp_archive_dir, monkeypatch):
        """Test handling of OS errors."""
        archiver = Archiver(temp_archive_dir)
        
        # Mock copytree to raise OSError
        def mock_copytree(*args, **kwargs):
            raise OSError("Disk full")
        
        monkeypatch.setattr("shutil.copytree", mock_copytree)
        
        success, archive_path, error = archiver.archive_album(sample_album_structure)
        
        assert success is False
        assert "OS error" in error
    
    def test_verification_error_cleanup(self, sample_album_structure, temp_archive_dir):
        """Test that failed verification cleans up partial archive."""
        archiver = Archiver(temp_archive_dir, verify_copies=True)
        
        # Mock verification to fail
        original_verify = archiver._verify_copy
        def mock_verify(*args):
            return False, "Verification failed"
        
        with patch.object(archiver, '_verify_copy', side_effect=mock_verify):
            success, archive_path, error = archiver.archive_album(sample_album_structure)
        
        assert success is False
        # Archive should be cleaned up (not exist)
        if archive_path:
            assert not archive_path.exists()


@pytest.mark.integration
class TestArchiverIntegration:
    """Integration tests using real test album."""
    
    def test_archive_real_album(self, test_album_path, temp_archive_dir):
        """Test archiving a real ISO/DSF album."""
        archiver = Archiver(temp_archive_dir, verify_copies=True)
        
        # Find first album directory
        album_dirs = [d for d in test_album_path.iterdir() if d.is_dir()]
        if not album_dirs:
            pytest.skip("No album directories found in TEST_ALBUM_PATH")
        
        album_dir = album_dirs[0]
        
        success, archive_path, error = archiver.archive_album(album_dir)
        
        assert success is True, f"Archiving failed: {error}"
        assert archive_path is not None
        assert archive_path.exists()
        
        # Verify archive has content
        archived_files = list(archive_path.rglob("*"))
        assert len(archived_files) > 0

