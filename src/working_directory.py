"""
Working directory manager for conversion process.
Manages temporary working directories for atomic album processing.
"""

import shutil
import os
from pathlib import Path
from typing import Optional, Tuple, List
from datetime import datetime
import hashlib


class WorkingDirectoryManager:
    """
    Manages working directories for album conversion.
    
    Creates _source and _processed directories for each album,
    enabling atomic operations and precise resume capabilities.
    """
    
    def __init__(self, working_root: Path, verify_copies: bool = True):
        """
        Initialize working directory manager.
        
        Args:
            working_root: Root directory for all working directories
            verify_copies: Whether to verify copied files
        """
        self.working_root = Path(working_root)
        self.verify_copies = verify_copies
        
        # Create working root if it doesn't exist
        self.working_root.mkdir(parents=True, exist_ok=True)
    
    def create_working_dirs(
        self,
        album_path: Path,
        album_name: Optional[str] = None
    ) -> Tuple[bool, Optional[Path], Optional[Path], Optional[str]]:
        """
        Create working directories for an album.
        
        Args:
            album_path: Path to source album
            album_name: Optional album name (defaults to album_path.name)
            
        Returns:
            Tuple of (success, source_dir, processed_dir, error_message)
        """
        try:
            if not album_name:
                album_name = album_path.name
            
            # Create unique directory names with timestamp to avoid conflicts
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = self._sanitize_name(album_name)
            
            source_dir = self.working_root / f"{safe_name}_{timestamp}_source"
            processed_dir = self.working_root / f"{safe_name}_{timestamp}_processed"
            
            # Ensure they don't already exist
            if source_dir.exists() or processed_dir.exists():
                return False, None, None, "Working directories already exist"
            
            # Create the directories
            source_dir.mkdir(parents=True, exist_ok=False)
            processed_dir.mkdir(parents=True, exist_ok=False)
            
            return True, source_dir, processed_dir, None
            
        except Exception as e:
            return False, None, None, f"Error creating working directories: {e}"
    
    def copy_to_source(
        self,
        album_path: Path,
        source_dir: Path
    ) -> Tuple[bool, Optional[str]]:
        """
        Copy album contents to source working directory.
        
        Args:
            album_path: Original album path
            source_dir: Destination source working directory
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            if not album_path.exists():
                return False, f"Source album not found: {album_path}"
            
            if not source_dir.exists():
                return False, f"Source working directory not found: {source_dir}"
            
            # Copy all contents from album_path to source_dir
            # Using copytree with dirs_exist_ok since we already created the directory
            for item in album_path.iterdir():
                dest_item = source_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest_item, symlinks=False, copy_function=shutil.copy2)
                else:
                    shutil.copy2(item, dest_item)
            
            # Verify if requested
            if self.verify_copies:
                success, error = self._verify_copy(album_path, source_dir)
                if not success:
                    return False, f"Verification failed: {error}"
            
            return True, None
            
        except Exception as e:
            return False, f"Error copying to source: {e}"
    
    def create_processed_structure(
        self,
        album_path: Path,
        processed_dir: Path,
        copy_non_music: bool = True,
        music_extensions: Optional[List[str]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Create directory structure in processed dir (without music files).
        
        Args:
            album_path: Original album path
            processed_dir: Destination processed working directory
            copy_non_music: Whether to copy non-music files
            music_extensions: List of music file extensions to skip
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            if not album_path.exists():
                return False, f"Source album not found: {album_path}"
            
            if not processed_dir.exists():
                return False, f"Processed working directory not found: {processed_dir}"
            
            if music_extensions is None:
                music_extensions = ['.dsf', '.dff', '.iso', '.flac', '.dsd']
            
            # Normalize extensions to lowercase
            music_extensions = [ext.lower() for ext in music_extensions]
            
            # Walk through album_path and replicate structure
            for root, dirs, files in os.walk(album_path):
                # Calculate relative path from album_path
                rel_path = Path(root).relative_to(album_path)
                
                # Create corresponding directories in processed_dir
                for dir_name in dirs:
                    dest_dir = processed_dir / rel_path / dir_name
                    dest_dir.mkdir(parents=True, exist_ok=True)
                
                # Copy non-music files if requested
                if copy_non_music:
                    for file_name in files:
                        file_path = Path(root) / file_name
                        
                        # Skip music files
                        if file_path.suffix.lower() in music_extensions:
                            continue
                        
                        dest_file = processed_dir / rel_path / file_name
                        shutil.copy2(file_path, dest_file)
            
            return True, None
            
        except Exception as e:
            return False, f"Error creating processed structure: {e}"
    
    def get_converted_tracks(
        self,
        processed_dir: Path,
        extension: str = '.flac'
    ) -> List[Path]:
        """
        Get list of already-converted tracks in processed directory.
        
        Args:
            processed_dir: Processed working directory
            extension: Expected file extension
            
        Returns:
            List of converted track paths
        """
        if not processed_dir.exists():
            return []
        
        # Find all files with the specified extension
        return sorted(processed_dir.rglob(f'*{extension}'))
    
    def cleanup_working_dirs(
        self,
        source_dir: Optional[Path],
        processed_dir: Optional[Path]
    ) -> Tuple[bool, Optional[str]]:
        """
        Remove working directories.
        
        Args:
            source_dir: Source working directory (can be None)
            processed_dir: Processed working directory (can be None)
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            errors = []
            
            if source_dir and source_dir.exists():
                try:
                    shutil.rmtree(source_dir)
                except Exception as e:
                    errors.append(f"Failed to remove source dir: {e}")
            
            if processed_dir and processed_dir.exists():
                try:
                    shutil.rmtree(processed_dir)
                except Exception as e:
                    errors.append(f"Failed to remove processed dir: {e}")
            
            if errors:
                return False, "; ".join(errors)
            
            return True, None
            
        except Exception as e:
            return False, f"Error cleaning up: {e}"
    
    def move_to_archive(
        self,
        source_dir: Path,
        archive_path: Path
    ) -> Tuple[bool, Optional[str]]:
        """
        Move source working directory to archive location.
        
        Args:
            source_dir: Source working directory
            archive_path: Final archive path (without _source suffix)
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            if not source_dir.exists():
                return False, f"Source directory not found: {source_dir}"
            
            # Check if archive already exists
            if archive_path.exists():
                return False, f"Archive already exists: {archive_path}"
            
            # Create parent directory
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Move (rename) the directory
            shutil.move(str(source_dir), str(archive_path))
            
            return True, None
            
        except Exception as e:
            return False, f"Error moving to archive: {e}"
    
    def copy_to_archive(
        self,
        source_dir: Path,
        archive_path: Path
    ) -> Tuple[bool, Optional[str]]:
        """
        Copy source working directory to archive location (keeps source intact).
        
        Args:
            source_dir: Source working directory
            archive_path: Final archive path
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            if not source_dir.exists():
                return False, f"Source directory not found: {source_dir}"
            
            # Check if archive already exists
            if archive_path.exists():
                return False, f"Archive already exists: {archive_path}"
            
            # Create parent directory
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy the directory tree
            shutil.copytree(source_dir, archive_path, symlinks=False, copy_function=shutil.copy2)
            
            return True, None
            
        except Exception as e:
            return False, f"Error copying to archive: {e}"
    
    def move_to_output(
        self,
        processed_dir: Path,
        output_path: Path
    ) -> Tuple[bool, Optional[str]]:
        """
        Move processed working directory to output location.
        
        Args:
            processed_dir: Processed working directory
            output_path: Final output path (without _processed suffix)
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            if not processed_dir.exists():
                return False, f"Processed directory not found: {processed_dir}"
            
            # Check if output already exists
            if output_path.exists():
                return False, f"Output already exists: {output_path}"
            
            # Create parent directory
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Move (rename) the directory
            shutil.move(str(processed_dir), str(output_path))
            
            return True, None
            
        except Exception as e:
            return False, f"Error moving to output: {e}"
    
    def copy_to_output(
        self,
        processed_dir: Path,
        output_path: Path
    ) -> Tuple[bool, Optional[str]]:
        """
        Copy processed working directory to output location (keeps processed intact).
        
        Args:
            processed_dir: Processed working directory
            output_path: Final output path
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            if not processed_dir.exists():
                return False, f"Processed directory not found: {processed_dir}"
            
            # Check if output already exists
            if output_path.exists():
                return False, f"Output already exists: {output_path}"
            
            # Create parent directory
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy the directory tree
            shutil.copytree(processed_dir, output_path, symlinks=False, copy_function=shutil.copy2)
            
            return True, None
            
        except Exception as e:
            return False, f"Error copying to output: {e}"
    
    def list_working_directories(self) -> List[Tuple[Path, Path]]:
        """
        List all working directory pairs in the working root.
        
        Returns:
            List of (source_dir, processed_dir) tuples
        """
        pairs = []
        
        if not self.working_root.exists():
            return pairs
        
        # Find all _source directories
        source_dirs = [d for d in self.working_root.iterdir() 
                      if d.is_dir() and d.name.endswith('_source')]
        
        for source_dir in source_dirs:
            # Find matching _processed directory
            base_name = source_dir.name[:-7]  # Remove '_source'
            processed_dir = self.working_root / f"{base_name}_processed"
            
            if processed_dir.exists():
                pairs.append((source_dir, processed_dir))
        
        return pairs
    
    def get_disk_space(self, path: Path) -> Tuple[int, int]:
        """
        Get available and total disk space for a path.
        
        Args:
            path: Path to check
            
        Returns:
            Tuple of (available_bytes, total_bytes)
        """
        stat = shutil.disk_usage(path)
        return stat.free, stat.total
    
    def estimate_required_space(self, album_path: Path) -> int:
        """
        Estimate space required for processing an album.
        
        For regular files: 3x (source copy + processing buffer)
        For ISO files: 5x (source + extraction + conversion + temp buffers)
        
        ISO workflow requires more space due to:
        1. Copy ISO to working_source (1x)
        2. Extract ISO to DSF in temp (1x+, can be larger)
        3. Convert DSF to FLAC in working_processed (0.5x)
        4. Archive copy (1x)
        5. Temporary buffers and overhead (1x)
        
        Args:
            album_path: Path to album
            
        Returns:
            Estimated bytes required
        """
        if not album_path.exists():
            return 0
        
        total_size = 0
        has_iso_files = False
        
        for root, dirs, files in os.walk(album_path):
            for filename in files:
                file_path = Path(root) / filename
                try:
                    total_size += file_path.stat().st_size
                    # Check if this is an ISO file
                    if file_path.suffix.lower() == '.iso':
                        has_iso_files = True
                except:
                    pass
        
        # Use higher multiplier for ISO files due to extraction overhead
        multiplier = 5 if has_iso_files else 3
        return total_size * multiplier
    
    def check_disk_space(
        self,
        album_path: Path,
        safety_margin_gb: float = 5.0
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if sufficient disk space is available.
        
        Args:
            album_path: Path to album to process
            safety_margin_gb: Additional safety margin in GB
            
        Returns:
            Tuple of (sufficient, error_message)
        """
        try:
            required = self.estimate_required_space(album_path)
            required += int(safety_margin_gb * 1024 * 1024 * 1024)
            
            available, _ = self.get_disk_space(self.working_root)
            
            if available < required:
                required_gb = required / (1024 ** 3)
                available_gb = available / (1024 ** 3)
                return False, (
                    f"Insufficient disk space. "
                    f"Required: {required_gb:.2f} GB, "
                    f"Available: {available_gb:.2f} GB"
                )
            
            return True, None
            
        except Exception as e:
            return False, f"Error checking disk space: {e}"
    
    def _verify_copy(
        self,
        source_dir: Path,
        dest_dir: Path
    ) -> Tuple[bool, Optional[str]]:
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
            
            return True, None
            
        except Exception as e:
            return False, f"Verification error: {e}"
    
    def _get_all_files(self, directory: Path) -> List[Path]:
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
    
    def _sanitize_name(self, name: str) -> str:
        """
        Sanitize name for use as directory name.
        
        Args:
            name: Name to sanitize
            
        Returns:
            Sanitized name
        """
        # Replace problematic characters
        sanitized = name.replace('/', '_').replace('\\', '_')
        sanitized = sanitized.replace(':', '_').replace('*', '_')
        sanitized = sanitized.replace('?', '_').replace('"', '_')
        sanitized = sanitized.replace('<', '_').replace('>', '_')
        sanitized = sanitized.replace('|', '_')
        
        # Limit length
        if len(sanitized) > 200:
            sanitized = sanitized[:200]
        
        return sanitized

