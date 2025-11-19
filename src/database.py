"""
Database management for music catalog.
Uses DuckDB for storing album metadata, tracks, and processing history.
"""

import duckdb
import uuid
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from contextlib import contextmanager


class MusicDatabase:
    """
    Manages the DuckDB database for music catalog tracking.
    """
    
    def __init__(self, db_path: Path):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to DuckDB database file
        """
        self.db_path = Path(db_path)
        self.conn = None
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database connection and create tables if needed."""
        self.conn = duckdb.connect(str(self.db_path))
        self._create_tables()
    
    def _create_tables(self):
        """Create database tables if they don't exist."""
        # Albums table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS albums (
                album_id VARCHAR PRIMARY KEY,
                album_name VARCHAR,
                artist VARCHAR,
                release_year INTEGER,
                recording_year INTEGER,
                remaster_year INTEGER,
                label VARCHAR,
                label_original VARCHAR,
                release_series VARCHAR,
                catalog_number VARCHAR,
                genre VARCHAR,
                mastering_engineer VARCHAR,
                recording_engineer VARCHAR,
                recording_studio VARCHAR,
                allmusic_rating DECIMAL(3, 1),
                source_path VARCHAR,
                archive_path VARCHAR,
                playback_path VARCHAR,
                audio_files_checksum VARCHAR,
                processed_at TIMESTAMP,
                updated_at TIMESTAMP,
                conversion_mode VARCHAR,
                sample_rate INTEGER,
                bit_depth INTEGER,
                processing_stage VARCHAR,
                working_source_path VARCHAR,
                working_processed_path VARCHAR
            )
        """)
        
        # Tracks table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tracks (
                track_id VARCHAR PRIMARY KEY,
                album_id VARCHAR,
                track_number INTEGER,
                title VARCHAR,
                duration_seconds DECIMAL(10, 2),
                file_path VARCHAR,
                file_size BIGINT,
                file_format VARCHAR,
                genre VARCHAR,
                dynamic_range_crest DECIMAL(6, 2),
                dynamic_range_r128 DECIMAL(6, 2),
                musicians JSON,
                processed_at TIMESTAMP,
                FOREIGN KEY (album_id) REFERENCES albums(album_id)
            )
        """)
        
        # Metadata candidates table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS metadata_candidates (
                candidate_id VARCHAR PRIMARY KEY,
                album_id VARCHAR,
                source VARCHAR,
                source_id VARCHAR,
                rank INTEGER,
                confidence_score DECIMAL(5, 4),
                metadata_json JSON,
                fetched_at TIMESTAMP,
                FOREIGN KEY (album_id) REFERENCES albums(album_id)
            )
        """)
        
        # Processing history table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS processing_history (
                history_id VARCHAR PRIMARY KEY,
                album_id VARCHAR,
                operation_type VARCHAR,
                status VARCHAR,
                error_message VARCHAR,
                duration_seconds DECIMAL(10, 2),
                processed_at TIMESTAMP,
                working_source_path VARCHAR,
                working_processed_path VARCHAR,
                FOREIGN KEY (album_id) REFERENCES albums(album_id)
            )
        """)
        
        # Create indices for common queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_albums_checksum 
            ON albums(audio_files_checksum)
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_albums_source_path 
            ON albums(source_path)
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tracks_album_id 
            ON tracks(album_id)
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_metadata_candidates_album_id 
            ON metadata_candidates(album_id)
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_processing_history_album_id 
            ON processing_history(album_id)
        """)
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    # Album operations
    
    def create_album(
        self,
        album_id: str,
        album_name: str,
        source_path: str,
        audio_files_checksum: str,
        **kwargs
    ) -> bool:
        """
        Create a new album record.
        
        Args:
            album_id: Unique album ID (UUID)
            album_name: Album name
            source_path: Original source path
            audio_files_checksum: SHA256 checksum of audio files
            **kwargs: Additional album fields
            
        Returns:
            True if successful
        """
        try:
            now = datetime.now()
            
            self.conn.execute("""
                INSERT INTO albums (
                    album_id, album_name, source_path, audio_files_checksum,
                    processed_at, updated_at,
                    artist, release_year, recording_year, remaster_year,
                    label, label_original, release_series, catalog_number, genre,
                    mastering_engineer, recording_engineer, recording_studio,
                    allmusic_rating, archive_path, playback_path,
                    conversion_mode, sample_rate, bit_depth,
                    processing_stage, working_source_path, working_processed_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                album_id, album_name, source_path, audio_files_checksum,
                now, now,
                kwargs.get('artist'),
                kwargs.get('release_year'),
                kwargs.get('recording_year'),
                kwargs.get('remaster_year'),
                kwargs.get('label'),
                kwargs.get('label_original'),
                kwargs.get('release_series'),
                kwargs.get('catalog_number'),
                kwargs.get('genre'),
                kwargs.get('mastering_engineer'),
                kwargs.get('recording_engineer'),
                kwargs.get('recording_studio'),
                kwargs.get('allmusic_rating'),
                kwargs.get('archive_path'),
                kwargs.get('playback_path'),
                kwargs.get('conversion_mode'),
                kwargs.get('sample_rate'),
                kwargs.get('bit_depth'),
                kwargs.get('processing_stage'),
                kwargs.get('working_source_path'),
                kwargs.get('working_processed_path')
            ])
            
            return True
        except Exception as e:
            print(f"Error creating album: {e}")
            return False
    
    def update_album(self, album_id: str, **kwargs) -> bool:
        """
        Update an existing album record.
        
        Args:
            album_id: Album ID to update
            **kwargs: Fields to update
            
        Returns:
            True if successful
        """
        try:
            # Build dynamic update query
            fields = []
            values = []
            
            for key, value in kwargs.items():
                if value is not None:
                    fields.append(f"{key} = ?")
                    values.append(value)
            
            if not fields:
                return True
            
            # Always update updated_at
            fields.append("updated_at = ?")
            values.append(datetime.now())
            values.append(album_id)
            
            query = f"UPDATE albums SET {', '.join(fields)} WHERE album_id = ?"
            self.conn.execute(query, values)
            
            return True
        except Exception as e:
            print(f"Error updating album: {e}")
            return False
    
    def get_album_by_id(self, album_id: str) -> Optional[Dict[str, Any]]:
        """
        Get album by ID.
        
        Args:
            album_id: Album ID
            
        Returns:
            Album dict or None
        """
        try:
            result = self.conn.execute(
                "SELECT * FROM albums WHERE album_id = ?",
                [album_id]
            ).fetchone()
            
            if result:
                columns = [desc[0] for desc in self.conn.description]
                return dict(zip(columns, result))
            return None
        except Exception as e:
            print(f"Error getting album: {e}")
            return None
    
    def get_album_by_checksum(self, checksum: str) -> Optional[Dict[str, Any]]:
        """
        Get album by audio files checksum.
        
        Args:
            checksum: Audio files checksum
            
        Returns:
            Album dict or None
        """
        try:
            result = self.conn.execute(
                "SELECT * FROM albums WHERE audio_files_checksum = ?",
                [checksum]
            ).fetchone()
            
            if result:
                columns = [desc[0] for desc in self.conn.description]
                return dict(zip(columns, result))
            return None
        except Exception as e:
            print(f"Error getting album by checksum: {e}")
            return None
    
    def get_album_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Get album by source path.
        
        Args:
            path: Source path
            
        Returns:
            Album dict or None
        """
        try:
            result = self.conn.execute(
                "SELECT * FROM albums WHERE source_path = ?",
                [path]
            ).fetchone()
            
            if result:
                columns = [desc[0] for desc in self.conn.description]
                return dict(zip(columns, result))
            return None
        except Exception as e:
            print(f"Error getting album by path: {e}")
            return None
    
    # Track operations
    
    def create_track(
        self,
        track_id: str,
        album_id: str,
        track_number: int,
        title: str,
        file_path: str,
        **kwargs
    ) -> bool:
        """
        Create a new track record.
        
        Args:
            track_id: Unique track ID (UUID)
            album_id: Album ID this track belongs to
            track_number: Track number
            title: Track title
            file_path: File path
            **kwargs: Additional track fields
            
        Returns:
            True if successful
        """
        try:
            now = datetime.now()
            
            # Convert musicians list to JSON string if provided
            musicians = kwargs.get('musicians')
            if musicians and isinstance(musicians, list):
                musicians = json.dumps(musicians)
            
            self.conn.execute("""
                INSERT INTO tracks (
                    track_id, album_id, track_number, title, file_path,
                    duration_seconds, file_size, file_format, genre,
                    dynamic_range_crest, dynamic_range_r128,
                    musicians, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                track_id, album_id, track_number, title, file_path,
                kwargs.get('duration_seconds'),
                kwargs.get('file_size'),
                kwargs.get('file_format'),
                kwargs.get('genre'),
                kwargs.get('dynamic_range_crest'),
                kwargs.get('dynamic_range_r128'),
                musicians,
                now
            ])
            
            return True
        except Exception as e:
            print(f"Error creating track: {e}")
            return False
    
    def get_tracks_by_album(self, album_id: str) -> List[Dict[str, Any]]:
        """
        Get all tracks for an album.
        
        Args:
            album_id: Album ID
            
        Returns:
            List of track dicts
        """
        try:
            results = self.conn.execute(
                "SELECT * FROM tracks WHERE album_id = ? ORDER BY track_number",
                [album_id]
            ).fetchall()
            
            columns = [desc[0] for desc in self.conn.description]
            return [dict(zip(columns, row)) for row in results]
        except Exception as e:
            print(f"Error getting tracks: {e}")
            return []
    
    def update_track(self, track_id: str, **kwargs) -> bool:
        """
        Update an existing track record.
        
        Args:
            track_id: Track ID to update
            **kwargs: Fields to update
            
        Returns:
            True if successful
        """
        try:
            # Build dynamic update query
            fields = []
            values = []
            
            # Handle musicians specially (convert to JSON)
            if 'musicians' in kwargs and kwargs['musicians'] is not None:
                if isinstance(kwargs['musicians'], list):
                    kwargs['musicians'] = json.dumps(kwargs['musicians'])
            
            for key, value in kwargs.items():
                if value is not None:
                    fields.append(f"{key} = ?")
                    values.append(value)
            
            if not fields:
                return True
            
            values.append(track_id)
            
            query = f"UPDATE tracks SET {', '.join(fields)} WHERE track_id = ?"
            self.conn.execute(query, values)
            
            return True
        except Exception as e:
            print(f"Error updating track: {e}")
            return False
    
    # Metadata candidate operations
    
    def create_metadata_candidate(
        self,
        candidate_id: str,
        album_id: str,
        source: str,
        source_id: str,
        rank: int,
        metadata_dict: Dict[str, Any],
        confidence_score: Optional[float] = None
    ) -> bool:
        """
        Create a metadata candidate record.
        
        Args:
            candidate_id: Unique candidate ID (UUID)
            album_id: Album ID
            source: Source name (musicbrainz/discogs)
            source_id: External source ID
            rank: Ranking (1-10, lower is better)
            metadata_dict: Full metadata as dictionary
            confidence_score: Optional confidence score (0-1)
            
        Returns:
            True if successful
        """
        try:
            now = datetime.now()
            metadata_json = json.dumps(metadata_dict)
            
            self.conn.execute("""
                INSERT INTO metadata_candidates (
                    candidate_id, album_id, source, source_id, rank,
                    confidence_score, metadata_json, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                candidate_id, album_id, source, source_id, rank,
                confidence_score, metadata_json, now
            ])
            
            return True
        except Exception as e:
            print(f"Error creating metadata candidate: {e}")
            return False
    
    def get_metadata_candidates(
        self,
        album_id: str,
        source: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get metadata candidates for an album.
        
        Args:
            album_id: Album ID
            source: Optional source filter (musicbrainz/discogs)
            
        Returns:
            List of candidate dicts
        """
        try:
            if source:
                results = self.conn.execute(
                    """SELECT * FROM metadata_candidates 
                       WHERE album_id = ? AND source = ? 
                       ORDER BY rank""",
                    [album_id, source]
                ).fetchall()
            else:
                results = self.conn.execute(
                    """SELECT * FROM metadata_candidates 
                       WHERE album_id = ? 
                       ORDER BY rank""",
                    [album_id]
                ).fetchall()
            
            columns = [desc[0] for desc in self.conn.description]
            candidates = []
            for row in results:
                candidate = dict(zip(columns, row))
                # Parse JSON metadata
                if candidate['metadata_json']:
                    candidate['metadata'] = json.loads(candidate['metadata_json'])
                candidates.append(candidate)
            
            return candidates
        except Exception as e:
            print(f"Error getting metadata candidates: {e}")
            return []
    
    # Processing history operations
    
    def add_processing_history(
        self,
        album_id: str,
        operation_type: str,
        status: str,
        duration_seconds: Optional[float] = None,
        error_message: Optional[str] = None,
        working_source_path: Optional[str] = None,
        working_processed_path: Optional[str] = None
    ) -> bool:
        """
        Add a processing history record.
        
        Args:
            album_id: Album ID
            operation_type: Type of operation (scan/archive/convert/enrich)
            status: Status (success/failed/skipped)
            duration_seconds: Operation duration
            error_message: Error message if failed
            working_source_path: Path to working source directory
            working_processed_path: Path to working processed directory
            
        Returns:
            True if successful
        """
        try:
            history_id = str(uuid.uuid4())
            now = datetime.now()
            
            self.conn.execute("""
                INSERT INTO processing_history (
                    history_id, album_id, operation_type, status,
                    error_message, duration_seconds, processed_at,
                    working_source_path, working_processed_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                history_id, album_id, operation_type, status,
                error_message, duration_seconds, now,
                working_source_path, working_processed_path
            ])
            
            return True
        except Exception as e:
            print(f"Error adding processing history: {e}")
            return False
    
    def get_processing_history(
        self,
        album_id: str,
        operation_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get processing history for an album.
        
        Args:
            album_id: Album ID
            operation_type: Optional operation type filter
            
        Returns:
            List of history dicts
        """
        try:
            if operation_type:
                results = self.conn.execute(
                    """SELECT * FROM processing_history 
                       WHERE album_id = ? AND operation_type = ? 
                       ORDER BY processed_at DESC""",
                    [album_id, operation_type]
                ).fetchall()
            else:
                results = self.conn.execute(
                    """SELECT * FROM processing_history 
                       WHERE album_id = ? 
                       ORDER BY processed_at DESC""",
                    [album_id]
                ).fetchall()
            
            columns = [desc[0] for desc in self.conn.description]
            return [dict(zip(columns, row)) for row in results]
        except Exception as e:
            print(f"Error getting processing history: {e}")
            return []
    
    # Query operations
    
    def get_all_albums(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all albums.
        
        Args:
            limit: Optional limit on number of results
            
        Returns:
            List of album dicts
        """
        try:
            query = "SELECT * FROM albums ORDER BY processed_at DESC"
            if limit:
                query += f" LIMIT {limit}"
            
            results = self.conn.execute(query).fetchall()
            columns = [desc[0] for desc in self.conn.description]
            return [dict(zip(columns, row)) for row in results]
        except Exception as e:
            print(f"Error getting all albums: {e}")
            return []
    
    def search_albums(
        self,
        artist: Optional[str] = None,
        album_name: Optional[str] = None,
        label: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for albums by various criteria.
        
        Args:
            artist: Artist name (partial match)
            album_name: Album name (partial match)
            label: Label name (partial match)
            
        Returns:
            List of matching album dicts
        """
        try:
            conditions = []
            params = []
            
            if artist:
                conditions.append("artist LIKE ?")
                params.append(f"%{artist}%")
            
            if album_name:
                conditions.append("album_name LIKE ?")
                params.append(f"%{album_name}%")
            
            if label:
                conditions.append("label LIKE ?")
                params.append(f"%{label}%")
            
            if not conditions:
                return self.get_all_albums()
            
            query = f"SELECT * FROM albums WHERE {' AND '.join(conditions)}"
            results = self.conn.execute(query, params).fetchall()
            
            columns = [desc[0] for desc in self.conn.description]
            return [dict(zip(columns, row)) for row in results]
        except Exception as e:
            print(f"Error searching albums: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary with statistics
        """
        try:
            stats = {}
            
            # Album count
            result = self.conn.execute("SELECT COUNT(*) FROM albums").fetchone()
            stats['total_albums'] = result[0] if result else 0
            
            # Track count
            result = self.conn.execute("SELECT COUNT(*) FROM tracks").fetchone()
            stats['total_tracks'] = result[0] if result else 0
            
            # Metadata candidates count
            result = self.conn.execute(
                "SELECT COUNT(*) FROM metadata_candidates"
            ).fetchone()
            stats['total_metadata_candidates'] = result[0] if result else 0
            
            # Processing history count
            result = self.conn.execute(
                "SELECT COUNT(*) FROM processing_history"
            ).fetchone()
            stats['total_processing_records'] = result[0] if result else 0
            
            # Artists count
            result = self.conn.execute(
                "SELECT COUNT(DISTINCT artist) FROM albums WHERE artist IS NOT NULL"
            ).fetchone()
            stats['total_artists'] = result[0] if result else 0
            
            # Labels count
            result = self.conn.execute(
                "SELECT COUNT(DISTINCT label) FROM albums WHERE label IS NOT NULL"
            ).fetchone()
            stats['total_labels'] = result[0] if result else 0
            
            return stats
        except Exception as e:
            print(f"Error getting statistics: {e}")
            return {}

