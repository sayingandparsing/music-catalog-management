"""
Deduplication logic for preventing reprocessing of albums.
Checks album metadata files and database for processing status.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from src.album_metadata import AlbumMetadata, AlbumIdentifier
from src.database import MusicDatabase


@dataclass
class ProcessingStatus:
    """Status of album processing."""
    is_processed: bool
    album_id: Optional[str] = None
    checksum_matches: bool = False
    in_database: bool = False
    database_record: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


class DeduplicationManager:
    """
    Manages deduplication logic to prevent reprocessing albums.
    """
    
    def __init__(
        self,
        database: MusicDatabase,
        verify_checksums: bool = True
    ):
        """
        Initialize deduplication manager.
        
        Args:
            database: MusicDatabase instance
            verify_checksums: Whether to verify audio file checksums
        """
        self.database = database
        self.verify_checksums = verify_checksums
    
    def check_album_status(
        self,
        album_path: Path,
        audio_files: List[Path]
    ) -> ProcessingStatus:
        """
        Check if an album has already been processed.
        
        Args:
            album_path: Path to album directory
            audio_files: List of audio files in album
            
        Returns:
            ProcessingStatus object with details
        """
        # Check for metadata file
        metadata = AlbumMetadata(album_path)
        
        if not metadata.exists():
            # No metadata file - album not processed
            return ProcessingStatus(
                is_processed=False,
                reason="No metadata file found"
            )
        
        # Read metadata
        metadata_dict = metadata.read()
        if not metadata_dict:
            # Invalid metadata file
            return ProcessingStatus(
                is_processed=False,
                reason="Invalid metadata file"
            )
        
        album_id = metadata_dict.get('album_id')
        stored_checksum = metadata_dict.get('audio_checksum')
        
        if not album_id or not stored_checksum:
            # Missing required fields
            return ProcessingStatus(
                is_processed=False,
                album_id=album_id,
                reason="Missing required metadata fields"
            )
        
        # Verify checksum if enabled
        checksum_matches = False
        if self.verify_checksums:
            current_checksum = AlbumMetadata.calculate_audio_checksum(audio_files)
            checksum_matches = (current_checksum == stored_checksum)
            
            if not checksum_matches:
                # Checksums don't match - files changed
                return ProcessingStatus(
                    is_processed=False,
                    album_id=album_id,
                    checksum_matches=False,
                    reason="Audio files changed (checksum mismatch)"
                )
        else:
            # Assume checksum matches if not verifying
            checksum_matches = True
        
        # Check database for album record
        db_record = self.database.get_album_by_id(album_id)
        
        if not db_record:
            # Album not in database - metadata file exists but no DB record
            # This could happen if database was reset or metadata file copied
            return ProcessingStatus(
                is_processed=False,
                album_id=album_id,
                checksum_matches=checksum_matches,
                in_database=False,
                reason="Album not found in database"
            )
        
        # Album found in database - check if it was successfully processed
        # We consider an album processed if it has both archive_path and playback_path
        archive_path = db_record.get('archive_path')
        playback_path = db_record.get('playback_path')
        
        if not archive_path or not playback_path:
            return ProcessingStatus(
                is_processed=False,
                album_id=album_id,
                checksum_matches=checksum_matches,
                in_database=True,
                database_record=db_record,
                reason="Processing incomplete (missing archive or playback path)"
            )
        
        # Check processing history for successful conversion
        history = self.database.get_processing_history(album_id, 'convert')
        has_successful_conversion = any(
            h.get('status') == 'success' for h in history
        )
        
        if not has_successful_conversion:
            return ProcessingStatus(
                is_processed=False,
                album_id=album_id,
                checksum_matches=checksum_matches,
                in_database=True,
                database_record=db_record,
                reason="No successful conversion in history"
            )
        
        # Album is fully processed
        return ProcessingStatus(
            is_processed=True,
            album_id=album_id,
            checksum_matches=checksum_matches,
            in_database=True,
            database_record=db_record,
            reason="Album already processed"
        )
    
    def find_duplicate_by_checksum(
        self,
        audio_files: List[Path]
    ) -> Optional[Dict[str, Any]]:
        """
        Find if an album with the same audio checksum exists in database.
        
        Args:
            audio_files: List of audio files
            
        Returns:
            Database record if duplicate found, None otherwise
        """
        checksum = AlbumMetadata.calculate_audio_checksum(audio_files)
        return self.database.get_album_by_checksum(checksum)
    
    def should_skip_album(
        self,
        album_path: Path,
        audio_files: List[Path],
        force_reprocess: bool = False
    ) -> Tuple[bool, str]:
        """
        Determine if an album should be skipped.
        
        Args:
            album_path: Path to album directory
            audio_files: List of audio files
            force_reprocess: Force reprocessing even if already processed
            
        Returns:
            Tuple of (should_skip, reason)
        """
        if force_reprocess:
            return False, "Force reprocess enabled"
        
        status = self.check_album_status(album_path, audio_files)
        
        if status.is_processed:
            return True, f"Already processed: {status.reason}"
        
        return False, "Not processed or needs reprocessing"
    
    def get_or_create_album_id(
        self,
        album_path: Path,
        audio_files: List[Path]
    ) -> str:
        """
        Get existing album ID or create a new deterministic one.
        
        Since album IDs are now deterministic (based on audio content),
        the same audio files will always produce the same ID.
        
        Args:
            album_path: Path to album directory
            audio_files: List of audio files
            
        Returns:
            Album ID (UUID v5 derived from audio content)
        """
        metadata = AlbumMetadata(album_path)
        
        # Check if metadata file exists and is valid
        if metadata.exists():
            album_id = metadata.get_album_id()
            if album_id:
                return album_id
        
        # Generate deterministic album ID from audio content
        # This will always produce the same ID for the same audio files
        album_id = AlbumMetadata.generate_album_id(audio_files)
        checksum = AlbumMetadata.calculate_audio_checksum(audio_files)
        
        # Write metadata file
        metadata.write(
            album_id=album_id,
            audio_checksum=checksum
        )
        
        return album_id
    
    def reconcile_moved_album(
        self,
        old_path: str,
        new_path: Path,
        album_id: str
    ) -> bool:
        """
        Update database when an album has been moved.
        
        Args:
            old_path: Old path (from database)
            new_path: New path (current location)
            album_id: Album ID
            
        Returns:
            True if successful
        """
        try:
            # Determine which path type was moved
            db_record = self.database.get_album_by_id(album_id)
            if not db_record:
                return False
            
            updates = {}
            
            if db_record.get('source_path') == old_path:
                updates['source_path'] = str(new_path)
            elif db_record.get('archive_path') == old_path:
                updates['archive_path'] = str(new_path)
            elif db_record.get('playback_path') == old_path:
                updates['playback_path'] = str(new_path)
            
            if updates:
                result = self.database.update_album(album_id, **updates)
                if result:
                    self.database.commit()
                return result
            
            return True
        except Exception as e:
            print(f"Error reconciling moved album: {e}")
            return False


class AlbumRegistry:
    """
    Registry for tracking albums across multiple locations.
    """
    
    def __init__(self, database: MusicDatabase):
        """
        Initialize album registry.
        
        Args:
            database: MusicDatabase instance
        """
        self.database = database
    
    def register_album_location(
        self,
        album_id: str,
        location_type: str,
        path: Path
    ) -> bool:
        """
        Register an album location in the database.
        
        Args:
            album_id: Album ID
            location_type: Type of location (source/archive/playback)
            path: Path to album
            
        Returns:
            True if successful
        """
        valid_types = ['source_path', 'archive_path', 'playback_path']
        if location_type not in valid_types:
            location_type = f"{location_type}_path"
        
        if location_type not in valid_types:
            return False
        
        result = self.database.update_album(
            album_id,
            **{location_type: str(path)}
        )
        if result:
            self.database.commit()
        return result
    
    def find_album_locations(
        self,
        album_id: str
    ) -> Dict[str, Optional[str]]:
        """
        Find all known locations for an album.
        
        Args:
            album_id: Album ID
            
        Returns:
            Dict with source_path, archive_path, playback_path
        """
        record = self.database.get_album_by_id(album_id)
        
        if not record:
            return {
                'source_path': None,
                'archive_path': None,
                'playback_path': None
            }
        
        return {
            'source_path': record.get('source_path'),
            'archive_path': record.get('archive_path'),
            'playback_path': record.get('playback_path')
        }
    
    def verify_album_locations(
        self,
        album_id: str
    ) -> Dict[str, bool]:
        """
        Verify which album locations still exist.
        
        Args:
            album_id: Album ID
            
        Returns:
            Dict with existence status for each location
        """
        locations = self.find_album_locations(album_id)
        
        return {
            'source_exists': Path(locations['source_path']).exists() 
                if locations['source_path'] else False,
            'archive_exists': Path(locations['archive_path']).exists() 
                if locations['archive_path'] else False,
            'playback_exists': Path(locations['playback_path']).exists() 
                if locations['playback_path'] else False
        }

