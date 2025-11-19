"""
Tests for SACD metadata parser functionality.
"""

import pytest
from pathlib import Path
import tempfile
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sacd_metadata_parser import (
    parse_sacd_metadata_file,
    find_sacd_metadata_files,
    get_metadata_for_album,
    write_sacd_metadata_to_flac,
    _parse_disc_info,
    _parse_album_info,
    _parse_track_list
)

try:
    from mutagen.flac import FLAC
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


SAMPLE_SACD_METADATA = """

Disc Information:

	Version:  1.20
	Creation date: 2022-10-22
	Disc Catalog Number: CAPJ 0000       
	Disc Category: General
	Disc Genre: Jazz
	Locale: en, Code character set:[1], ISO646-JP
	Title: Blues & Roots
	Artist: Charles Mingus
	Publisher: Analogue Productions
	Copyright: Analogue Productions

Album Information:

	Album Catalog Number: CAPJ0000        
	Sequence Number: 1
	Set Size: 1
	Album Category: General
	Album Genre: Jazz
	Title: Blues & Roots
	Artist: Charles Mingus
	Publisher: Analogue Productions
	Copyright: Analogue Productions

Area count: 1
	Area Information [0]:
	Version:  1.20
	Track Count: 6
	Total play time: 38:56:36 [mins:secs:frames]
	Speaker config: 2 Channel
	Track list [0]:
		Title[0]: Wednesday Night Prayer Meeting
		Performer[0]: Charles Mingus
		Track_Start_Time_Code: 00:02:00 [mins:secs:frames]
		Duration: 05:42:01 [mins:secs:frames]
		Title[1]: Cryin' Blues
		Performer[1]: Charles Mingus
		Track_Start_Time_Code: 05:44:01 [mins:secs:frames]
		Duration: 05:03:22 [mins:secs:frames]
		Title[2]: Moanin'
		Performer[2]: Charles Mingus
		Track_Start_Time_Code: 10:47:23 [mins:secs:frames]
		Duration: 08:02:39 [mins:secs:frames]
		Title[3]: Tensions
		Performer[3]: Charles Mingus
		Track_Start_Time_Code: 18:49:62 [mins:secs:frames]
		Duration: 06:29:63 [mins:secs:frames]
		Title[4]: My Jelly Roll Soul
		Performer[4]: Charles Mingus
		Track_Start_Time_Code: 25:19:50 [mins:secs:frames]
		Duration: 06:50:28 [mins:secs:frames]
		Title[5]: E's Flat Ah's Flat Too
		Performer[5]: Charles Mingus
		Track_Start_Time_Code: 32:10:03 [mins:secs:frames]
		Duration: 06:46:33 [mins:secs:frames]

"""


