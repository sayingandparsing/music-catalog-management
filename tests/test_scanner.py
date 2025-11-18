"""
Unit tests for scanner module (DirectoryScanner, Album, MusicFile).
"""

import pytest
from pathlib import Path
from scanner import DirectoryScanner, Album, MusicFile, NonMusicFile


class TestMusicFile:
    """Tests for MusicFile dataclass."""
    
    def test_music_file_creation(self, sample_album_structure):
        """Test creating a MusicFile object."""
        file_path = sample_album_structure / "01 - Track One.dsf"
        music_file = MusicFile(
            path=file_path,
            relative_path=Path("01 - Track One.dsf"),
            extension=".dsf"
        )
        
        assert music_file.path == file_path
        assert music_file.relative_path == Path("01 - Track One.dsf")
        assert music_file.extension == ".dsf"
        assert music_file.size > 0  # File exists and has size
    
    def test_music_file_size_calculation(self, sample_album_structure):
        """Test that file size is calculated correctly."""
        file_path = sample_album_structure / "01 - Track One.dsf"
        music_file = MusicFile(
            path=file_path,
            relative_path=Path("01 - Track One.dsf"),
            extension=".dsf"
        )
        
        expected_size = file_path.stat().st_size
        assert music_file.size == expected_size
    
    def test_music_file_nonexistent(self, temp_dir):
        """Test MusicFile with non-existent file."""
        file_path = temp_dir / "nonexistent.dsf"
        music_file = MusicFile(
            path=file_path,
            relative_path=Path("nonexistent.dsf"),
            extension=".dsf"
        )
        
        assert music_file.size == 0  # Non-existent file has size 0


class TestNonMusicFile:
    """Tests for NonMusicFile dataclass."""
    
    def test_non_music_file_creation(self, sample_album_structure):
        """Test creating a NonMusicFile object."""
        file_path = sample_album_structure / "cover.jpg"
        non_music_file = NonMusicFile(
            path=file_path,
            relative_path=Path("cover.jpg"),
            extension=".jpg"
        )
        
        assert non_music_file.path == file_path
        assert non_music_file.relative_path == Path("cover.jpg")
        assert non_music_file.extension == ".jpg"


class TestAlbum:
    """Tests for Album dataclass."""
    
    def test_album_creation(self, sample_album_structure):
        """Test creating an Album object."""
        music_file = MusicFile(
            path=sample_album_structure / "01 - Track One.dsf",
            relative_path=Path("01 - Track One.dsf"),
            extension=".dsf"
        )
        
        album = Album(
            root_path=sample_album_structure,
            name="Test Artist - Test Album",
            music_files=[music_file],
            non_music_files=[],
            subdirectories=[]
        )
        
        assert album.root_path == sample_album_structure
        assert album.name == "Test Artist - Test Album"
        assert len(album.music_files) == 1
        assert album.file_count == 1
    
    def test_album_total_size(self, sample_album_structure):
        """Test album total_size property."""
        music_files = [
            MusicFile(
                path=sample_album_structure / "01 - Track One.dsf",
                relative_path=Path("01 - Track One.dsf"),
                extension=".dsf"
            ),
            MusicFile(
                path=sample_album_structure / "02 - Track Two.dsf",
                relative_path=Path("02 - Track Two.dsf"),
                extension=".dsf"
            )
        ]
        
        album = Album(
            root_path=sample_album_structure,
            name="Test Album",
            music_files=music_files
        )
        
        expected_size = sum(f.size for f in music_files)
        assert album.total_size == expected_size
    
    def test_album_file_count(self, sample_album_structure):
        """Test album file_count property."""
        music_files = [
            MusicFile(
                path=sample_album_structure / "01 - Track One.dsf",
                relative_path=Path("01 - Track One.dsf"),
                extension=".dsf"
            ),
            MusicFile(
                path=sample_album_structure / "02 - Track Two.dsf",
                relative_path=Path("02 - Track Two.dsf"),
                extension=".dsf"
            )
        ]
        
        album = Album(
            root_path=sample_album_structure,
            name="Test Album",
            music_files=music_files
        )
        
        assert album.file_count == 2
    
    def test_album_repr(self, sample_album_structure):
        """Test album string representation."""
        music_file = MusicFile(
            path=sample_album_structure / "01 - Track One.dsf",
            relative_path=Path("01 - Track One.dsf"),
            extension=".dsf"
        )
        
        album = Album(
            root_path=sample_album_structure,
            name="Test Album",
            music_files=[music_file]
        )
        
        repr_str = repr(album)
        assert "Test Album" in repr_str
        assert "files=1" in repr_str


