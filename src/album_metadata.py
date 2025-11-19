"""
Album metadata file management.
Handles .album_metadata files for album identification and deduplication.
"""

import json
import hashlib
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import tempfile


class AlbumMetadata:
    """
    Manages .album_metadata files for tracking album identity and checksums.
    """
    
    METADATA_FILENAME = ".album_metadata"
    
    # UUID v5 namespace for deterministic album IDs
    # Using a custom namespace UUID for music catalog
    ALBUM_ID_NAMESPACE = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')
    
    def __init__(self, album_path: Path):
        """
        Initialize album metadata manager.
        
        Args:
            album_path: Path to album directory
        """
        self.album_path = Path(album_path)
        self.metadata_file = self.album_path / self.METADATA_FILENAME
    
    def exists(self) -> bool:
        """
        Check if metadata file exists.
        
        Returns:
            True if metadata file exists
        """
        return self.metadata_file.exists()
    
    def read(self) -> Optional[Dict[str, Any]]:
        """
        Read metadata file.
        
        Returns:
            Metadata dict or None if file doesn't exist or is invalid
        """
        if not self.exists():
            return None
        
        try:
            with open(self.metadata_file, 'r') as f:
                data = json.load(f)
            
            # Validate required fields
            # Note: processed_album_id is optional (only after conversion)
            required_fields = ['album_id', 'created_at', 'audio_checksum']
            if not all(field in data for field in required_fields):
                return None
            
            return data
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading metadata file: {e}")
            return None
    
    def write(
        self,
        album_id: str,
        audio_checksum: str,
        created_at: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        Write metadata file.
        
        Args:
            album_id: Album UUID
            audio_checksum: SHA256 checksum of audio files
            created_at: Creation timestamp (defaults to now)
            **kwargs: Additional metadata fields
            
        Returns:
            True if successful
        """
        try:
            metadata = {
                'album_id': album_id,
                'created_at': created_at or datetime.now().isoformat(),
                'last_processed': datetime.now().isoformat(),
                'audio_checksum': audio_checksum,
                **kwargs
            }
            
            # Write atomically using temp file
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self.album_path,
                prefix='.tmp_metadata_',
                suffix='.json'
            )
            
            try:
                with open(temp_fd, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                # Atomic replace
                Path(temp_path).replace(self.metadata_file)
                return True
            finally:
                # Clean up temp file if it still exists
                if Path(temp_path).exists():
                    Path(temp_path).unlink()
        
        except (IOError, OSError) as e:
            print(f"Error writing metadata file: {e}")
            return False
    
    def update(self, **kwargs) -> bool:
        """
        Update existing metadata file.
        
        Args:
            **kwargs: Fields to update
            
        Returns:
            True if successful
        """
        # Read existing metadata
        existing = self.read()
        if not existing:
            return False
        
        # Update last_processed timestamp
        kwargs['last_processed'] = datetime.now().isoformat()
        
        # Merge with existing data
        existing.update(kwargs)
        
        # Write back
        return self.write(
            album_id=existing['album_id'],
            audio_checksum=existing['audio_checksum'],
            created_at=existing['created_at'],
            **{k: v for k, v in existing.items() 
               if k not in ['album_id', 'audio_checksum', 'created_at']}
        )
    
    def get_album_id(self) -> Optional[str]:
        """
        Get album ID from metadata file.
        
        Returns:
            Album ID or None
        """
        metadata = self.read()
        return metadata['album_id'] if metadata else None
    
    def get_checksum(self) -> Optional[str]:
        """
        Get audio checksum from metadata file.
        
        Returns:
            Checksum or None
        """
        metadata = self.read()
        return metadata['audio_checksum'] if metadata else None
    
    def get_processed_album_id(self) -> Optional[str]:
        """
        Get processed album ID from metadata file.
        
        Returns:
            Processed album ID or None
        """
        metadata = self.read()
        return metadata.get('processed_album_id') if metadata else None
    
    def set_processed_album_id(self, processed_album_id: str) -> bool:
        """
        Set processed album ID in metadata file.
        
        Args:
            processed_album_id: Processed album ID to set
            
        Returns:
            True if successful
        """
        return self.update(processed_album_id=processed_album_id)
    
    @staticmethod
    def validate_audio_files(audio_files: List[Path]) -> None:
        """
        Validate that audio files don't mix ISO and FLAC/DSF formats.
        
        Args:
            audio_files: List of audio file paths
            
        Raises:
            ValueError: If files contain mixed ISO and FLAC/DSF formats
        """
        if not audio_files:
            return
        
        extensions = {f.suffix.lower() for f in audio_files}
        has_iso = '.iso' in extensions
        has_flac_dsf = bool(extensions & {'.flac', '.dsf', '.dff'})
        
        if has_iso and has_flac_dsf:
            raise ValueError(
                "Mixed album formats not supported: album contains both ISO and FLAC/DSF files. "
                "Albums must be either ISO-only or FLAC/DSF-only."
            )
    
    @staticmethod
    def generate_album_id(audio_files: List[Path]) -> str:
        """
        Generate a deterministic album UUID based on audio content.
        
        Uses UUID v5 with content hash to ensure the same audio files
        always produce the same album ID.
        
        Args:
            audio_files: List of audio file paths
            
        Returns:
            UUID v5 string derived from audio content
            
        Raises:
            ValueError: If audio files contain mixed ISO and FLAC/DSF formats
        """
        # Validate audio files first
        AlbumMetadata.validate_audio_files(audio_files)
        
        # Calculate content checksum
        content_hash = AlbumMetadata.calculate_audio_checksum(audio_files)
        
        # Generate deterministic UUID v5 from content hash
        album_uuid = uuid.uuid5(AlbumMetadata.ALBUM_ID_NAMESPACE, content_hash)
        
        return str(album_uuid)
    
    @staticmethod
    def calculate_audio_checksum(
        audio_files: List[Path],
        algorithm: str = 'sha256'
    ) -> str:
        """
        Calculate checksum for audio files.
        
        For ISO files:
        - Hash first 20MB + file size (fast, collision-resistant)
        
        For FLAC/DSF files:
        1. Sorting file paths alphabetically
        2. For each file, calculate individual checksum
        3. Concatenate all checksums and hash the result
        
        This approach is faster than hashing all file contents sequentially
        and allows for parallel processing in the future.
        
        Args:
            audio_files: List of audio file paths
            algorithm: Hash algorithm (default: sha256)
            
        Returns:
            Hex digest of combined checksum
            
        Raises:
            ValueError: If files contain mixed ISO and FLAC/DSF formats
        """
        # Validate no mixed formats
        AlbumMetadata.validate_audio_files(audio_files)
        
        # Sort files for consistent ordering
        sorted_files = sorted(audio_files, key=lambda p: str(p))
        
        # Check if this is an ISO album
        if sorted_files and sorted_files[0].suffix.lower() == '.iso':
            # For ISO files, use special fast hashing
            # (should only be one ISO file per album)
            return AlbumMetadata._calculate_iso_checksum(
                sorted_files[0],
                algorithm
            )
        
        # For FLAC/DSF files, calculate individual checksums
        file_checksums = []
        for file_path in sorted_files:
            file_checksum = AlbumMetadata._calculate_file_checksum(
                file_path,
                algorithm
            )
            file_checksums.append(file_checksum)
        
        # Combine all checksums
        combined = ''.join(file_checksums)
        
        # Hash the combined string
        hash_obj = hashlib.new(algorithm)
        hash_obj.update(combined.encode('utf-8'))
        
        return hash_obj.hexdigest()
    
    @staticmethod
    def _calculate_iso_checksum(
        file_path: Path,
        algorithm: str = 'sha256'
    ) -> str:
        """
        Calculate checksum for an ISO file using first 20MB + file size.
        
        This is much faster than hashing the entire ISO file (which can be 5GB+)
        while still providing excellent collision resistance.
        
        Args:
            file_path: Path to ISO file
            algorithm: Hash algorithm
            
        Returns:
            Hex digest of partial checksum
        """
        hash_obj = hashlib.new(algorithm)
        
        # Get file size
        file_size = file_path.stat().st_size
        
        # Read first 20MB (or full file if smaller)
        chunk_size = 20 * 1024 * 1024  # 20MB
        bytes_to_read = min(chunk_size, file_size)
        
        with open(file_path, 'rb') as f:
            # Read in 8MB chunks up to 20MB total
            bytes_read = 0
            while bytes_read < bytes_to_read:
                chunk = f.read(min(8192 * 1024, bytes_to_read - bytes_read))
                if not chunk:
                    break
                hash_obj.update(chunk)
                bytes_read += len(chunk)
        
        # Include file size in hash for additional uniqueness
        hash_obj.update(str(file_size).encode('utf-8'))
        
        return hash_obj.hexdigest()
    
    @staticmethod
    def _calculate_file_checksum(
        file_path: Path,
        algorithm: str = 'sha256'
    ) -> str:
        """
        Calculate checksum for a single file.
        
        Args:
            file_path: Path to file
            algorithm: Hash algorithm
            
        Returns:
            Hex digest of file checksum
        """
        hash_obj = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            # Read in chunks for memory efficiency
            for chunk in iter(lambda: f.read(8192 * 1024), b''):  # 8MB chunks
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
    
    @staticmethod
    def create_for_album(
        album_path: Path,
        audio_files: List[Path],
        album_id: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Create metadata file for an album.
        
        Args:
            album_path: Path to album directory
            audio_files: List of audio file paths
            album_id: Optional original album ID (for processed/converted albums)
            **kwargs: Additional metadata fields
            
        Returns:
            Album ID if successful, None otherwise
        """
        try:
            # If album_id is provided (e.g., for converted albums), use it
            # Otherwise, generate deterministic album ID from audio content
            if album_id is None:
                album_id = AlbumMetadata.generate_album_id(audio_files)
            
            # Calculate audio checksum
            audio_checksum = AlbumMetadata.calculate_audio_checksum(audio_files)
            
            # Create metadata manager
            metadata = AlbumMetadata(album_path)
            
            # Write metadata file
            success = metadata.write(
                album_id=album_id,
                audio_checksum=audio_checksum,
                **kwargs
            )
            
            return album_id if success else None
        except Exception as e:
            print(f"Error creating metadata for album: {e}")
            return None
    
    @staticmethod
    def verify_checksum(
        album_path: Path,
        audio_files: List[Path]
    ) -> bool:
        """
        Verify that current audio files match stored checksum.
        
        Args:
            album_path: Path to album directory
            audio_files: List of current audio file paths
            
        Returns:
            True if checksums match
        """
        metadata = AlbumMetadata(album_path)
        stored_checksum = metadata.get_checksum()
        
        if not stored_checksum:
            return False
        
        current_checksum = AlbumMetadata.calculate_audio_checksum(audio_files)
        
        return stored_checksum == current_checksum


class AlbumIdentifier:
    """
    Helper class for identifying albums across different locations.
    """
    
    @staticmethod
    def find_album_by_id(
        search_paths: List[Path],
        album_id: str,
        music_extensions: Optional[List[str]] = None
    ) -> Optional[Path]:
        """
        Find an album directory by its ID across multiple search paths.
        
        Args:
            search_paths: List of directories to search
            album_id: Album ID to find
            music_extensions: Music file extensions to identify albums
            
        Returns:
            Path to album directory or None if not found
        """
        music_extensions = music_extensions or ['.iso', '.dsf', '.dff', '.flac']
        music_extensions = [ext.lower() for ext in music_extensions]
        
        for search_path in search_paths:
            if not search_path.exists():
                continue
            
            # Walk through directory tree
            for dirpath, dirnames, filenames in search_path.walk():
                # Check if this directory has a metadata file
                metadata_file = dirpath / AlbumMetadata.METADATA_FILENAME
                
                if metadata_file.exists():
                    try:
                        metadata = AlbumMetadata(dirpath)
                        if metadata.get_album_id() == album_id:
                            return dirpath
                    except Exception:
                        continue
        
        return None
    
    @staticmethod
    def get_album_info(album_path: Path) -> Optional[Dict[str, Any]]:
        """
        Get album information from metadata file.
        
        Args:
            album_path: Path to album directory
            
        Returns:
            Album info dict or None
        """
        metadata = AlbumMetadata(album_path)
        return metadata.read()

