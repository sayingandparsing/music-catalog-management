"""
Unit tests for metadata_enricher module (MetadataEnricher class).
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from metadata_enricher import MetadataEnricher


class TestMetadataEnricherInitialization:
    """Tests for MetadataEnricher initialization."""
    
    def test_enricher_init_default(self):
        """Test enricher initialization with default settings."""
        with patch('metadata_enricher.mb'):
            with patch('metadata_enricher.discogs_client'):
                with patch('metadata_enricher.FLAC'):
                    enricher = MetadataEnricher()
                    
                    assert enricher.sources == ['musicbrainz', 'discogs']
                    assert enricher.behavior == 'fill_missing'
                    assert enricher.discogs_token is None
    
    def test_enricher_init_custom_sources(self):
        """Test enricher with custom sources."""
        with patch('metadata_enricher.mb'):
            with patch('metadata_enricher.FLAC'):
                enricher = MetadataEnricher(sources=['musicbrainz'])
                
                assert enricher.sources == ['musicbrainz']
    
    def test_enricher_init_with_discogs_token(self):
        """Test enricher initialization with Discogs token."""
        with patch('metadata_enricher.mb'):
            with patch('metadata_enricher.discogs_client') as mock_discogs:
                with patch('metadata_enricher.FLAC'):
                    enricher = MetadataEnricher(
                        sources=['discogs'],
                        discogs_token='test_token'
                    )
                    
                    assert enricher.discogs_token == 'test_token'
                    assert enricher.discogs is not None
    
    def test_enricher_init_overwrite_behavior(self):
        """Test enricher with overwrite behavior."""
        with patch('metadata_enricher.mb'):
            with patch('metadata_enricher.FLAC'):
                enricher = MetadataEnricher(behavior='overwrite')
                
                assert enricher.behavior == 'overwrite'
    
    def test_enricher_missing_musicbrainz(self):
        """Test that missing musicbrainzngs raises ImportError."""
        with patch('metadata_enricher.mb', None):
            with patch('metadata_enricher.FLAC'):
                with pytest.raises(ImportError, match="musicbrainzngs"):
                    MetadataEnricher(sources=['musicbrainz'])
    
    def test_enricher_missing_discogs(self):
        """Test that missing discogs_client raises ImportError."""
        with patch('metadata_enricher.discogs_client', None):
            with patch('metadata_enricher.mb'):
                with patch('metadata_enricher.FLAC'):
                    with pytest.raises(ImportError, match="discogs_client"):
                        MetadataEnricher(sources=['discogs'], discogs_token='token')
    
    def test_enricher_missing_mutagen(self):
        """Test that missing mutagen raises ImportError."""
        with patch('metadata_enricher.FLAC', None):
            with patch('metadata_enricher.mb'):
                with pytest.raises(ImportError, match="mutagen"):
                    MetadataEnricher()


class TestExtractAlbumInfo:
    """Tests for _extract_album_info method."""
    
    def test_extract_from_artist_album_pattern(self, temp_dir, mock_musicbrainz):
        """Test extracting info from 'Artist - Album' pattern."""
        with patch('metadata_enricher.FLAC'):
            enricher = MetadataEnricher(sources=['musicbrainz'])
            
            album_path = temp_dir / "The Beatles - Abbey Road"
            album_path.mkdir()
            
            info = enricher._extract_album_info(album_path, [])
            
            assert info['artist'] == 'The Beatles'
            assert info['album'] == 'Abbey Road'
    
    def test_extract_from_artist_album_year_pattern(self, temp_dir, mock_musicbrainz):
        """Test extracting info from 'Artist - Album (Year)' pattern."""
        with patch('metadata_enricher.FLAC'):
            enricher = MetadataEnricher(sources=['musicbrainz'])
            
            album_path = temp_dir / "Miles Davis - Kind of Blue (1959)"
            album_path.mkdir()
            
            info = enricher._extract_album_info(album_path, [])
            
            assert info['artist'] == 'Miles Davis'
            assert info['album'] == 'Kind of Blue'
            assert info['year'] == '1959'
    
    def test_extract_album_only(self, temp_dir, mock_musicbrainz):
        """Test extracting when only album name is available."""
        with patch('metadata_enricher.FLAC'):
            enricher = MetadataEnricher(sources=['musicbrainz'])
            
            album_path = temp_dir / "Some Album Name"
            album_path.mkdir()
            
            info = enricher._extract_album_info(album_path, [])
            
            assert info['album'] == 'Some Album Name'
            assert info['artist'] is None


class TestExtractTrackNumber:
    """Tests for _extract_track_number method."""
    
    def test_extract_track_number_dash_pattern(self, temp_dir, mock_musicbrainz):
        """Test extracting track number from '01 - Title' pattern."""
        with patch('metadata_enricher.FLAC'):
            enricher = MetadataEnricher(sources=['musicbrainz'])
            
            file_path = temp_dir / "01 - Track Title.flac"
            
            track_num = enricher._extract_track_number(file_path)
            
            assert track_num == '1'
    
    def test_extract_track_number_dot_pattern(self, temp_dir, mock_musicbrainz):
        """Test extracting track number from '01. Title' pattern."""
        with patch('metadata_enricher.FLAC'):
            enricher = MetadataEnricher(sources=['musicbrainz'])
            
            file_path = temp_dir / "01. Track Title.flac"
            
            track_num = enricher._extract_track_number(file_path)
            
            assert track_num == '1'
    
    def test_extract_track_number_track_prefix(self, temp_dir, mock_musicbrainz):
        """Test extracting from 'Track 01' pattern."""
        with patch('metadata_enricher.FLAC'):
            enricher = MetadataEnricher(sources=['musicbrainz'])
            
            file_path = temp_dir / "Track 01.flac"
            
            track_num = enricher._extract_track_number(file_path)
            
            assert track_num == '1'
    
    def test_extract_track_number_no_match(self, temp_dir, mock_musicbrainz):
        """Test when no track number pattern matches."""
        with patch('metadata_enricher.FLAC'):
            enricher = MetadataEnricher(sources=['musicbrainz'])
            
            file_path = temp_dir / "Some Title.flac"
            
            track_num = enricher._extract_track_number(file_path)
            
            assert track_num is None
    
    def test_extract_track_number_leading_zeros(self, temp_dir, mock_musicbrainz):
        """Test that leading zeros are removed."""
        with patch('metadata_enricher.FLAC'):
            enricher = MetadataEnricher(sources=['musicbrainz'])
            
            file_path = temp_dir / "05 - Track.flac"
            
            track_num = enricher._extract_track_number(file_path)
            
            assert track_num == '5'


class TestSearchMusicBrainz:
    """Tests for _search_musicbrainz method."""
    
    def test_search_musicbrainz_success(self, mock_musicbrainz):
        """Test successful MusicBrainz search."""
        with patch('metadata_enricher.FLAC'):
            enricher = MetadataEnricher(sources=['musicbrainz'])
            
            with patch.object(enricher, '_rate_limit'):
                with patch('metadata_enricher.mb') as mock_mb:
                    # Mock search result
                    mock_mb.search_releases.return_value = {
                        'release-list': [{'id': 'test-id'}]
                    }
                    
                    # Mock detailed result with proper structure
                    mock_mb.get_release_by_id.return_value = {
                        'release': {
                            'artist-credit-phrase': 'Test Artist',
                            'title': 'Test Album',
                            'date': '2020-01-01',
                            'label-info-list': [
                                {
                                    'label': {'name': 'Test Label'},
                                    'catalog-number': 'CAT-001'
                                }
                            ],
                            'medium-list': [
                                {
                                    'track-list': [
                                        {
                                            'position': '1',
                                            'recording': {
                                                'title': 'Test Track',
                                                'length': '180000'
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                    
                    album_info = {'artist': 'Test Artist', 'album': 'Test Album'}
                    metadata = enricher._search_musicbrainz(album_info)
                    
                    assert metadata is not None
                    assert metadata['artist'] == 'Test Artist'
                    assert metadata['album'] == 'Test Album'
    
    def test_search_musicbrainz_no_results(self, mock_musicbrainz):
        """Test MusicBrainz search with no results."""
        with patch('metadata_enricher.FLAC'):
            enricher = MetadataEnricher(sources=['musicbrainz'])
            
            with patch.object(enricher, '_rate_limit'):
                with patch('metadata_enricher.mb') as mock_mb:
                    mock_mb.search_releases.return_value = {'release-list': []}
                    
                    album_info = {'artist': 'Unknown', 'album': 'Unknown'}
                    metadata = enricher._search_musicbrainz(album_info)
                    
                    assert metadata is None
    
    def test_search_musicbrainz_missing_info(self, mock_musicbrainz):
        """Test MusicBrainz search with missing artist/album info."""
        with patch('metadata_enricher.FLAC'):
            enricher = MetadataEnricher(sources=['musicbrainz'])
            
            album_info = {'artist': None, 'album': None}
            metadata = enricher._search_musicbrainz(album_info)
            
            assert metadata is None


class TestSearchDiscogs:
    """Tests for _search_discogs method."""
    
    def test_search_discogs_success(self, mock_discogs):
        """Test successful Discogs search."""
        with patch('metadata_enricher.mb'):
            with patch('metadata_enricher.FLAC'):
                enricher = MetadataEnricher(
                    sources=['discogs'],
                    discogs_token='test_token'
                )
                
                # Create a proper mock release object
                mock_release = Mock()
                mock_artist = Mock()
                mock_artist.name = 'Test Artist'
                mock_release.artists = [mock_artist]
                mock_release.title = 'Test Album'
                mock_release.year = 2020
                mock_release.labels = []
                mock_release.genres = []
                mock_release.tracklist = []
                
                # Mock the search to return our mock release
                mock_discogs.search.return_value = [mock_release]
                enricher.discogs = mock_discogs
                
                with patch.object(enricher, '_rate_limit'):
                    album_info = {'artist': 'Test Artist', 'album': 'Test Album'}
                    metadata = enricher._search_discogs(album_info)
                    
                    assert metadata is not None
                    assert metadata['album'] == 'Test Album'
                    assert metadata['artist'] == 'Test Artist'
    
    def test_search_discogs_no_client(self, mock_musicbrainz):
        """Test Discogs search when client is not initialized."""
        with patch('metadata_enricher.FLAC'):
            enricher = MetadataEnricher(sources=['musicbrainz'])
            enricher.discogs = None
            
            album_info = {'artist': 'Test', 'album': 'Test'}
            metadata = enricher._search_discogs(album_info)
            
            assert metadata is None


class TestRateLimiting:
    """Tests for rate limiting."""
    
    def test_rate_limit_delay(self, mock_musicbrainz):
        """Test that rate limiting introduces appropriate delay."""
        with patch('metadata_enricher.FLAC'):
            enricher = MetadataEnricher(sources=['musicbrainz'])
            enricher.min_api_interval = 0.1  # Short interval for testing
            
            import time
            start = time.time()
            enricher._rate_limit()
            enricher._rate_limit()
            elapsed = time.time() - start
            
            # Should have at least one interval delay
            assert elapsed >= 0.1


class TestApplyMetadata:
    """Tests for _apply_metadata_to_flac method."""
    
    def test_apply_metadata_fill_missing(self, temp_dir, mock_musicbrainz):
        """Test applying metadata with fill_missing behavior."""
        with patch('metadata_enricher.FLAC') as mock_flac_class:
            enricher = MetadataEnricher(
                sources=['musicbrainz'],
                behavior='fill_missing'
            )
            
            file_path = temp_dir / "test.flac"
            file_path.write_text("mock flac")
            
            # Mock FLAC object
            mock_audio = MagicMock()
            mock_audio.__contains__ = lambda self, key: False  # No existing metadata
            mock_flac_class.return_value = mock_audio
            
            metadata = {
                'artist': 'Test Artist',
                'album': 'Test Album',
                'date': '2020'
            }
            
            success = enricher._apply_metadata_to_flac(file_path, metadata)
            
            assert success is True
            mock_audio.save.assert_called_once()
    
    def test_apply_metadata_overwrite(self, temp_dir, mock_musicbrainz):
        """Test applying metadata with overwrite behavior."""
        with patch('metadata_enricher.FLAC') as mock_flac_class:
            enricher = MetadataEnricher(
                sources=['musicbrainz'],
                behavior='overwrite'
            )
            
            file_path = temp_dir / "test.flac"
            file_path.write_text("mock flac")
            
            mock_audio = MagicMock()
            mock_audio.__contains__ = lambda self, key: True  # Has existing metadata
            mock_flac_class.return_value = mock_audio
            
            metadata = {
                'artist': 'New Artist',
                'album': 'New Album'
            }
            
            success = enricher._apply_metadata_to_flac(file_path, metadata)
            
            assert success is True
            # Should overwrite existing values
            assert mock_audio.__setitem__.call_count >= 2


class TestEnrichAlbum:
    """Tests for enrich_album method."""
    
    def test_enrich_album_success(self, temp_dir, mock_musicbrainz):
        """Test successful album enrichment."""
        with patch('metadata_enricher.FLAC'):
            enricher = MetadataEnricher(sources=['musicbrainz'])
            
            album_path = temp_dir / "Artist - Album"
            album_path.mkdir()
            
            flac_file = album_path / "01 - Track.flac"
            flac_file.write_text("mock flac")
            
            # Mock methods
            with patch.object(enricher, '_extract_album_info', return_value={
                'artist': 'Test Artist',
                'album': 'Test Album'
            }):
                with patch.object(enricher, '_search_album_metadata', return_value={
                    'artist': 'Test Artist',
                    'album': 'Test Album'
                }):
                    with patch.object(enricher, '_apply_metadata_to_flac', return_value=True):
                        success, error = enricher.enrich_album(album_path, [flac_file])
                        
                        assert success is True
                        assert error is None
    
    def test_enrich_album_no_metadata_found(self, temp_dir, mock_musicbrainz):
        """Test album enrichment when no metadata is found."""
        with patch('metadata_enricher.FLAC'):
            enricher = MetadataEnricher(sources=['musicbrainz'])
            
            album_path = temp_dir / "Album"
            album_path.mkdir()
            
            with patch.object(enricher, '_extract_album_info', return_value={}):
                with patch.object(enricher, '_search_album_metadata', return_value=None):
                    success, error = enricher.enrich_album(album_path, [])
                    
                    assert success is False
                    assert "No metadata found" in error
    
    def test_enrich_album_apply_fails(self, temp_dir, mock_musicbrainz):
        """Test album enrichment when applying metadata fails."""
        with patch('metadata_enricher.FLAC'):
            enricher = MetadataEnricher(sources=['musicbrainz'])
            
            album_path = temp_dir / "Album"
            album_path.mkdir()
            
            flac_file = album_path / "01.flac"
            flac_file.write_text("mock")
            
            with patch.object(enricher, '_extract_album_info', return_value={}):
                with patch.object(enricher, '_search_album_metadata', return_value={}):
                    with patch.object(enricher, '_apply_metadata_to_flac', return_value=False):
                        success, error = enricher.enrich_album(album_path, [flac_file])
                        
                        assert success is False
                        assert error is not None
    
    def test_enrich_album_exception_handling(self, temp_dir, mock_musicbrainz):
        """Test album enrichment exception handling."""
        with patch('metadata_enricher.FLAC'):
            enricher = MetadataEnricher(sources=['musicbrainz'])
            
            album_path = temp_dir / "Album"
            
            with patch.object(enricher, '_extract_album_info', side_effect=Exception("Test error")):
                success, error = enricher.enrich_album(album_path, [])
                
                assert success is False
                assert "error" in error.lower()


class TestSearchAlbumMetadata:
    """Tests for _search_album_metadata method."""
    
    def test_search_tries_all_sources(self, mock_musicbrainz):
        """Test that search tries all configured sources."""
        with patch('metadata_enricher.mb'):
            with patch('metadata_enricher.discogs_client'):
                with patch('metadata_enricher.FLAC'):
                    enricher = MetadataEnricher(sources=['musicbrainz'])  # Start with musicbrainz only
                    
                    album_info = {'artist': 'Test', 'album': 'Test'}
                    
                    with patch.object(enricher, '_search_musicbrainz', return_value=None):
                        with patch.object(enricher, '_search_discogs', return_value={'album': 'Test'}):
                            enricher.sources = ['musicbrainz', 'discogs']  # Now add discogs
                            metadata = enricher._search_album_metadata(album_info)
                            
                            # Should find result from second source
                            assert metadata is not None
                            assert metadata['album'] == 'Test'
    
    def test_search_stops_on_first_result(self, mock_musicbrainz):
        """Test that search stops after first successful result."""
        with patch('metadata_enricher.mb'):
            with patch('metadata_enricher.discogs_client'):
                with patch('metadata_enricher.FLAC'):
                    enricher = MetadataEnricher(sources=['musicbrainz'])  # Start with musicbrainz only
                    
                    album_info = {'artist': 'Test', 'album': 'Test'}
                    
                    # Mock musicbrainz to return metadata with identifiable content
                    mb_metadata = {'artist': 'Test', 'album': 'Test', 'label': 'MB Label'}
                    discogs_metadata = {'artist': 'Test', 'album': 'Test', 'label': 'Discogs Label'}
                    
                    with patch.object(enricher, '_search_musicbrainz', return_value=mb_metadata) as mb_mock:
                        with patch.object(enricher, '_search_discogs', return_value=discogs_metadata) as discogs_mock:
                            enricher.sources = ['musicbrainz', 'discogs']  # Now add discogs
                            metadata = enricher._search_album_metadata(album_info)
                            
                            # Should return first result and not call second source
                            assert metadata is not None
                            assert metadata == mb_metadata  # Should be the MusicBrainz result
                            mb_mock.assert_called_once()
                            discogs_mock.assert_not_called()


@pytest.mark.integration
class TestMetadataEnricherIntegration:
    """Integration tests (require actual dependencies)."""
    
    @pytest.mark.skip(reason="Requires actual MusicBrainz API access")
    def test_real_musicbrainz_search(self):
        """Test actual MusicBrainz search (requires network)."""
        enricher = MetadataEnricher(sources=['musicbrainz'])
        
        album_info = {
            'artist': 'Miles Davis',
            'album': 'Kind of Blue'
        }
        
        metadata = enricher._search_musicbrainz(album_info)
        
        assert metadata is not None
        assert 'Kind of Blue' in metadata['album']

