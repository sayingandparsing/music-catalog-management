"""
Metadata enrichment for music files.
Integrates with MusicBrainz and Discogs APIs.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
import time
import re
import uuid

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
        behavior: str = "fill_missing",
        database=None
    ):
        """
        Initialize metadata enricher.
        
        Args:
            sources: List of sources to use ('musicbrainz', 'discogs')
            discogs_token: Discogs API user token
            behavior: 'fill_missing' or 'overwrite'
            database: MusicDatabase instance (optional, for storing candidates)
        """
        self.sources = sources or ['musicbrainz', 'discogs']
        self.discogs_token = discogs_token
        self.behavior = behavior
        self.database = database
        
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
        music_files: List[Path],
        album_id: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Enrich metadata for all files in an album.
        
        Args:
            album_path: Path to album directory
            music_files: List of music file paths
            album_id: Optional album UUID for database storage
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Extract album info from path or existing files
            album_info = self._extract_album_info(album_path, music_files)
            
            # Search for album metadata and candidates
            metadata, all_candidates = self._search_album_metadata_with_candidates(
                album_info,
                album_id
            )
            
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
    
    def _search_album_metadata_with_candidates(
        self,
        album_info: Dict[str, Any],
        album_id: Optional[str] = None
    ) -> tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Search for album metadata and collect all candidates from configured sources.
        
        Args:
            album_info: Album information for search
            album_id: Optional album UUID for database storage
            
        Returns:
            Tuple of (best_metadata, all_candidates_list)
        """
        best_metadata = None
        all_candidates = []
        
        for source in self.sources:
            if source == 'musicbrainz':
                candidates = self._search_musicbrainz_candidates(album_info, limit=5)
                all_candidates.extend(candidates)
                if not best_metadata and candidates:
                    best_metadata = candidates[0]['metadata']
            elif source == 'discogs' and self.discogs:
                candidates = self._search_discogs_candidates(album_info, limit=5)
                all_candidates.extend(candidates)
                if not best_metadata and candidates:
                    best_metadata = candidates[0]['metadata']
        
        # Store candidates in database if available
        if self.database and album_id and all_candidates:
            self._store_metadata_candidates(album_id, all_candidates)
        
        return best_metadata, all_candidates
    
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
        metadata, _ = self._search_album_metadata_with_candidates(album_info)
        return metadata
    
    def _search_musicbrainz_candidates(
        self,
        album_info: Dict[str, Any],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search MusicBrainz for album metadata candidates.
        
        Args:
            album_info: Album information
            limit: Maximum number of candidates to return
            
        Returns:
            List of candidate dictionaries with metadata and source info
        """
        candidates = []
        
        try:
            self._rate_limit()
            
            artist = album_info.get('artist', '')
            album = album_info.get('album', '')
            
            if not artist or not album:
                return candidates
            
            # Search for releases
            result = mb.search_releases(
                artist=artist,
                release=album,
                limit=limit
            )
            
            if not result.get('release-list'):
                return candidates
            
            # Process each result
            for rank, release in enumerate(result['release-list'][:limit], 1):
                release_id = release['id']
                
                # Get detailed release info
                self._rate_limit()
                try:
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
                    if 'label-info-list' in release_data and release_data['label-info-list']:
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
                    
                    # Calculate confidence score (simplified)
                    confidence = 1.0 - (rank - 1) * 0.15
                    
                    candidates.append({
                        'source': 'musicbrainz',
                        'source_id': release_id,
                        'rank': rank,
                        'confidence_score': max(0.1, confidence),
                        'metadata': metadata
                    })
                
                except Exception as e:
                    print(f"Error fetching MusicBrainz release {release_id}: {e}")
                    continue
        
        except Exception as e:
            print(f"MusicBrainz search error: {e}")
        
        return candidates
    
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
            print(f"MusicBrainz search error (legacy): {e}")
            return None
    
    def _search_discogs_candidates(
        self,
        album_info: Dict[str, Any],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search Discogs for album metadata candidates.
        
        Args:
            album_info: Album information
            limit: Maximum number of candidates to return
            
        Returns:
            List of candidate dictionaries with metadata and source info
        """
        candidates = []
        
        if not self.discogs:
            return candidates
        
        try:
            self._rate_limit()
            
            artist = album_info.get('artist', '')
            album = album_info.get('album', '')
            
            if not artist or not album:
                return candidates
            
            # Search for releases
            results = self.discogs.search(
                f"{artist} {album}",
                type='release'
            )
            
            if not results:
                return candidates
            
            # Process each result
            for rank, release in enumerate(results[:limit], 1):
                try:
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
                    
                    # Calculate confidence score
                    confidence = 1.0 - (rank - 1) * 0.15
                    
                    candidates.append({
                        'source': 'discogs',
                        'source_id': str(release.id),
                        'rank': rank,
                        'confidence_score': max(0.1, confidence),
                        'metadata': metadata
                    })
                
                except Exception as e:
                    print(f"Error processing Discogs release: {e}")
                    continue
        
        except Exception as e:
            print(f"Discogs search error: {e}")
        
        return candidates
    
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
            print(f"Discogs search error (legacy): {e}")
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
    
    def _store_metadata_candidates(
        self,
        album_id: str,
        candidates: List[Dict[str, Any]]
    ) -> bool:
        """
        Store metadata candidates in database.
        
        Args:
            album_id: Album UUID
            candidates: List of candidate dictionaries
            
        Returns:
            True if successful
        """
        if not self.database:
            return False
        
        try:
            for candidate in candidates:
                candidate_id = str(uuid.uuid4())
                
                self.database.create_metadata_candidate(
                    candidate_id=candidate_id,
                    album_id=album_id,
                    source=candidate['source'],
                    source_id=candidate['source_id'],
                    rank=candidate['rank'],
                    metadata_dict=candidate['metadata'],
                    confidence_score=candidate.get('confidence_score')
                )
            
            return True
        except Exception as e:
            print(f"Error storing metadata candidates: {e}")
            return False