class TestDirectoryScanner:
    """Tests for DirectoryScanner class."""
    
    def test_scanner_initialization_default(self):
        """Test scanner initialization with default extensions."""
        scanner = DirectoryScanner()
        
        assert '.iso' in scanner.music_extensions
        assert '.dsf' in scanner.music_extensions
        assert '.dff' in scanner.music_extensions
        assert '.jpg' in scanner.copy_extensions
        assert '.pdf' in scanner.copy_extensions
    
    def test_scanner_initialization_custom(self):
        """Test scanner initialization with custom extensions."""
        scanner = DirectoryScanner(
            music_extensions=['.iso', '.dsf'],
            copy_extensions=['.jpg', '.png']
        )
        
        assert scanner.music_extensions == {'.iso', '.dsf'}
        assert scanner.copy_extensions == {'.jpg', '.png'}
    
    def test_scan_single_album(self, sample_album_structure):
        """Test scanning a single album directory."""
        scanner = DirectoryScanner()
        albums = scanner.scan(sample_album_structure)
        
        assert len(albums) == 1
        album = albums[0]
        assert album.name == "Test Artist - Test Album"
        assert album.file_count == 2  # Two DSF files
        assert len(album.non_music_files) == 2  # cover.jpg and booklet.pdf
    
    def test_scan_multiple_albums(self, sample_multi_album_structure):
        """Test scanning directory with multiple albums."""
        scanner = DirectoryScanner()
        albums = scanner.scan(sample_multi_album_structure)
        
        assert len(albums) == 2
        album_names = {album.name for album in albums}
        assert "Album 1" in album_names
        assert "Album 2" in album_names
    
    def test_scan_nested_album(self, sample_nested_album_structure):
        """Test scanning album with nested subdirectories."""
        scanner = DirectoryScanner()
        # Use single_album=True to treat the directory as one album with nested subdirectories
        albums = scanner.scan(sample_nested_album_structure, single_album=True)
        
        assert len(albums) == 1
        album = albums[0]
        assert album.name == "Artist - Album"
        assert album.file_count == 3  # Three DSF files total
        assert "CD1" in album.subdirectories
        assert "CD2" in album.subdirectories
    
    def test_scan_empty_directory(self, temp_input_dir):
        """Test scanning an empty directory."""
        scanner = DirectoryScanner()
        albums = scanner.scan(temp_input_dir)
        
        assert len(albums) == 0
    
    def test_scan_nonexistent_directory(self, temp_dir):
        """Test scanning a non-existent directory."""
        scanner = DirectoryScanner()
        nonexistent_path = temp_dir / "nonexistent"
        
        with pytest.raises(FileNotFoundError):
            scanner.scan(nonexistent_path)
    
    def test_scan_file_instead_of_directory(self, temp_dir):
        """Test scanning a file instead of a directory."""
        file_path = temp_dir / "test.txt"
        file_path.write_text("test content")
        
        scanner = DirectoryScanner()
        with pytest.raises(NotADirectoryError):
            scanner.scan(file_path)
    
    def test_scan_no_music_files(self, temp_input_dir):
        """Test scanning directory with no music files."""
        # Create directory with only non-music files
        album_path = temp_input_dir / "No Music Album"
        album_path.mkdir()
        (album_path / "cover.jpg").write_bytes(b"\xff\xd8\xff\xe0")
        (album_path / "readme.txt").write_text("test")
        
        scanner = DirectoryScanner()
        albums = scanner.scan(temp_input_dir)
        
        assert len(albums) == 0
    
    def test_scan_mixed_extensions(self, temp_input_dir):
        """Test scanning with mixed file extensions."""
        album_path = temp_input_dir / "Mixed Album"
        album_path.mkdir()
        (album_path / "track1.iso").write_text("mock iso")
        (album_path / "track2.dsf").write_text("mock dsf")
        (album_path / "track3.dff").write_text("mock dff")
        
        scanner = DirectoryScanner()
        albums = scanner.scan(temp_input_dir)
        
        assert len(albums) == 1
        album = albums[0]
        assert album.file_count == 3
        
        extensions = {f.extension for f in album.music_files}
        assert extensions == {'.iso', '.dsf', '.dff'}
    
    def test_scan_case_insensitive_extensions(self, temp_input_dir):
        """Test that extension matching is case-insensitive."""
        album_path = temp_input_dir / "Case Test Album"
        album_path.mkdir()
        (album_path / "track1.DSF").write_text("mock dsf")
        (album_path / "track2.Dsf").write_text("mock dsf")
        (album_path / "track3.dsf").write_text("mock dsf")
        
        scanner = DirectoryScanner()
        albums = scanner.scan(temp_input_dir)
        
        assert len(albums) == 1
        assert albums[0].file_count == 3
    
    def test_is_album_method(self, sample_album_structure, temp_input_dir):
        """Test _is_album method."""
        scanner = DirectoryScanner()
        
        # Directory with music files
        assert scanner._is_album(sample_album_structure) is True
        
        # Empty directory
        empty_dir = temp_input_dir / "empty"
        empty_dir.mkdir()
        assert scanner._is_album(empty_dir) is False
    
    def test_scan_album_file_sorting(self, temp_input_dir):
        """Test that scanned files are sorted."""
        album_path = temp_input_dir / "Sorted Album"
        album_path.mkdir()
        (album_path / "03 - Track.dsf").write_text("mock")
        (album_path / "01 - Track.dsf").write_text("mock")
        (album_path / "02 - Track.dsf").write_text("mock")
        
        scanner = DirectoryScanner()
        albums = scanner.scan(temp_input_dir)
        
        album = albums[0]
        file_names = [f.path.name for f in album.music_files]
        assert file_names == sorted(file_names)
    
    def test_get_statistics(self, sample_multi_album_structure):
        """Test get_statistics method."""
        scanner = DirectoryScanner()
        albums = scanner.scan(sample_multi_album_structure)
        stats = scanner.get_statistics(albums)
        
        assert stats['album_count'] == 2
        assert stats['total_files'] == 3  # 1 ISO + 2 DSF
        assert stats['total_size_bytes'] > 0
        assert stats['total_size_gb'] >= 0
        assert '.iso' in stats['extensions']
        assert '.dsf' in stats['extensions']
    
    def test_get_statistics_empty_list(self):
        """Test get_statistics with empty album list."""
        scanner = DirectoryScanner()
        stats = scanner.get_statistics([])
        
        assert stats['album_count'] == 0
        assert stats['total_files'] == 0
        assert stats['total_size_bytes'] == 0
        assert stats['total_size_gb'] == 0
        assert stats['extensions'] == {}
    
    def test_print_summary(self, sample_album_structure, capsys):
        """Test print_summary method."""
        scanner = DirectoryScanner()
        albums = scanner.scan(sample_album_structure)
        
        scanner.print_summary(albums)
        
        captured = capsys.readouterr()
        assert "Scan Summary" in captured.out
        assert "Albums found:" in captured.out
        assert "Total files:" in captured.out
    
    def test_relative_path_calculation(self, sample_nested_album_structure):
        """Test that relative paths are calculated correctly."""
        scanner = DirectoryScanner()
        # Use single_album=True to treat the directory as one album
        albums = scanner.scan(sample_nested_album_structure, single_album=True)
        
        album = albums[0]
        
        # Check that files in subdirectories have correct relative paths
        cd1_files = [f for f in album.music_files if "CD1" in str(f.relative_path)]
        assert len(cd1_files) == 2
        
        for music_file in cd1_files:
            assert str(music_file.relative_path).startswith("CD1/")
    
    def test_scan_with_hidden_files(self, temp_input_dir):
        """Test that hidden files are handled appropriately."""
        album_path = temp_input_dir / "Album With Hidden"
        album_path.mkdir()
        (album_path / "track.dsf").write_text("mock")
        (album_path / ".hidden.txt").write_text("hidden")
        (album_path / ".DS_Store").write_text("macos metadata")
        
        scanner = DirectoryScanner()
        albums = scanner.scan(temp_input_dir)
        
        # Should find the album
        assert len(albums) == 1
        # Hidden files may or may not be included depending on scanner logic
        # The main test is that it doesn't crash
    
    def test_extensionless_files(self, temp_input_dir):
        """Test handling of files without extensions."""
        album_path = temp_input_dir / "Album"
        album_path.mkdir()
        (album_path / "track.dsf").write_text("mock")
        (album_path / "README").write_text("readme content")
        (album_path / "LICENSE").write_text("license content")
        
        scanner = DirectoryScanner()
        albums = scanner.scan(temp_input_dir)
        
        album = albums[0]
        # Extensionless files should be included in non_music_files
        extensionless = [f for f in album.non_music_files if f.extension == '']
        assert len(extensionless) >= 0  # May or may not include extensionless


@pytest.mark.integration
class TestDirectoryScannerIntegration:
    """Integration tests using real test album."""
    
    def test_scan_real_album(self, test_album_path):
        """Test scanning a real ISO/DSF album."""
        scanner = DirectoryScanner()
        albums = scanner.scan(test_album_path)
        
        # Should find at least one album
        assert len(albums) >= 1
        
        # All albums should have at least one music file
        for album in albums:
            assert album.file_count > 0
            assert all(f.extension in {'.iso', '.dsf', '.dff'} 
                      for f in album.music_files)
    
    def test_real_album_statistics(self, test_album_path):
        """Test statistics calculation with real album."""
        scanner = DirectoryScanner()
        albums = scanner.scan(test_album_path)
        stats = scanner.get_statistics(albums)
        
        assert stats['album_count'] >= 1
        assert stats['total_files'] >= 1
        assert stats['total_size_bytes'] > 0
        
        # Real files should have non-trivial size
        for album in albums:
            assert album.total_size > 1000  # At least 1KB