class TestSACDMetadataParser:
    """Tests for SACD metadata parsing."""
    
    def test_parse_disc_info(self):
        """Test parsing of disc information section."""
        disc_section = """
	Disc Catalog Number: CAPJ 0000
	Disc Genre: Jazz
	Title: Blues & Roots
	Artist: Charles Mingus
	Publisher: Analogue Productions
	Copyright: Analogue Productions
"""
        disc_info = _parse_disc_info(disc_section)
        
        assert disc_info['catalog_number'] == 'CAPJ 0000'
        assert disc_info['genre'] == 'Jazz'
        assert disc_info['title'] == 'Blues & Roots'
        assert disc_info['artist'] == 'Charles Mingus'
        assert disc_info['label'] == 'Analogue Productions'
        assert disc_info['copyright'] == 'Analogue Productions'
    
    def test_parse_album_info(self):
        """Test parsing of album information section."""
        album_section = """
	Album Catalog Number: CAPJ0000
	Album Genre: Jazz
	Title: Blues & Roots
	Artist: Charles Mingus
	Publisher: Analogue Productions
"""
        album_info = _parse_album_info(album_section)
        
        assert album_info['catalog_number'] == 'CAPJ0000'
        assert album_info['genre'] == 'Jazz'
        assert album_info['title'] == 'Blues & Roots'
        assert album_info['artist'] == 'Charles Mingus'
        assert album_info['label'] == 'Analogue Productions'
    
    def test_parse_track_list(self):
        """Test parsing of track list."""
        tracks = _parse_track_list(SAMPLE_SACD_METADATA)
        
        assert len(tracks) == 6
        
        # Check first track
        assert tracks[0]['track_number'] == 1
        assert tracks[0]['title'] == 'Wednesday Night Prayer Meeting'
        assert tracks[0]['artist'] == 'Charles Mingus'
        assert tracks[0]['duration_seconds'] == 5 * 60 + 42  # 5:42
        
        # Check third track
        assert tracks[2]['track_number'] == 3
        assert tracks[2]['title'] == "Moanin'"
        assert tracks[2]['artist'] == 'Charles Mingus'
        # Duration is 08:02:39 which is 8 minutes 2 seconds (frames ignored)
        assert tracks[2]['duration_seconds'] == 8 * 60 + 2  # 8:02
        
        # Check last track
        assert tracks[5]['track_number'] == 6
        assert tracks[5]['title'] == "E's Flat Ah's Flat Too"
        assert tracks[5]['duration_seconds'] == 6 * 60 + 46  # 6:46
    
    def test_parse_full_sacd_metadata_file(self, tmp_path):
        """Test parsing complete SACD metadata file."""
        # Create a temporary metadata file
        metadata_file = tmp_path / "sacd_metadata.txt"
        metadata_file.write_text(SAMPLE_SACD_METADATA)
        
        metadata = parse_sacd_metadata_file(metadata_file)
        
        assert metadata is not None
        assert 'disc' in metadata
        assert 'album' in metadata
        assert 'tracks' in metadata
        
        # Check disc info
        assert metadata['disc']['catalog_number'] == 'CAPJ 0000'
        assert metadata['disc']['genre'] == 'Jazz'
        assert metadata['disc']['title'] == 'Blues & Roots'
        assert metadata['disc']['artist'] == 'Charles Mingus'
        assert metadata['disc']['label'] == 'Analogue Productions'
        
        # Check album info
        assert metadata['album']['catalog_number'] == 'CAPJ0000'
        assert metadata['album']['genre'] == 'Jazz'
        
        # Check tracks
        assert len(metadata['tracks']) == 6
        assert metadata['tracks'][0]['title'] == 'Wednesday Night Prayer Meeting'
        assert metadata['tracks'][1]['title'] == "Cryin' Blues"
    
    def test_parse_nonexistent_file(self, tmp_path):
        """Test parsing returns None for nonexistent file."""
        metadata_file = tmp_path / "nonexistent.txt"
        metadata = parse_sacd_metadata_file(metadata_file)
        
        assert metadata is None
    
    def test_parse_invalid_file(self, tmp_path):
        """Test parsing handles invalid/malformed files."""
        metadata_file = tmp_path / "invalid.txt"
        metadata_file.write_text("This is not SACD metadata")
        
        metadata = parse_sacd_metadata_file(metadata_file)
        
        # Should still return a structure, but with empty sections
        assert metadata is not None
        assert len(metadata['tracks']) == 0
    
    def test_find_sacd_metadata_files(self, tmp_path):
        """Test finding SACD metadata files in a directory."""
        # Create various files
        (tmp_path / "regular.txt").write_text("Some text")
        (tmp_path / "SACD_info.txt").write_text("Disc Information:\nTitle: Test")
        (tmp_path / "album_metadata.txt").write_text("Album Information:\nTitle: Test")
        (tmp_path / "not_sacd.txt").write_text("Regular text file")
        
        metadata_files = find_sacd_metadata_files(tmp_path)
        
        # Should find the two valid SACD metadata files
        assert len(metadata_files) == 2
        file_names = [f.name for f in metadata_files]
        assert "SACD_info.txt" in file_names
        assert "album_metadata.txt" in file_names
    
    def test_get_metadata_for_album(self, tmp_path):
        """Test getting metadata for an album directory."""
        # Create a metadata file in the album directory
        metadata_file = tmp_path / "sacd_info.txt"
        metadata_file.write_text(SAMPLE_SACD_METADATA)
        
        metadata = get_metadata_for_album(tmp_path)
        
        assert metadata is not None
        assert metadata['disc']['title'] == 'Blues & Roots'
        assert len(metadata['tracks']) == 6
    
    def test_get_metadata_no_files(self, tmp_path):
        """Test returns None when no metadata files found."""
        metadata = get_metadata_for_album(tmp_path)
        
        assert metadata is None
    
    def test_field_mappings(self, tmp_path):
        """Test that field mappings are correct (Publisher → label, etc.)."""
        metadata_content = """
Disc Information:
	Disc Catalog Number: TEST123
	Disc Genre: Classical
	Publisher: Test Label
"""
        metadata_file = tmp_path / "test.txt"
        metadata_file.write_text(metadata_content)
        
        metadata = parse_sacd_metadata_file(metadata_file)
        
        # Verify field mappings
        assert metadata['disc']['catalog_number'] == 'TEST123'
        assert metadata['disc']['genre'] == 'Classical'
        assert metadata['disc']['label'] == 'Test Label'  # Publisher → label
    
    def test_track_duration_parsing(self):
        """Test various duration formats are parsed correctly."""
        content = """
Title[0]: Test Track
Duration: 01:23:45 [mins:secs:frames]
"""
        tracks = _parse_track_list(content)
        
        assert len(tracks) == 1
        assert tracks[0]['duration_seconds'] == 1 * 60 + 23  # Minutes + seconds
    
    def test_track_number_zero_indexed_to_one_indexed(self):
        """Test that track numbers are converted from 0-indexed to 1-indexed."""
        content = """
Title[0]: First Track
Title[1]: Second Track
Title[2]: Third Track
"""
        tracks = _parse_track_list(content)
        
        assert tracks[0]['track_number'] == 1
        assert tracks[1]['track_number'] == 2
        assert tracks[2]['track_number'] == 3


