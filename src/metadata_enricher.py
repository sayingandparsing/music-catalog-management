"""
Metadata enrichment for music files.
Integrates with MusicBrainz and Discogs APIs.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
import time
import re

try:
    import musicbrainzngs as mb
except ImportError:
    mb = None

try:
    import discogs_client
except ImportError:
    discogs_client = None

try:
    from mutagen.flac import FLAC
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TRCK, TDRC, TCON
except ImportError:
    FLAC = None


class MetadataEnricher:
    """
    Enriches music file metadata using external APIs.
    Supports MusicBrainz and Discogs.
    """
    
    def __init__(
        self,
        sources: Optional[List[str]] = None,
        discogs_token: Optional[str] = None,
        behavior: str = "fill_missing"
    ):
        """
        Initialize metadata enricher.
        
        Args:
            sources: List of sources to use ('musicbrainz', 'discogs')
            discogs_token: Discogs API user token
            behavior: 'fill_missing' or 'overwrite'
        """
        self.sources = sources or ['musicbrainz', 'discogs']
        self.discogs_token = discogs_token
        self.behavior = behavior
        
        # Initialize MusicBrainz
        if 'musicbrainz' in self.sources:
            if mb is None:
                raise ImportError(
                    "musicbrainzngs not installed. "
                    "Install with: pip install python-musicbrainzngs"
                )
            mb.set_useragent("DSD Music Converter", "1.0", "converter@example.com")
        
        # Initialize Discogs
        self.discogs = None
        if 'discogs' in self.sources:
            if discogs_client is None:
                raise ImportError(
                    "discogs_client not installed. "
                    "Install with: pip install python3-discogs-client"
                )
            if discogs_token:
                self.discogs = discogs_client.Client(
                    'DSDMusicConverter/1.0',
                    user_token=discogs_token
                )
        
        # Check mutagen
        if FLAC is None:
            raise ImportError(
                "mutagen not installed. "
                "Install with: pip install mutagen"
            )
        
        # Rate limiting
        self.last_api_call = 0
        self.min_api_interval = 1.0  # seconds between API calls
    
    def enrich_album(
        self,
        album_path: Path,
        music_files: List[Path]
    ) -> tuple[bool, Optional[str]]:
        """
        Enrich metadata for all files in an album.
        
        Args:
            album_path: Path to album directory
            music_files: List of music file paths
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Extract album info from path or existing files
            album_info = self._extract_album_info(album_path, music_files)
            
            # Search for album metadata
            metadata = self._search_album_metadata(album_info)
            
            if not metadata:
                return False, "No metadata found for album"
            
            # Apply metadata to files
            for file_path in music_files:
                if file_path.suffix.lower() == '.flac':
                    success = self._apply_metadata_to_flac(file_path, metadata)
                    if not success:
                        return False, f"Failed to apply metadata to {file_path.name}"
            
            return True, None
            
        except Exception as e:
            return False, f"Error enriching metadata: {e}"
    
    def _extract_album_info(
        self,
        album_path: Path,
        music_files: List[Path]
    ) -> Dict[str, Any]:
        """
        Extract album information from path and existing metadata.
        
        Args:
            album_path: Path to album
            music_files: List of music files
            
        Returns:
            Dictionary with album info
        """
        info = {
            'album': None,
            'artist': None,
            'year': None,
            'tracks': []
        }
        
        # Try to parse from directory name
        # Common patterns: "Artist - Album (Year)" or "Artist - Album"
        album_name = album_path.name
        
        # Pattern: Artist - Album (Year)
        match = re.match(r'(.+?)\s*-\s*(.+?)\s*\((\d{4})\)', album_name)
        if match:
            info['artist'] = match.group(1).strip()
            info['album'] = match.group(2).strip()
            info['year'] = match.group(3)
        else:
            # Pattern: Artist - Album
            match = re.match(r'(.+?)\s*-\s*(.+)', album_name)
            if match:
                info['artist'] = match.group(1).strip()
                info['album'] = match.group(2).strip()
            else:
                # Just album name
                info['album'] = album_name
        
        # Try to get metadata from first FLAC file if available
        if music_files:
            first_file = music_files[0]
            if first_file.suffix.lower() == '.flac':
                try:
                    audio = FLAC(first_file)
                    if not info['artist'] and 'artist' in audio:
                        info['artist'] = audio['artist'][0]
                    if not info['album'] and 'album' in audio:
                        info['album'] = audio['album'][0]
                    if not info['year'] and 'date' in audio:
                        info['year'] = audio['date'][0][:4]
                except:
                    pass
        
        return info
    
    def _search_album_metadata(
        self,
        album_info: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Search for album metadata from configured sources.
        
        Args:
            album_info: Album information for search
            
        Returns:
            Metadata dictionary or None
        """
        for source in self.sources:
            if source == 'musicbrainz':
                metadata = self._search_musicbrainz(album_info)
                if metadata:
                    return metadata
            elif source == 'discogs' and self.discogs:
                metadata = self._search_discogs(album_info)
                if metadata:
                    return metadata
        
        return None
    
    def _search_musicbrainz(
        self,
        album_info: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Search MusicBrainz for album metadata.
        
        Args:
            album_info: Album information
            
        Returns:
            Metadata dictionary or None
        """
        try:
            self._rate_limit()
            
            artist = album_info.get('artist', '')
            album = album_info.get('album', '')
            
            if not artist or not album:
                return None
            
            # Search for release
            result = mb.search_releases(
                artist=artist,
                release=album,
                limit=5
            )
            
            if not result.get('release-list'):
                return None
            
            # Get first result
            release = result['release-list'][0]
            release_id = release['id']
            
            # Get detailed release info
            self._rate_limit()
            detailed = mb.get_release_by_id(
                release_id,
                includes=['artists', 'recordings', 'labels']
            )
            
            release_data = detailed['release']
            
            # Extract metadata
            metadata = {
                'artist': release_data['artist-credit-phrase'],
                'album': release_data['title'],
                'date': release_data.get('date', ''),
                'label': None,
                'catalog_number': None,
                'tracks': []
            }
            
            # Extract label info
            if 'label-info-list' in release_data:
                label_info = release_data['label-info-list'][0]
                if 'label' in label_info:
                    metadata['label'] = label_info['label'].get('name')
                metadata['catalog_number'] = label_info.get('catalog-number')
            
            # Extract track info
            if 'medium-list' in release_data:
                for medium in release_data['medium-list']:
                    if 'track-list' in medium:
                        for track in medium['track-list']:
                            recording = track['recording']
                            metadata['tracks'].append({
                                'number': track['position'],
                                'title': recording['title'],
                                'length': recording.get('length')
                            })
            
            return metadata
            
        except Exception as e:
            print(f"MusicBrainz search error: {e}")
            return None
    
    def _search_discogs(
        self,
        album_info: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Search Discogs for album metadata.
        
        Args:
            album_info: Album information
            
        Returns:
            Metadata dictionary or None
        """
        if not self.discogs:
            return None
        
        try:
            self._rate_limit()
            
            artist = album_info.get('artist', '')
            album = album_info.get('album', '')
            
            if not artist or not album:
                return None
            
            # Search for release
            results = self.discogs.search(
                f"{artist} {album}",
                type='release'
            )
            
            if not results:
                return None
            
            # Get first result
            release = results[0]
            
            # Extract metadata
            metadata = {
                'artist': release.artists[0].name if release.artists else artist,
                'album': release.title,
                'date': str(release.year) if hasattr(release, 'year') else '',
                'label': release.labels[0].name if release.labels else None,
                'catalog_number': release.labels[0].catno if release.labels else None,
                'genre': ', '.join(release.genres) if hasattr(release, 'genres') else None,
                'tracks': []
            }
            
            # Extract track info
            if hasattr(release, 'tracklist'):
                for track in release.tracklist:
                    metadata['tracks'].append({
                        'number': track.position,
                        'title': track.title,
                        'length': track.duration
                    })
            
            return metadata
            
        except Exception as e:
            print(f"Discogs search error: {e}")
            return None
    
    def _apply_metadata_to_flac(
        self,
        file_path: Path,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Apply metadata to FLAC file.
        
        Args:
            file_path: Path to FLAC file
            metadata: Metadata dictionary
            
        Returns:
            True if successful
        """
        try:
            audio = FLAC(file_path)
            
            # Determine track number from filename if possible
            track_num = self._extract_track_number(file_path)
            
            # Apply metadata based on behavior
            if self.behavior == 'overwrite' or self.behavior == 'fill_missing':
                if metadata.get('artist'):
                    if self.behavior == 'overwrite' or 'artist' not in audio:
                        audio['artist'] = metadata['artist']
                
                if metadata.get('album'):
                    if self.behavior == 'overwrite' or 'album' not in audio:
                        audio['album'] = metadata['album']
                
                if metadata.get('date'):
                    if self.behavior == 'overwrite' or 'date' not in audio:
                        audio['date'] = metadata['date']
                
                if metadata.get('label'):
                    if self.behavior == 'overwrite' or 'label' not in audio:
                        audio['label'] = metadata['label']
                
                if metadata.get('catalog_number'):
                    if self.behavior == 'overwrite' or 'catalognumber' not in audio:
                        audio['catalognumber'] = metadata['catalog_number']
                
                if metadata.get('genre'):
                    if self.behavior == 'overwrite' or 'genre' not in audio:
                        audio['genre'] = metadata['genre']
                
                # Try to match track info
                if track_num and metadata.get('tracks'):
                    for track_info in metadata['tracks']:
                        if str(track_info.get('number')) == str(track_num):
                            if self.behavior == 'overwrite' or 'title' not in audio:
                                audio['title'] = track_info['title']
                            if self.behavior == 'overwrite' or 'tracknumber' not in audio:
                                audio['tracknumber'] = str(track_num)
                            break
            
            audio.save()
            return True
            
        except Exception as e:
            print(f"Error applying metadata to {file_path}: {e}")
            return False
    
    def _extract_track_number(self, file_path: Path) -> Optional[str]:
        """
        Extract track number from filename.
        
        Args:
            file_path: Path to file
            
        Returns:
            Track number or None
        """
        # Try to match patterns like "01 - ", "01. ", "Track 01", etc.
        patterns = [
            r'^(\d+)\s*[-.]',  # "01 - " or "01. "
            r'track\s*(\d+)',  # "Track 01"
            r'_(\d+)_',  # "_01_"
        ]
        
        filename = file_path.stem
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return match.group(1).lstrip('0') or '0'
        
        return None
    
    def _rate_limit(self):
        """Apply rate limiting for API calls."""
        now = time.time()
        time_since_last = now - self.last_api_call
        
        if time_since_last < self.min_api_interval:
            time.sleep(self.min_api_interval - time_since_last)
        
        self.last_api_call = time.time()

