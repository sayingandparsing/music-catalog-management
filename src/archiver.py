"""
Archiver for backing up original music files before conversion.
Preserves directory structure and file metadata.
"""

import shutil
import os
from pathlib import Path
from typing import Optional
from datetime import datetime
import hashlib


class Archiver:
    """
    Handles archiving of original music files.
    Creates backups before conversion with integrity verification.
    """
    
    def __init__(self, archive_root: Path, verify_copies: bool = True):
        """
        Initialize archiver.
        
        Args:
            archive_root: Root directory for archives
            verify_copies: Whether to verify copied files with checksums
        """
        self.archive_root = Path(archive_root)
        self.verify_copies = verify_copies
        
        # Create archive root if it doesn't exist
        self.archive_root.mkdir(parents=True, exist_ok=True)
    
    def archive_album(
        self,
        album_path: Path,
        preserve_timestamps: bool = True
    ) -> tuple[bool, Optional[Path], Optional[str]]:
        """
        Archive an album directory.
        
        Args:
            album_path: Path to album directory to archive
            preserve_timestamps: Whether to preserve file timestamps
            
        Returns:
            Tuple of (success, archive_path, error_message)
        """
        try:
            # Create archive path
            archive_path = self._get_archive_path(album_path)
            
            # Check if already archived
            if archive_path.exists():
                # Archive already exists, assume it's valid
                return True, archive_path, None
            
            # Create parent directory
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy directory tree
            shutil.copytree(
                album_path,
                archive_path,
                symlinks=False,
                copy_function=shutil.copy2 if preserve_timestamps else shutil.copy
            )
            
            # Verify copy if requested
            if self.verify_copies:
                verification_result = self._verify_copy(album_path, archive_path)
                if not verification_result[0]:
                    # Verification failed, clean up
                    shutil.rmtree(archive_path, ignore_errors=True)
                    return False, None, verification_result[1]
            
            return True, archive_path, None
            
        except PermissionError as e:
            return False, None, f"Permission denied: {e}"
        except OSError as e:
            return False, None, f"OS error during archiving: {e}"
        except Exception as e:
            return False, None, f"Unexpected error: {e}"
    
    def _get_archive_path(self, album_path: Path) -> Path:
        """
        Generate archive path for an album.
        
        Args:
            album_path: Original album path
            
        Returns:
            Archive path
        """
        # Use album name as archive name
        album_name = album_path.name
        
        # Add timestamp to avoid conflicts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{album_name}_{timestamp}"
        
        return self.archive_root / archive_name
    
    def _verify_copy(
        self,
        source_dir: Path,
        dest_dir: Path
    ) -> tuple[bool, Optional[str]]:
        """
        Verify that copied directory matches source.
        
        Args:
            source_dir: Source directory
            dest_dir: Destination directory
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get all files in both directories
            source_files = self._get_all_files(source_dir)
            dest_files = self._get_all_files(dest_dir)
            
            # Check file counts match
            if len(source_files) != len(dest_files):
                return False, (
                    f"File count mismatch: "
                    f"source={len(source_files)}, dest={len(dest_files)}"
                )
            
            # Verify each file
            for source_file in source_files:
                rel_path = source_file.relative_to(source_dir)
                dest_file = dest_dir / rel_path
                
                # Check file exists
                if not dest_file.exists():
                    return False, f"Missing file in destination: {rel_path}"
                
                # Check file sizes match
                source_size = source_file.stat().st_size
                dest_size = dest_file.stat().st_size
                
                if source_size != dest_size:
                    return False, (
                        f"Size mismatch for {rel_path}: "
                        f"source={source_size}, dest={dest_size}"
                    )
                
                # For large files, just check size
                # For smaller files (< 100MB), verify checksums
                if source_size < 100 * 1024 * 1024:
                    source_hash = self._calculate_checksum(source_file)
                    dest_hash = self._calculate_checksum(dest_file)
                    
                    if source_hash != dest_hash:
                        return False, f"Checksum mismatch for {rel_path}"
            
            return True, None
            
        except Exception as e:
            return False, f"Verification error: {e}"
    
    def _get_all_files(self, directory: Path) -> list[Path]:
        """
        Get all files in directory recursively.
        
        Args:
            directory: Directory to scan
            
        Returns:
            List of file paths
        """
        files = []
        for root, dirs, filenames in os.walk(directory):
            for filename in filenames:
                files.append(Path(root) / filename)
        return sorted(files)
    
    def _calculate_checksum(self, file_path: Path, algorithm: str = 'md5') -> str:
        """
        Calculate checksum of a file.
        
        Args:
            file_path: Path to file
            algorithm: Hash algorithm to use
            
        Returns:
            Checksum as hex string
        """
        hash_obj = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            # Read in chunks for memory efficiency
            for chunk in iter(lambda: f.read(8192), b''):
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
    
    def get_archive_size(self) -> int:
        """
        Get total size of all archives.
        
        Returns:
            Size in bytes
        """
        total_size = 0
        for root, dirs, files in os.walk(self.archive_root):
            for filename in files:
                file_path = Path(root) / filename
                total_size += file_path.stat().st_size
        return total_size
    
    def list_archives(self) -> list[Path]:
        """
        List all archived albums.
        
        Returns:
            List of archive directory paths
        """
        archives = []
        if self.archive_root.exists():
            archives = [
                item for item in self.archive_root.iterdir()
                if item.is_dir()
            ]
        return sorted(archives)
    
    def delete_archive(self, archive_path: Path) -> tuple[bool, Optional[str]]:
        """
        Delete an archive.
        
        Args:
            archive_path: Path to archive to delete
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            if not archive_path.exists():
                return False, "Archive does not exist"
            
            if not archive_path.is_relative_to(self.archive_root):
                return False, "Archive path is not within archive root"
            
            shutil.rmtree(archive_path)
            return True, None
            
        except Exception as e:
            return False, f"Error deleting archive: {e}"