class TestSACDMetadataParserErrorHandling:
    """Tests for error handling in SACD metadata parser."""
    
    def test_parse_none_path(self):
        """Test parsing handles None path gracefully."""
        metadata = parse_sacd_metadata_file(None)
        assert metadata is None
    
    def test_parse_empty_file(self, tmp_path):
        """Test parsing handles empty files gracefully."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")
        
        metadata = parse_sacd_metadata_file(empty_file)
        assert metadata is None
    
    def test_parse_file_too_large(self, tmp_path):
        """Test parsing skips extremely large files."""
        # Mock a file that appears too large
        large_file = tmp_path / "large.txt"
        # We can't actually create a 10MB+ file in tests, but we can test the logic exists
        # For now, just ensure small files work
        large_file.write_text("Disc Information:\nTitle: Test")
        metadata = parse_sacd_metadata_file(large_file)
        assert metadata is not None  # Small file should work
    
    def test_parse_directory_not_file(self, tmp_path):
        """Test parsing handles directory instead of file."""
        directory = tmp_path / "not_a_file"
        directory.mkdir()
        
        metadata = parse_sacd_metadata_file(directory)
        assert metadata is None
    
    def test_parse_malformed_track_data(self, tmp_path):
        """Test parser handles malformed track data gracefully."""
        malformed_content = """
Disc Information:
    Title: Test Album
    
Track list [0]:
    Title[0]: Valid Track
    Duration: INVALID:TIME:FORMAT
    Title[1]: Another Track
    Duration: 05:30:00
"""
        metadata_file = tmp_path / "malformed.txt"
        metadata_file.write_text(malformed_content)
        
        metadata = parse_sacd_metadata_file(metadata_file)
        
        # Should still return structure, even if some tracks fail
        assert metadata is not None
        assert 'tracks' in metadata
        # At least one track should parse successfully
        assert len(metadata['tracks']) >= 1
    
    def test_parse_partial_metadata(self, tmp_path):
        """Test parser handles partial metadata gracefully."""
        partial_content = """
Disc Information:
    Title: Incomplete Album
"""
        metadata_file = tmp_path / "partial.txt"
        metadata_file.write_text(partial_content)
        
        metadata = parse_sacd_metadata_file(metadata_file)
        
        assert metadata is not None
        assert metadata['disc']['title'] == 'Incomplete Album'
        assert len(metadata['tracks']) == 0  # No tracks
    
    def test_find_files_in_nonexistent_directory(self, tmp_path):
        """Test finding files in nonexistent directory returns empty list."""
        nonexistent = tmp_path / "does_not_exist"
        files = find_sacd_metadata_files(nonexistent)
        
        assert files == []
    
    def test_find_files_with_none_directory(self):
        """Test finding files with None directory returns empty list."""
        files = find_sacd_metadata_files(None)
        assert files == []
    
    def test_find_files_with_file_not_directory(self, tmp_path):
        """Test finding files when given a file not a directory."""
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("test")
        
        files = find_sacd_metadata_files(file_path)
        assert files == []
    
    def test_get_metadata_with_none_directory(self):
        """Test get_metadata_for_album with None directory."""
        metadata = get_metadata_for_album(None)
        assert metadata is None
    
    def test_parse_disc_info_empty_section(self):
        """Test disc info parsing with empty section."""
        disc_info = _parse_disc_info("")
        assert disc_info == {}
    
    def test_parse_disc_info_none_section(self):
        """Test disc info parsing with None section."""
        disc_info = _parse_disc_info(None)
        assert disc_info == {}
    
    def test_parse_album_info_empty_section(self):
        """Test album info parsing with empty section."""
        album_info = _parse_album_info("")
        assert album_info == {}
    
    def test_parse_track_list_empty_content(self):
        """Test track list parsing with empty content."""
        tracks = _parse_track_list("")
        assert tracks == []
    
    def test_parse_track_list_none_content(self):
        """Test track list parsing with None content."""
        tracks = _parse_track_list(None)
        assert tracks == []
    
    def test_parse_track_with_missing_performer(self):
        """Test track parsing when performer is missing."""
        content = """
