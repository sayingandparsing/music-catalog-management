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
    
    @staticmethod
    def generate_album_id() -> str:
        """
        Generate a new album UUID.
        
        Returns:
            UUID string
        """
        return str(uuid.uuid4())
    
    @staticmethod
    def calculate_audio_checksum(
        audio_files: List[Path],
        algorithm: str = 'sha256'
    ) -> str:
        """
        Calculate checksum for audio files.
        
        Checksums are calculated by:
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
        """
        # Sort files for consistent ordering
        sorted_files = sorted(audio_files, key=lambda p: str(p))
        
        # Calculate individual checksums
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
        **kwargs
    ) -> Optional[str]:
        """
        Create metadata file for an album.
        
        Args:
            album_path: Path to album directory
            audio_files: List of audio file paths
            **kwargs: Additional metadata fields
            
        Returns:
            Album ID if successful, None otherwise
        """
        try:
            # Generate album ID
            album_id = AlbumMetadata.generate_album_id()
            
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

