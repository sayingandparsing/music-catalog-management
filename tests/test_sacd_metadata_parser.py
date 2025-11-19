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
    _parse_disc_info,
    _parse_album_info,
    _parse_track_list
)


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


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