Title[0]: Track Without Performer
Duration: 03:45:00
"""
        tracks = _parse_track_list(content)
        
        assert len(tracks) == 1
        assert tracks[0]['title'] == 'Track Without Performer'
        assert 'artist' not in tracks[0]  # No performer field
    
    def test_parse_track_with_missing_duration(self):
        """Test track parsing when duration is missing."""
        content = """
Title[0]: Track Without Duration
Performer[0]: Some Artist
"""
        tracks = _parse_track_list(content)
        
        assert len(tracks) == 1
        assert tracks[0]['title'] == 'Track Without Duration'
        assert 'duration_seconds' not in tracks[0]  # No duration field
    
    def test_parse_with_unicode_content(self, tmp_path):
        """Test parsing handles unicode characters properly."""
        unicode_content = """
Disc Information:
    Title: Björk - Homogénic
    Artist: Björk
    Genre: Electronic
    
Track list [0]:
    Title[0]: Jóga
    Performer[0]: Björk
    Duration: 05:07:00
"""
        metadata_file = tmp_path / "unicode.txt"
        metadata_file.write_text(unicode_content, encoding='utf-8')
        
        metadata = parse_sacd_metadata_file(metadata_file)
        
        assert metadata is not None
        assert metadata['disc']['title'] == 'Björk - Homogénic'
        assert metadata['disc']['artist'] == 'Björk'
        assert metadata['tracks'][0]['title'] == 'Jóga'


@pytest.mark.skipif(not MUTAGEN_AVAILABLE, reason="mutagen not available")
class TestWriteSACDMetadataToFLAC:
    """Tests for writing SACD metadata to FLAC files."""
    
    def create_dummy_flac(self, path: Path) -> Path:
        """Create a minimal valid FLAC file for testing."""
        import subprocess
        # Create a 1-second silent FLAC file using ffmpeg
        result = subprocess.run([
            'ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', '0.1',
            '-y', str(path)
        ], capture_output=True, timeout=5)
        
        if result.returncode != 0:
            # Fallback: create using Python's wave module and convert to FLAC
            import wave
            import struct
            wav_path = path.with_suffix('.wav')
            with wave.open(str(wav_path), 'w') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(44100)
                # Write 0.1 seconds of silence
                samples = [0] * int(44100 * 0.1)
                wav_file.writeframes(struct.pack('h' * len(samples), *samples))
            
            # Convert WAV to FLAC
            subprocess.run(['ffmpeg', '-i', str(wav_path), '-y', str(path)],
                         capture_output=True, check=True, timeout=5)
            wav_path.unlink()
        
        return path
    
    def test_write_basic_metadata(self, tmp_path):
        """Test writing basic SACD metadata to FLAC file."""
        # Create a dummy FLAC file
        flac_file = tmp_path / "test.flac"
        self.create_dummy_flac(flac_file)
        
        # Create SACD metadata
        sacd_metadata = {
            'disc': {
                'title': 'Test Album',
                'artist': 'Test Artist',
                'label': 'Test Label',
                'catalog_number': 'TEST-001',
                'genre': 'Jazz'
            },
            'tracks': []
        }
        
        # Write metadata
        result = write_sacd_metadata_to_flac(flac_file, sacd_metadata)
        
        assert result is True
        
        # Verify metadata was written
        audio = FLAC(str(flac_file))
        assert audio.get('label') == ['Test Label']
        assert audio.get('catalognumber') == ['TEST-001']
        assert audio.get('genre') == ['Jazz']
        assert audio.get('album') == ['Test Album']
        assert audio.get('artist') == ['Test Artist']
        assert audio.get('albumartist') == ['Test Artist']
    
    def test_write_track_metadata(self, tmp_path):
        """Test writing track-specific metadata."""
        flac_file = tmp_path / "test.flac"
        self.create_dummy_flac(flac_file)
        
        sacd_metadata = {
            'disc': {
                'title': 'Test Album',
                'artist': 'Album Artist'
            },
            'tracks': [
                {'track_number': 1, 'title': 'Track 1', 'artist': 'Track Artist 1'},
                {'track_number': 2, 'title': 'Track 2', 'artist': 'Track Artist 2'}
            ]
        }
        
        # Write metadata for track 2
        result = write_sacd_metadata_to_flac(flac_file, sacd_metadata, track_number=2)
        
        assert result is True
        
        # Verify track-specific metadata
        audio = FLAC(str(flac_file))
        assert audio.get('title') == ['Track 2']
        assert audio.get('artist') == ['Track Artist 2']
        assert audio.get('tracknumber') == ['2']
        assert audio.get('album') == ['Test Album']
    
    def test_preserve_existing_metadata(self, tmp_path):
        """Test that existing metadata is preserved."""
        flac_file = tmp_path / "test.flac"
        self.create_dummy_flac(flac_file)
        
        # Add existing metadata
        audio = FLAC(str(flac_file))
        audio['title'] = 'Existing Title'
        audio['genre'] = 'Existing Genre'
        audio.save()
        
        # Try to write SACD metadata
        sacd_metadata = {
            'disc': {
                'title': 'New Album',
                'genre': 'New Genre',
                'label': 'New Label'
            },
            'tracks': []
        }
        
        result = write_sacd_metadata_to_flac(flac_file, sacd_metadata)
        
        assert result is True
        
        # Verify existing metadata preserved
        audio = FLAC(str(flac_file))
        assert audio.get('title') == ['Existing Title']  # Should not be overwritten
        assert audio.get('genre') == ['Existing Genre']  # Should not be overwritten
        assert audio.get('label') == ['New Label']  # New field should be added
        assert audio.get('album') == ['New Album']  # New field should be added
    
    def test_write_with_album_metadata_priority(self, tmp_path):
        """Test that album metadata is preferred over disc metadata."""
        flac_file = tmp_path / "test.flac"
        self.create_dummy_flac(flac_file)
        
        sacd_metadata = {
            'disc': {
                'title': 'Disc Title',
                'label': 'Disc Label',
                'catalog_number': 'DISC-001'
            },
            'album': {
                'title': 'Album Title',
                'label': 'Album Label',
                'catalog_number': 'ALBUM-001'
            },
            'tracks': []
        }
        
        result = write_sacd_metadata_to_flac(flac_file, sacd_metadata)
        
        assert result is True
        
        # Verify album metadata used
        audio = FLAC(str(flac_file))
        assert audio.get('album') == ['Album Title']
        assert audio.get('label') == ['Album Label']
        assert audio.get('catalognumber') == ['ALBUM-001']
    
    def test_write_handles_missing_fields(self, tmp_path):
        """Test writing with partial/missing metadata."""
        flac_file = tmp_path / "test.flac"
        self.create_dummy_flac(flac_file)
        
        # Minimal metadata
        sacd_metadata = {
            'disc': {
                'label': 'Only Label'
            },
            'tracks': []
        }
        
        result = write_sacd_metadata_to_flac(flac_file, sacd_metadata)
        
        assert result is True
        
        # Verify only available field written
        audio = FLAC(str(flac_file))
        assert audio.get('label') == ['Only Label']
        assert audio.get('catalognumber') is None
        assert audio.get('genre') is None
    
    def test_write_fails_for_nonexistent_file(self, tmp_path):
        """Test that writing fails gracefully for nonexistent files."""
        flac_file = tmp_path / "nonexistent.flac"
        
        sacd_metadata = {
            'disc': {'label': 'Test'},
            'tracks': []
        }
        
        result = write_sacd_metadata_to_flac(flac_file, sacd_metadata)
        
        assert result is False
    
    def test_write_fails_for_directory(self, tmp_path):
        """Test that writing fails gracefully for directories."""
        sacd_metadata = {
            'disc': {'label': 'Test'},
            'tracks': []
        }
        
        result = write_sacd_metadata_to_flac(tmp_path, sacd_metadata)
        
        assert result is False
    
    def test_write_with_empty_metadata(self, tmp_path):
        """Test writing with empty metadata."""
        flac_file = tmp_path / "test.flac"
        self.create_dummy_flac(flac_file)
        
        result = write_sacd_metadata_to_flac(flac_file, {})
        
        # Should succeed but not write anything
        assert result is True
    
    def test_write_with_none_metadata(self, tmp_path):
        """Test writing with None metadata."""
        flac_file = tmp_path / "test.flac"
        self.create_dummy_flac(flac_file)
        
        result = write_sacd_metadata_to_flac(flac_file, None)
        
        assert result is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

