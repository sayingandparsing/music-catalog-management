"""
Directory scanner for finding DSD music files.
Identifies albums and organizes files for conversion.
"""

import os
from pathlib import Path
from typing import List, Set, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class MusicFile:
    """Represents a music file to be converted."""
    path: Path
    relative_path: Path  # Relative to album root
    extension: str
    size: int = 0
    
    def __post_init__(self):
        if self.path.exists():
            self.size = self.path.stat().st_size


@dataclass
class NonMusicFile:
    """Represents a non-music file to be copied."""
    path: Path
    relative_path: Path  # Relative to album root
    extension: str


@dataclass
class Album:
    """Represents an album with music and non-music files."""
    root_path: Path
    name: str
    music_files: List[MusicFile] = field(default_factory=list)
    non_music_files: List[NonMusicFile] = field(default_factory=list)
    subdirectories: List[str] = field(default_factory=list)
    
    @property
    def total_size(self) -> int:
        """Total size of music files in bytes."""
        return sum(f.size for f in self.music_files)
    
    @property
    def file_count(self) -> int:
        """Number of music files."""
        return len(self.music_files)
    
    def __repr__(self) -> str:
        return (
            f"Album(name={self.name}, "
            f"files={self.file_count}, "
            f"size={self.total_size / (1024**3):.2f}GB)"
        )


class DirectoryScanner:
    """
    Scans directories for DSD music files.
    Identifies album boundaries and organizes files.
    """
    
    def __init__(
        self,
        music_extensions: Optional[List[str]] = None,
        copy_extensions: Optional[List[str]] = None
    ):
        """
        Initialize scanner.
        
        Args:
            music_extensions: File extensions for music files (e.g., ['.iso', '.dsf'])
            copy_extensions: File extensions for non-music files to copy
        """
        self.music_extensions = set(
            ext.lower() for ext in (music_extensions or ['.iso', '.dsf', '.dff'])
        )
        self.copy_extensions = set(
            ext.lower() for ext in (copy_extensions or [
                '.jpg', '.jpeg', '.png', '.pdf', '.txt', 
                '.log', '.cue', '.m3u', '.nfo'
            ])
        )
    
    def scan(self, root_dir: Path) -> List[Album]:
        """
        Scan directory for albums.
        
        Args:
            root_dir: Root directory to scan
            
        Returns:
            List of Album objects
        """
        if not root_dir.exists():
            raise FileNotFoundError(f"Directory not found: {root_dir}")
        
        if not root_dir.is_dir():
            raise NotADirectoryError(f"Not a directory: {root_dir}")
        
        albums = []
        
        # Check if root_dir itself is an album
        if self._is_album(root_dir):
            album = self._scan_album(root_dir, root_dir)
            if album.file_count > 0:
                albums.append(album)
        else:
            # Scan subdirectories for albums
            albums.extend(self._scan_for_albums(root_dir))
        
        return albums
    
    def _scan_for_albums(self, root_dir: Path) -> List[Album]:
        """
        Recursively scan for albums in subdirectories.
        
        Args:
            root_dir: Root directory to scan
            
        Returns:
            List of Album objects
        """
        albums = []
        
        # Walk through directory tree
        for dirpath, dirnames, filenames in os.walk(root_dir):
            current_path = Path(dirpath)
            
            # Check if current directory contains music files
            has_music = any(
                Path(dirpath, f).suffix.lower() in self.music_extensions
                for f in filenames
            )
            
            if has_music:
                # This is an album directory
                album = self._scan_album(current_path, root_dir)
                if album.file_count > 0:
                    albums.append(album)
                
                # Don't descend into this directory's subdirectories
                # as they're part of this album
                dirnames.clear()
        
        return albums
    
    def _is_album(self, directory: Path) -> bool:
        """
        Check if a directory is an album (contains music files).
        
        Args:
            directory: Directory to check
            
        Returns:
            True if directory or its subdirectories contain music files
        """
        for root, dirs, files in os.walk(directory):
            for file in files:
                if Path(file).suffix.lower() in self.music_extensions:
                    return True
        return False
    
    def _scan_album(self, album_path: Path, root_dir: Path) -> Album:
        """
        Scan a single album directory.
        
        Args:
            album_path: Path to album directory
            root_dir: Root directory for relative path calculation
            
        Returns:
            Album object
        """
        music_files = []
        non_music_files = []
        subdirs = set()
        
        # Walk through album directory and subdirectories
        for dirpath, dirnames, filenames in os.walk(album_path):
            current_path = Path(dirpath)
            
            # Track subdirectories
            if current_path != album_path:
                relative_dir = current_path.relative_to(album_path)
                subdirs.add(str(relative_dir.parts[0]))
            
            # Process files
            for filename in filenames:
                file_path = current_path / filename
                extension = file_path.suffix.lower()
                relative_path = file_path.relative_to(album_path)
                
                if extension in self.music_extensions:
                    music_files.append(MusicFile(
                        path=file_path,
                        relative_path=relative_path,
                        extension=extension
                    ))
                elif extension in self.copy_extensions or extension == '':
                    # Include extensionless files (like README)
                    non_music_files.append(NonMusicFile(
                        path=file_path,
                        relative_path=relative_path,
                        extension=extension
                    ))
        
        return Album(
            root_path=album_path,
            name=album_path.name,
            music_files=sorted(music_files, key=lambda x: str(x.path)),
            non_music_files=sorted(non_music_files, key=lambda x: str(x.path)),
            subdirectories=sorted(list(subdirs))
        )
    
    def get_statistics(self, albums: List[Album]) -> Dict:
        """
        Get statistics about scanned albums.
        
        Args:
            albums: List of Album objects
            
        Returns:
            Dictionary with statistics
        """
        total_files = sum(album.file_count for album in albums)
        total_size = sum(album.total_size for album in albums)
        
        extensions = {}
        for album in albums:
            for file in album.music_files:
                ext = file.extension
                extensions[ext] = extensions.get(ext, 0) + 1
        
        return {
            'album_count': len(albums),
            'total_files': total_files,
            'total_size_bytes': total_size,
            'total_size_gb': total_size / (1024**3),
            'extensions': extensions
        }
    
    def print_summary(self, albums: List[Album]):
        """
        Print a summary of scanned albums.
        
        Args:
            albums: List of Album objects
        """
        stats = self.get_statistics(albums)
        
        print(f"\nScan Summary:")
        print(f"  Albums found:    {stats['album_count']}")
        print(f"  Total files:     {stats['total_files']}")
        print(f"  Total size:      {stats['total_size_gb']:.2f} GB")
        print(f"\n  Files by type:")
        for ext, count in sorted(stats['extensions'].items()):
            print(f"    {ext:8s}: {count}")
        print()

