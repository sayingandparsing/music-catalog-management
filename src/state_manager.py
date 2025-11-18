"""
State management for conversion process.
Handles persistence, crash recovery, and pause/resume functionality.

This module complements the database by maintaining lightweight JSON state
for active conversion sessions, while the database provides long-term storage
and historical tracking.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, asdict, field
from enum import Enum


class AlbumStatus(Enum):
    """Status of album processing."""
    PENDING = "pending"
    ARCHIVING = "archiving"
    CONVERTING = "converting"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class FileConversionState:
    """State of individual file conversion."""
    source_path: str
    output_path: str
    status: str  # 'pending', 'converting', 'completed', 'failed'
    attempts: int = 0
    error_message: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class AlbumConversionState:
    """State of album conversion."""
    album_path: str
    album_name: str
    status: str  # AlbumStatus value
    archive_path: Optional[str] = None
    files: List[FileConversionState] = field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ConversionSession:
    """Overall conversion session state."""
    session_id: str
    input_dir: str
    output_dir: str
    archive_dir: str
    conversion_mode: str
    sample_rate: int
    bit_depth: int
    enrich_metadata: bool
    started_at: str
    completed_at: Optional[str] = None
    albums: List[AlbumConversionState] = field(default_factory=list)
    paused: bool = False


class StateManager:
    """
    Manages conversion state for crash recovery and resume.
    
    The StateManager maintains lightweight JSON state files for active conversion
    sessions. This complements the database by providing:
    - Quick resume capability after interruptions
    - Minimal overhead during active conversions
    - Human-readable state files for debugging
    
    The database provides:
    - Long-term album and metadata storage
    - Historical processing records
    - Advanced querying capabilities
    """
    
    STATE_DIR = Path(".state")
    STATE_FILE = "conversion_state.json"
    PAUSE_SIGNAL_FILE = "PAUSE"
    
    def __init__(self, state_dir: Optional[Path] = None, database=None):
        """
        Initialize state manager.
        
        Args:
            state_dir: Directory for state files (default: .state)
            database: Optional MusicDatabase instance for coordination
        """
        self.state_dir = Path(state_dir) if state_dir else self.STATE_DIR
        self.state_file = self.state_dir / self.STATE_FILE
        self.pause_signal_file = self.state_dir / self.PAUSE_SIGNAL_FILE
        self.database = database
        
        # Create state directory
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        self.session: Optional[ConversionSession] = None
    
    def create_session(
        self,
        input_dir: Path,
        output_dir: Path,
        archive_dir: Path,
        conversion_mode: str,
        sample_rate: int,
        bit_depth: int,
        enrich_metadata: bool
    ) -> ConversionSession:
        """
        Create a new conversion session.
        
        Args:
            input_dir: Input directory
            output_dir: Output directory
            archive_dir: Archive directory
            conversion_mode: Conversion mode
            sample_rate: Sample rate
            bit_depth: Bit depth
            enrich_metadata: Whether to enrich metadata
            
        Returns:
            ConversionSession object
        """
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self.session = ConversionSession(
            session_id=session_id,
            input_dir=str(input_dir),
            output_dir=str(output_dir),
            archive_dir=str(archive_dir),
            conversion_mode=conversion_mode,
            sample_rate=sample_rate,
            bit_depth=bit_depth,
            enrich_metadata=enrich_metadata,
            started_at=datetime.now().isoformat()
        )
        
        self.save_state()
        return self.session
    
    def load_session(self) -> Optional[ConversionSession]:
        """
        Load existing session from state file.
        
        Returns:
            ConversionSession object or None if no session exists
        """
        if not self.state_file.exists():
            return None
        
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
            
            # Reconstruct session
            albums = [
                AlbumConversionState(
                    album_path=a['album_path'],
                    album_name=a['album_name'],
                    status=a['status'],
                    archive_path=a.get('archive_path'),
                    files=[
                        FileConversionState(**f) for f in a.get('files', [])
                    ],
                    started_at=a.get('started_at'),
                    completed_at=a.get('completed_at'),
                    error_message=a.get('error_message')
                )
                for a in data.get('albums', [])
            ]
            
            self.session = ConversionSession(
                session_id=data['session_id'],
                input_dir=data['input_dir'],
                output_dir=data['output_dir'],
                archive_dir=data['archive_dir'],
                conversion_mode=data['conversion_mode'],
                sample_rate=data['sample_rate'],
                bit_depth=data['bit_depth'],
                enrich_metadata=data['enrich_metadata'],
                started_at=data['started_at'],
                completed_at=data.get('completed_at'),
                albums=albums,
                paused=data.get('paused', False)
            )
            
            return self.session
            
        except Exception as e:
            print(f"Error loading session: {e}")
            return None
    
    def save_state(self):
        """Save current session state to file."""
        if not self.session:
            return
        
        # Convert to dict
        data = {
            'session_id': self.session.session_id,
            'input_dir': self.session.input_dir,
            'output_dir': self.session.output_dir,
            'archive_dir': self.session.archive_dir,
            'conversion_mode': self.session.conversion_mode,
            'sample_rate': self.session.sample_rate,
            'bit_depth': self.session.bit_depth,
            'enrich_metadata': self.session.enrich_metadata,
            'started_at': self.session.started_at,
            'completed_at': self.session.completed_at,
            'paused': self.session.paused,
            'albums': [
                {
                    'album_path': a.album_path,
                    'album_name': a.album_name,
                    'status': a.status,
                    'archive_path': a.archive_path,
                    'started_at': a.started_at,
                    'completed_at': a.completed_at,
                    'error_message': a.error_message,
                    'files': [
                        {
                            'source_path': f.source_path,
                            'output_path': f.output_path,
                            'status': f.status,
                            'attempts': f.attempts,
                            'error_message': f.error_message,
                            'completed_at': f.completed_at
                        }
                        for f in a.files
                    ]
                }
                for a in self.session.albums
            ]
        }
        
        # Write to file (atomic write)
        temp_file = self.state_file.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Atomic replace
        temp_file.replace(self.state_file)
    
    def add_album(
        self,
        album_path: Path,
        album_name: str,
        music_files: List[tuple[Path, Path]]
    ):
        """
        Add album to session state.
        
        Args:
            album_path: Path to album
            album_name: Album name
            music_files: List of (source_path, output_path) tuples
        """
        if not self.session:
            raise RuntimeError("No active session")
        
        files = [
            FileConversionState(
                source_path=str(source),
                output_path=str(output),
                status='pending'
            )
            for source, output in music_files
        ]
        
        album_state = AlbumConversionState(
            album_path=str(album_path),
            album_name=album_name,
            status=AlbumStatus.PENDING.value,
            files=files,
            started_at=datetime.now().isoformat()
        )
        
        self.session.albums.append(album_state)
        self.save_state()
    
    def update_album_status(
        self,
        album_path: Path,
        status: AlbumStatus,
        archive_path: Optional[Path] = None,
        error_message: Optional[str] = None
    ):
        """
        Update album status.
        
        Args:
            album_path: Path to album
            status: New status
            archive_path: Archive path (optional)
            error_message: Error message if failed (optional)
        """
        if not self.session:
            return
        
        for album in self.session.albums:
            if album.album_path == str(album_path):
                album.status = status.value
                if archive_path:
                    album.archive_path = str(archive_path)
                if error_message:
                    album.error_message = error_message
                if status in [AlbumStatus.COMPLETED, AlbumStatus.FAILED, AlbumStatus.SKIPPED]:
                    album.completed_at = datetime.now().isoformat()
                break
        
        self.save_state()
    
    def update_file_status(
        self,
        album_path: Path,
        file_path: Path,
        status: str,
        error_message: Optional[str] = None
    ):
        """
        Update file conversion status.
        
        Args:
            album_path: Path to album
            file_path: Path to file
            status: New status
            error_message: Error message if failed (optional)
        """
        if not self.session:
            return
        
        for album in self.session.albums:
            if album.album_path == str(album_path):
                for file_state in album.files:
                    if file_state.source_path == str(file_path):
                        file_state.status = status
                        if status == 'converting':
                            file_state.attempts += 1
                        if error_message:
                            file_state.error_message = error_message
                        if status in ['completed', 'failed']:
                            file_state.completed_at = datetime.now().isoformat()
                        break
                break
        
        self.save_state()
    
    def get_pending_albums(self) -> List[AlbumConversionState]:
        """
        Get albums that haven't been processed yet.
        
        Returns:
            List of pending album states
        """
        if not self.session:
            return []
        
        return [
            album for album in self.session.albums
            if album.status in [AlbumStatus.PENDING.value, AlbumStatus.FAILED.value]
        ]
    
    def check_pause_signal(self) -> bool:
        """
        Check if pause signal file exists.
        
        Returns:
            True if should pause
        """
        return self.pause_signal_file.exists()
    
    def create_pause_signal(self):
        """Create pause signal file."""
        self.pause_signal_file.touch()
        if self.session:
            self.session.paused = True
            self.save_state()
    
    def clear_pause_signal(self):
        """Remove pause signal file."""
        if self.pause_signal_file.exists():
            self.pause_signal_file.unlink()
        if self.session:
            self.session.paused = False
            self.save_state()
    
    def mark_completed(self):
        """
        Mark session as completed.
        
        Note: Album-specific completion is tracked in the database via
        processing_history records. This marks the overall session as complete.
        """
        if self.session:
            self.session.completed_at = datetime.now().isoformat()
            self.save_state()
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get conversion statistics.
        
        Returns:
            Dictionary with statistics
        """
        if not self.session:
            return {}
        
        total_albums = len(self.session.albums)
        completed = sum(
            1 for a in self.session.albums
            if a.status == AlbumStatus.COMPLETED.value
        )
        failed = sum(
            1 for a in self.session.albums
            if a.status == AlbumStatus.FAILED.value
        )
        skipped = sum(
            1 for a in self.session.albums
            if a.status == AlbumStatus.SKIPPED.value
        )
        
        total_files = sum(len(a.files) for a in self.session.albums)
        files_completed = sum(
            sum(1 for f in a.files if f.status == 'completed')
            for a in self.session.albums
        )
        files_failed = sum(
            sum(1 for f in a.files if f.status == 'failed')
            for a in self.session.albums
        )
        
        return {
            'albums_total': total_albums,
            'albums_completed': completed,
            'albums_failed': failed,
            'albums_skipped': skipped,
            'albums_pending': total_albums - completed - failed - skipped,
            'files_total': total_files,
            'files_completed': files_completed,
            'files_failed': files_failed,
            'files_pending': total_files - files_completed - files_failed
        }
    
    def clear_state(self):
        """
        Clear state file.
        
        Note: This only clears the session state file. Album data persists
        in the database for long-term tracking and deduplication.
        """
        if self.state_file.exists():
            self.state_file.unlink()
        self.session = None
    
    def sync_with_database(self):
        """
        Synchronize session state with database records.
        
        This method can be used to update the session state based on
        database records, useful for resume operations.
        """
        if not self.database or not self.session:
            return
        
        # Update album statuses based on database processing history
        for album in self.session.albums:
            # Check if album has successful conversion in database
            history = self.database.get_processing_history(
                album.album_path if hasattr(album, 'album_path') else album.album_name
            )
            
            # Update status based on most recent successful operation
            convert_history = [
                h for h in history
                if h.get('operation_type') == 'convert'
            ]
            
            if convert_history:
                latest = convert_history[0]  # Already sorted by date DESC
                if latest.get('status') == 'success' and album.status != AlbumStatus.COMPLETED.value:
                    album.status = AlbumStatus.COMPLETED.value
                    album.completed_at = latest.get('processed_at')
        
        self.save_state()

