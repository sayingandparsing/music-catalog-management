#!/usr/bin/env python3
"""
DSD Music Converter - Main CLI Entry Point
Converts DSD audio files (ISO/DSF) to FLAC or DSF format.
"""

import sys
from pathlib import Path
from typing import Optional
import click
from datetime import datetime, timedelta

from src.config import Config
from src.logger import setup_logger, ConversionLogger
from src.scanner import DirectoryScanner, Album
from src.archiver import Archiver
from src.converter import AudioConverter
from src.state_manager import StateManager, AlbumStatus
from src.metadata_enricher import MetadataEnricher
from src.database import MusicDatabase
from src.album_metadata import AlbumMetadata
from src.deduplication import DeduplicationManager
from src.working_directory import WorkingDirectoryManager
from src.sacd_metadata_parser import parse_sacd_metadata_file, find_sacd_metadata_files
import uuid

try:
    from mutagen.flac import FLAC as MutagenFLAC
except ImportError:
    MutagenFLAC = None


class ConversionOrchestrator:
    """
    Orchestrates the entire conversion process.
    Coordinates scanning, archiving, converting, and metadata enrichment.
    """
    
    def __init__(
        self,
        config: Config,
        logger: ConversionLogger,
        dry_run: bool = False,
        resume: bool = False,
        single_album: bool = False
    ):
        """
        Initialize orchestrator.
        
        Args:
            config: Configuration object
            logger: Logger instance
            dry_run: If True, don't perform actual conversions
            resume: If True, resume from previous session
            single_album: If True, treat input as single album directory
        """
        self.config = config
        self.logger = logger
        self.dry_run = dry_run
        self.resume = resume
        self.single_album = single_album
        
        # Initialize components
        self.scanner = DirectoryScanner(
            music_extensions=config.get('files.music_extensions'),
            copy_extensions=config.get('files.copy_extensions')
        )
        
        archive_dir = Path(config.get('paths.archive_dir'))
        self.archiver = Archiver(archive_dir)
        
        self.converter = AudioConverter(
            sample_rate=config.get('conversion.sample_rate'),
            bit_depth=config.get('conversion.bit_depth'),
            mode=config.get('conversion.mode'),
            resampler=config.get('conversion.audio_filter.resampler', 'soxr'),
            soxr_precision=config.get('conversion.audio_filter.soxr_precision', 28),
            dither_method=config.get('conversion.audio_filter.dither_method', 'triangular'),
            lowpass_freq=config.get('conversion.audio_filter.lowpass_freq', 40000),
            flac_compression_level=config.get('conversion.flac_compression_level', 8),
            preserve_metadata=config.get('conversion.preserve_metadata', True),
            ffmpeg_threads=config.get('processing.ffmpeg_threads', 0),
            calculate_dynamic_range=config.get('processing.calculate_dynamic_range', True),
            flac_standardization_enabled=config.get('conversion.flac_standardization.enabled', False),
            flac_higher_quality_behavior=config.get('conversion.flac_standardization.higher_quality_behavior', 'skip')
        )
        
        self.state_manager = StateManager()
        
        # Initialize working directory manager
        working_dir = Path(config.get('paths.working_dir', './working'))
        self.working_dir_manager = WorkingDirectoryManager(
            working_root=working_dir,
            verify_copies=True
        )
        
        # Initialize database if enabled
        self.database = None
        self.dedup_manager = None
        if config.get('database.enabled'):
            try:
                db_path = Path(config.get('database.path', './music_catalog.duckdb'))
                self.database = MusicDatabase(db_path)
                self.dedup_manager = DeduplicationManager(
                    database=self.database,
                    verify_checksums=config.get('processing.verify_checksums', True)
                )
                self.logger.info(f"Database initialized: {db_path}")
            except Exception as e:
                self.logger.warning(f"Database initialization failed: {e}")
        
        # Optional metadata enricher
        self.metadata_enricher = None
        if config.get('metadata.enabled'):
            try:
                self.metadata_enricher = MetadataEnricher(
                    sources=config.get('metadata.sources'),
                    discogs_token=config.get('metadata.discogs.user_token'),
                    behavior=config.get('metadata.behavior'),
                    database=self.database
                )
            except ImportError as e:
                self.logger.warning(f"Metadata enrichment disabled: {e}")
        
        # Statistics
        self.stats = {
            'albums_processed': 0,
            'albums_skipped': 0,
            'albums_already_processed': 0,
            'files_converted': 0,
            'files_failed': 0,
            'start_time': None,
            'end_time': None
        }
        
        # Skip processed flag
        self.skip_processed = config.get('processing.skip_processed', True)
    
    def run(self, input_dir: Path) -> bool:
        """
        Run the conversion process.
        
        Args:
            input_dir: Input directory to process
            
        Returns:
            True if successful
        """
        self.stats['start_time'] = datetime.now()
        
        output_dir = Path(
            self.config.get('paths.output_dir') or input_dir
        )
        archive_dir = Path(self.config.get('paths.archive_dir'))
        
        self.logger.log_conversion_start(input_dir, output_dir, archive_dir)
        
        try:
            # Load or create session
            if self.resume:
                session = self.state_manager.load_session()
                if session:
                    self.logger.info("Resuming previous session...")
                    albums = self._get_albums_from_session(session)
                else:
                    self.logger.warning("No previous session found, starting new...")
                    albums = self._scan_and_initialize(input_dir, output_dir, archive_dir)
            else:
                albums = self._scan_and_initialize(input_dir, output_dir, archive_dir)
            
            if not albums:
                self.logger.warning("No albums found to process")
                return True
            
            # Process albums
            success = self._process_albums(albums, output_dir)
            
            # Mark session as completed
            self.state_manager.mark_completed()
            
            self.stats['end_time'] = datetime.now()
            duration = self.stats['end_time'] - self.stats['start_time']
            self.stats['duration'] = str(duration).split('.')[0]  # Remove microseconds
            
            self.logger.log_conversion_end(success, self.stats)
            
            # Close database connection
            if self.database:
                self.database.close()
            
            return success
            
        except KeyboardInterrupt:
            self.logger.warning("\nConversion interrupted by user")
            self.logger.info("State has been saved. Use --resume to continue.")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}", exc_info=True)
            return False
    
    def _scan_and_initialize(
        self,
        input_dir: Path,
        output_dir: Path,
        archive_dir: Path
    ) -> list[Album]:
        """Scan directory and initialize session."""
        self.logger.info(f"Scanning directory: {input_dir}")
        albums = self.scanner.scan(input_dir, single_album=self.single_album)
        
        self.logger.info(f"Found {len(albums)} albums")
        self.scanner.print_summary(albums)
        
        # Create session
        self.state_manager.create_session(
            input_dir=input_dir,
            output_dir=output_dir,
            archive_dir=archive_dir,
            conversion_mode=self.config.get('conversion.mode'),
            sample_rate=self.config.get('conversion.sample_rate'),
            bit_depth=self.config.get('conversion.bit_depth'),
            enrich_metadata=self.config.get('metadata.enabled')
        )
        
        return albums
    
    def _get_albums_from_session(self, session) -> list[Album]:
        """Reconstruct albums from session state, considering working directories."""
        # Check if we should resume from working directories
        resume_from_working = self.config.get('processing.resume_from_working', True)
        
        if resume_from_working:
            # Get albums that can be resumed from working directories
            resumable = self.state_manager.get_resumable_albums()
            
            if resumable:
                self.logger.info(f"Found {len(resumable)} albums with working directories")
                
                # For each resumable album, verify working directories exist
                albums = []
                for album_state in resumable:
                    album_path = Path(album_state.album_path)
                    
                    # Check if working directories still exist
                    has_working = False
                    if album_state.working_source_path:
                        working_source = Path(album_state.working_source_path)
                        if working_source.exists():
                            has_working = True
                    
                    if album_state.working_processed_path:
                        working_processed = Path(album_state.working_processed_path)
                        if working_processed.exists():
                            has_working = True
                    
                    if has_working:
                        # Working directories exist, can resume
                        self.logger.info(f"  Resuming: {album_state.album_name} (stage: {album_state.processing_stage})")
                        
                        # Use working_source as the source if it exists, otherwise original path
                        if album_state.working_source_path and Path(album_state.working_source_path).exists():
                            scan_path = Path(album_state.working_source_path)
                        elif album_path.exists():
                            scan_path = album_path
                        else:
                            self.logger.warning(f"  Skipping {album_state.album_name}: no source available")
                            continue
                        
                        # Re-scan the album
                        album = self.scanner._scan_album(scan_path, scan_path.parent)
                        album.album_id = None  # Will be retrieved from database
                        albums.append(album)
                    elif album_path.exists():
                        # Working directories don't exist, but original still does
                        self.logger.info(f"  Reprocessing: {album_state.album_name} (working dirs lost)")
                        album = self.scanner._scan_album(album_path, album_path.parent)
                        albums.append(album)
                    else:
                        self.logger.warning(f"  Skipping {album_state.album_name}: source no longer exists")
                
                return albums
        
        # Standard resume: get pending albums
        pending = self.state_manager.get_pending_albums()
        
        # Reconstruct Album objects for pending albums
        albums = []
        for album_state in pending:
            album_path = Path(album_state.album_path)
            if album_path.exists():
                # Re-scan the album
                album = self.scanner._scan_album(album_path, album_path.parent)
                albums.append(album)
        
        return albums
    
    def _process_albums(self, albums: list[Album], output_dir: Path) -> bool:
        """
        Process all albums.
        
        Args:
            albums: List of albums to process
            output_dir: Output directory
            
        Returns:
            True if all albums processed successfully
        """
        total_albums = len(albums)
        all_success = True
        
        for idx, album in enumerate(albums, 1):
            # Check for pause signal
            if self.config.get('processing.check_pause'):
                if self.state_manager.check_pause_signal():
                    self.logger.info("\nPause signal detected. Stopping after current album.")
                    self.logger.info("Remove .state/PAUSE file and use --resume to continue.")
                    break
            
            # Check if album should be skipped (already processed)
            if self.skip_processed and self.dedup_manager:
                should_skip, reason = self.dedup_manager.should_skip_album(
                    album.root_path,
                    [f.path for f in album.music_files]
                )
                
                if should_skip:
                    self.logger.info(f"  Skipping album: {reason}")
                    self.stats['albums_already_processed'] += 1
                    continue
            
            self.logger.log_album_start(album.root_path, idx, total_albums)
            
            success = self._process_album(album, output_dir)
            
            if success:
                self.stats['albums_processed'] += 1
            else:
                self.stats['albums_skipped'] += 1
                all_success = False
            
            self.logger.log_album_end(album.root_path, success, len(album.music_files))
        
        return all_success
    
    def _process_album(self, album: Album, output_dir: Path) -> bool:
        """
        Process a single album using multi-stage working directory approach.
        
        Stages:
        1. PREPARING - Create working directories and copy source
        2. CONVERTING - Convert tracks to processed directory
        3. ARCHIVING - Copy source to archive
        4. FINALIZING - Move processed to output, delete original
        5. COMPLETED - Cleanup working directories
        
        Args:
            album: Album to process
            output_dir: Output directory
            
        Returns:
            True if successful
        """
        max_retries = self.config.get('processing.max_retries', 3)
        skip_on_error = self.config.get('processing.skip_album_on_error', True)
        cleanup_on_success = self.config.get('processing.cleanup_working_on_success', True)
        cleanup_on_failure = self.config.get('processing.cleanup_working_on_failure', False)
        start_time = datetime.now()
        
        # Working directory paths (will be set in PREPARING stage)
        working_source_path = None
        working_processed_path = None
        
        # Determine the original source path (may differ from album.root_path during resume)
        # This is the path we should use for source removal, not album.root_path
        original_source_path = album.root_path
        if self.state_manager.session:
            for album_state in self.state_manager.session.albums:
                # Check if album.root_path is a working directory
                if (album_state.working_source_path and 
                    str(album.root_path) == album_state.working_source_path):
                    # Found match - use the stored original path
                    original_source_path = Path(album_state.album_path)
                    self.logger.debug(f"  Resuming from working directory, original source: {original_source_path}")
                    break
                # Also check if album.root_path matches the original album_path
                elif str(album.root_path) == album_state.album_path:
                    original_source_path = album.root_path
                    break
        
        # Get or create album ID
        audio_files = [f.path for f in album.music_files]
        if self.dedup_manager:
            album_id = self.dedup_manager.get_or_create_album_id(
                album.root_path,
                audio_files
            )
        else:
            # Fallback if no dedup manager
            album_id = album.album_id or str(uuid.uuid4())
        
        # Calculate audio checksum
        audio_checksum = AlbumMetadata.calculate_audio_checksum(audio_files)
        
        # Create or update album record in database
        if self.database:
            db_album = self.database.get_album_by_id(album_id)
            if not db_album:
                self.database.create_album(
                    album_id=album_id,
                    album_name=album.name,
                    source_path=str(original_source_path),  # Use original source, not working dir
                    audio_files_checksum=audio_checksum,
                    conversion_mode=self.config.get('conversion.mode'),
                    sample_rate=self.config.get('conversion.sample_rate'),
                    bit_depth=self.config.get('conversion.bit_depth')
                )
        
        try:
            # ===================================================================
            # STAGE 1: PREPARING - Create working directories
            # ===================================================================
            self.logger.info("  [PREPARING] Creating working directories...")
            self.state_manager.update_album_status(
                album.root_path,
                AlbumStatus.PENDING,
                processing_stage='preparing'
            )
            
            if not self.dry_run:
                # Check disk space
                space_ok, space_error = self.working_dir_manager.check_disk_space(album.root_path)
                if not space_ok:
                    self.logger.error(f"  {space_error}")
                    self.state_manager.update_album_status(
                        album.root_path,
                        AlbumStatus.FAILED,
                        error_message=space_error,
                        processing_stage='failed_prepare'
                    )
                    return False
                
                # Create working directories
                success, working_source_path, working_processed_path, error = \
                    self.working_dir_manager.create_working_dirs(album.root_path, album.name)
                
                if not success:
                    self.logger.error(f"  Failed to create working directories: {error}")
                    self.state_manager.update_album_status(
                        album.root_path,
                        AlbumStatus.FAILED,
                        error_message=error,
                        processing_stage='failed_prepare'
                    )
                    return False
                
                # Copy source to working_source
                self.logger.info(f"  Copying source to working directory...")
                success, error = self.working_dir_manager.copy_to_source(
                    album.root_path,
                    working_source_path
                )
                
                if not success:
                    self.logger.error(f"  Failed to copy source: {error}")
                    # Cleanup and fail
                    self.working_dir_manager.cleanup_working_dirs(working_source_path, working_processed_path)
                    self.state_manager.update_album_status(
                        album.root_path,
                        AlbumStatus.FAILED,
                        error_message=error,
                        processing_stage='failed_prepare'
                    )
                    return False
                
                # Create processed structure (empty, for converted files)
                success, error = self.working_dir_manager.create_processed_structure(
                    album.root_path,
                    working_processed_path,
                    copy_non_music=True,
                    music_extensions=self.config.get('files.music_extensions')
                )
                
                if not success:
                    self.logger.error(f"  Failed to create processed structure: {error}")
                    # Cleanup and fail
                    self.working_dir_manager.cleanup_working_dirs(working_source_path, working_processed_path)
                    self.state_manager.update_album_status(
                        album.root_path,
                        AlbumStatus.FAILED,
                        error_message=error,
                        processing_stage='failed_prepare'
                    )
                    return False
                
                self.logger.info(f"  Working directories created successfully")
                self.state_manager.update_album_status(
                    album.root_path,
                    AlbumStatus.CONVERTING,
                    processing_stage='converting',
                    working_source_path=working_source_path,
                    working_processed_path=working_processed_path
                )
                
                # Update database with working paths
                if self.database:
                    self.database.update_album(
                        album_id=album_id,
                        working_source_path=str(working_source_path),
                        working_processed_path=str(working_processed_path),
                        processing_stage='converting'
                    )
            else:
                self.logger.info("  [DRY RUN] Would create working directories")
            
            # ===================================================================
            # STAGE 2: CONVERTING - Convert tracks
            # ===================================================================
            self.logger.info("  [CONVERTING] Processing tracks...")
            
            if self.database:
                self.database.add_processing_history(
                    album_id=album_id,
                    operation_type='convert',
                    status='started',
                    working_source_path=str(working_source_path) if working_source_path else None,
                    working_processed_path=str(working_processed_path) if working_processed_path else None
                )
            
            files_failed = 0
            files_converted = 0
            files_skipped = 0
            conversion_start = datetime.now()
            
            for music_file in album.music_files:
                # Determine input path (from working_source if available, else original)
                if working_source_path:
                    input_file_path = working_source_path / music_file.relative_path
                else:
                    input_file_path = music_file.path
                
                # Determine output path (in working_processed)
                if working_processed_path:
                    output_file_path = working_processed_path / music_file.relative_path
                else:
                    output_file_path = output_dir / album.root_path.name / music_file.relative_path
                
                # Change extension based on conversion mode
                if self.config.get('conversion.mode') == 'iso_dsf_to_flac':
                    output_file_path = output_file_path.with_suffix('.flac')
                elif self.config.get('conversion.mode') == 'iso_to_dsf':
                    output_file_path = output_file_path.with_suffix('.dsf')
                
                # Extract track number from filename if possible
                import re
                track_num = None
                match = re.match(r'^(\d+)', music_file.path.stem)
                if match:
                    track_num = int(match.group(1))
                
                # Convert file with retries
                success = False
                for attempt in range(1, max_retries + 1):
                    self.state_manager.update_file_status(
                        album.root_path,
                        music_file.path,
                        'converting'
                    )
                    
                    if not self.dry_run:
                        # Use skip_existing=True for resume capability
                        success, error, duration, dynamic_range = self.converter.convert_file(
                            input_file_path,
                            output_file_path,
                            skip_existing=True
                        )
                        
                        if success:
                            if error and "skipped" in error.lower():
                                # File was skipped (already converted)
                                self.logger.info(f"  ↻ {music_file.path.name} (already converted)")
                                files_skipped += 1
                            else:
                                # File was converted
                                self.logger.log_file_conversion(
                                    music_file.path,
                                    output_file_path,
                                    True,
                                    duration
                                )
                                files_converted += 1
                                
                                # Create track record in database
                                if self.database:
                                    # Check if this is an ISO file (multi-track handling is separate)
                                    is_iso = input_file_path.suffix.lower() == '.iso'
                                    
                                    if not is_iso and output_file_path.exists():
                                        # Single-file conversion (DSF, DFF, FLAC)
                                        # Extract metadata from source/output file
                                        track_metadata = self._extract_track_metadata(
                                            source_file_path=input_file_path,
                                            output_file_path=output_file_path,
                                            is_from_iso=False
                                        )
                                        
                                        # Get file stats
                                        file_stats = output_file_path.stat()
                                        
                                        # Create track record
                                        track_id = str(uuid.uuid4())
                                        self.database.create_track(
                                            track_id=track_id,
                                            album_id=album_id,
                                            track_number=track_metadata.get('track_number', track_num if track_num else 0),
                                            title=track_metadata.get('title', output_file_path.stem),
                                            file_path=str(output_file_path),
                                            duration_seconds=track_metadata.get('duration_seconds'),
                                            file_size=file_stats.st_size,
                                            file_format=output_file_path.suffix.lower(),
                                            genre=track_metadata.get('genre'),
                                            dynamic_range_crest=dynamic_range.get('dynamic_range_crest') if dynamic_range else None,
                                            dynamic_range_r128=dynamic_range.get('dynamic_range_r128') if dynamic_range else None,
                                            musicians=track_metadata.get('musicians')
                                        )
                                        
                                        self.logger.debug(f"  Created track record: {track_metadata.get('title', output_file_path.stem)}")
                                    
                                    elif is_iso:
                                        # Multi-track ISO conversion
                                        # ISO files create multiple output files in the output directory
                                        # Find all created FLAC/DSF files in the output directory
                                        output_dir = output_file_path.parent
                                        
                                        # Look for SACD metadata files
                                        sacd_metadata = None
                                        metadata_files = find_sacd_metadata_files(output_dir)
                                        if not metadata_files:
                                            # Also check source directory
                                            metadata_files = find_sacd_metadata_files(album.root_path)
                                        
                                        if metadata_files:
                                            sacd_metadata = parse_sacd_metadata_file(metadata_files[0])
                                            if sacd_metadata:
                                                self.logger.info(f"  Found SACD metadata file with {len(sacd_metadata.get('tracks', []))} tracks")
                                                
                                                # Update album with SACD metadata
                                                sacd_info = sacd_metadata.get('album', {}) or sacd_metadata.get('disc', {})
                                                if sacd_info:
                                                    album_updates = {}
                                                    if 'catalog_number' in sacd_info:
                                                        album_updates['catalog_number'] = sacd_info['catalog_number']
                                                    if 'genre' in sacd_info:
                                                        album_updates['genre'] = sacd_info['genre']
                                                    if 'label' in sacd_info:
                                                        album_updates['label'] = sacd_info['label']
                                                    
                                                    if album_updates:
                                                        self.database.update_album(album_id=album_id, **album_updates)
                                                        self.logger.debug(f"  Updated album with SACD metadata")
                                        
                                        # Determine file extension based on conversion mode
                                        if self.config.get('conversion.mode') == 'iso_dsf_to_flac':
                                            pattern = '*.flac'
                                        else:
                                            pattern = '*.dsf'
                                        
                                        # Find all output files
                                        output_files = sorted(output_dir.glob(pattern))
                                        
                                        if output_files:
                                            self.logger.debug(f"  Processing {len(output_files)} tracks from ISO")
                                            
                                            for track_file in output_files:
                                                # Parse track number from filename
                                                import re
                                                track_num_match = re.match(r'^(\d+)', track_file.stem)
                                                track_num = int(track_num_match.group(1)) if track_num_match else None
                                                
                                                # Extract metadata from each track with SACD metadata
                                                track_metadata = self._extract_track_metadata(
                                                    source_file_path=input_file_path,
                                                    output_file_path=track_file,
                                                    is_from_iso=True,
                                                    sacd_metadata=sacd_metadata,
                                                    track_number=track_num
                                                )
                                                
                                                # Get file stats
                                                file_stats = track_file.stat()
                                                
                                                # Create track record
                                                track_id = str(uuid.uuid4())
                                                self.database.create_track(
                                                    track_id=track_id,
                                                    album_id=album_id,
                                                    track_number=track_metadata.get('track_number', 0),
                                                    title=track_metadata.get('title', track_file.stem),
                                                    file_path=str(track_file),
                                                    duration_seconds=track_metadata.get('duration_seconds'),
                                                    file_size=file_stats.st_size,
                                                    file_format=track_file.suffix.lower(),
                                                    genre=track_metadata.get('genre'),
                                                    dynamic_range_crest=None,  # Dynamic range not calculated per-track for ISO
                                                    dynamic_range_r128=None,
                                                    musicians=track_metadata.get('musicians')
                                                )
                                                
                                                self.logger.debug(f"  Created track record: {track_metadata.get('title', track_file.stem)}")
                                        else:
                                            self.logger.warning(f"  No output files found for ISO conversion in {output_dir}")
                            
                            self.state_manager.update_file_status(
                                album.root_path,
                                music_file.path,
                                'completed'
                            )
                            break
                        else:
                            self.logger.warning(
                                f"  Attempt {attempt}/{max_retries} failed: {error}"
                            )
                            if attempt == max_retries:
                                self.logger.error(f"  Max retries reached for {music_file.path.name}")
                                self.state_manager.update_file_status(
                                    album.root_path,
                                    music_file.path,
                                    'failed',
                                    error
                                )
                                files_failed += 1
                    else:
                        self.logger.info(f"  [DRY RUN] Would convert: {music_file.path.name}")
                        success = True
                        files_converted += 1
                        break
                
                # Check if we should skip album on error
                if not success and skip_on_error:
                    self.logger.error(f"  Skipping album due to conversion failure")
                    self.state_manager.update_album_status(
                        album.root_path,
                        AlbumStatus.FAILED,
                        error_message="File conversion failed",
                        processing_stage='failed_convert'
                    )
                    
                    # Record failure in database
                    if self.database:
                        conversion_duration = (datetime.now() - conversion_start).total_seconds()
                        self.database.add_processing_history(
                            album_id=album_id,
                            operation_type='convert',
                            status='failed',
                            error_message="File conversion failed",
                            duration_seconds=conversion_duration
                        )
                    
                    self.stats['files_failed'] += files_failed
                    self.stats['files_converted'] += files_converted
                    
                    # Cleanup working directories if configured
                    if cleanup_on_failure and not self.dry_run:
                        self.working_dir_manager.cleanup_working_dirs(working_source_path, working_processed_path)
                    
                    return False
            
            # All files converted successfully
            conversion_duration = (datetime.now() - conversion_start).total_seconds()
            self.logger.info(f"  Conversion complete: {files_converted} converted, {files_skipped} skipped")
            
            if self.database:
                self.database.add_processing_history(
                    album_id=album_id,
                    operation_type='convert',
                    status='success',
                    duration_seconds=conversion_duration
                )
            
            # ===================================================================
            # STAGE 3: ARCHIVING - Copy source to archive
            # ===================================================================
            if not self.dry_run:
                self.logger.info("  [ARCHIVING] Archiving original files...")
                self.state_manager.update_album_status(
                    album.root_path,
                    AlbumStatus.ARCHIVING,
                    processing_stage='archiving'
                )
                
                archive_start = datetime.now()
                archive_dir = Path(self.config.get('paths.archive_dir'))
                archive_path = archive_dir / album.root_path.name
                
                # Add timestamp if archive already exists
                if archive_path.exists():
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    archive_path = archive_dir / f"{album.root_path.name}_{timestamp}"
                
                success, error = self.working_dir_manager.copy_to_archive(
                    working_source_path,
                    archive_path
                )
                
                archive_duration = (datetime.now() - archive_start).total_seconds()
                
                if not success:
                    self.logger.error(f"  Archive failed: {error}")
                    self.state_manager.update_album_status(
                        album.root_path,
                        AlbumStatus.FAILED,
                        error_message=error,
                        processing_stage='failed_archive'
                    )
                    
                    if self.database:
                        self.database.add_processing_history(
                            album_id=album_id,
                            operation_type='archive',
                            status='failed',
                            error_message=error,
                            duration_seconds=archive_duration
                        )
                    
                    # Cleanup working directories
                    if cleanup_on_failure:
                        self.working_dir_manager.cleanup_working_dirs(working_source_path, working_processed_path)
                    
                    return False
                
                self.logger.info(f"  Archived to: {archive_path}")
                
                # Update database with archive path
                if self.database:
                    self.database.update_album(
                        album_id=album_id,
                        archive_path=str(archive_path)
                    )
                    self.database.add_processing_history(
                        album_id=album_id,
                        operation_type='archive',
                        status='success',
                        duration_seconds=archive_duration
                    )
                
                # Create metadata file in archive
                archive_audio_files = list(archive_path.rglob('*'))
                archive_audio_files = [f for f in archive_audio_files if f.suffix.lower() in 
                                      self.config.get('files.music_extensions', ['.iso', '.dsf', '.dff', '.flac'])]
                if archive_audio_files:
                    AlbumMetadata.create_for_album(
                        archive_path,
                        archive_audio_files
                    )
            else:
                self.logger.info("  [DRY RUN] Would archive files")
            
            # ===================================================================
            # STAGE 4: FINALIZING - Move processed to output, delete original
            # ===================================================================
            if not self.dry_run:
                self.logger.info("  [FINALIZING] Moving to output location...")
                self.state_manager.update_album_status(
                    album.root_path,
                    AlbumStatus.CONVERTING,  # Still converting status
                    processing_stage='finalizing'
                )
                
                finalize_start = datetime.now()
                
                # Use the original source path determined at the beginning of the method
                # to get the correct album name for the output directory
                output_album_path = output_dir / original_source_path.name
                
                # Move processed to output
                success, error = self.working_dir_manager.move_to_output(
                    working_processed_path,
                    output_album_path
                )
                
                if not success:
                    self.logger.error(f"  Failed to move to output: {error}")
                    self.state_manager.update_album_status(
                        album.root_path,
                        AlbumStatus.FAILED,
                        error_message=error,
                        processing_stage='failed_finalize'
                    )
                    
                    if self.database:
                        self.database.add_processing_history(
                            album_id=album_id,
                            operation_type='finalize',
                            status='failed',
                            error_message=error,
                            duration_seconds=(datetime.now() - finalize_start).total_seconds()
                        )
                    
                    # Cleanup working directories
                    if cleanup_on_failure:
                        self.working_dir_manager.cleanup_working_dirs(working_source_path, None)
                    
                    return False
                
                self.logger.info(f"  Moved to: {output_album_path}")
                
                # Update database with playback path
                if self.database:
                    self.database.update_album(
                        album_id=album_id,
                        playback_path=str(output_album_path)
                    )
                
                # Create metadata file in output
                playback_audio_files = list(output_album_path.glob('*.flac'))
                if playback_audio_files:
                    AlbumMetadata.create_for_album(
                        output_album_path,
                        playback_audio_files,
                        album_id=album_id
                    )
                
                # Metadata enrichment (optional)
                if self.metadata_enricher:
                    self.logger.info("  Enriching metadata...")
                    enrich_start = datetime.now()
                    success_enrich, error_enrich = self.metadata_enricher.enrich_album(
                        output_album_path,
                        playback_audio_files,
                        album_id=album_id
                    )
                    enrich_duration = (datetime.now() - enrich_start).total_seconds()
                    
                    if not success_enrich:
                        self.logger.warning(f"  Metadata enrichment failed: {error_enrich}")
                        if self.database:
                            self.database.add_processing_history(
                                album_id=album_id,
                                operation_type='enrich',
                                status='failed',
                                error_message=error_enrich,
                                duration_seconds=enrich_duration
                            )
                    else:
                        if self.database:
                            self.database.add_processing_history(
                                album_id=album_id,
                                operation_type='enrich',
                                status='success',
                                duration_seconds=enrich_duration
                            )
                
                # Remove source files if configured
                if self.config.get('processing.remove_source_after_conversion', False):
                    self.logger.info("  Removing source files from input directory...")
                    # Safety check: only remove if the path exists and is not a working directory
                    if original_source_path.exists() and not str(original_source_path).endswith(('_source', '_processed')):
                        try:
                            import shutil
                            shutil.rmtree(original_source_path)
                            self.logger.info(f"  Successfully removed: {original_source_path}")
                            
                            if self.database:
                                self.database.add_processing_history(
                                    album_id=album_id,
                                    operation_type='cleanup',
                                    status='success',
                                    duration_seconds=0.0
                                )
                        except Exception as e:
                            self.logger.warning(f"  Failed to remove source files: {e}")
                            if self.database:
                                self.database.add_processing_history(
                                    album_id=album_id,
                                    operation_type='cleanup',
                                    status='failed',
                                    error_message=str(e),
                                    duration_seconds=0.0
                                )
                    else:
                        warning_msg = f"  Skipped source removal - safety check failed (path: {original_source_path})"
                        self.logger.warning(warning_msg)
                        if self.database:
                            self.database.add_processing_history(
                                album_id=album_id,
                                operation_type='cleanup',
                                status='skipped',
                                error_message="Safety check failed - appears to be working directory",
                                duration_seconds=0.0
                            )
            else:
                self.logger.info("  [DRY RUN] Would move to output and remove source")
            
            # ===================================================================
            # STAGE 5: COMPLETED - Cleanup working directories
            # ===================================================================
            if not self.dry_run and cleanup_on_success:
                self.logger.info("  [CLEANUP] Removing working directories...")
                success, error = self.working_dir_manager.cleanup_working_dirs(
                    working_source_path,
                    None  # processed_path already moved
                )
                
                if not success:
                    self.logger.warning(f"  Cleanup warning: {error}")
            
            # Mark album as completed
            self.state_manager.update_album_status(
                album.root_path,
                AlbumStatus.COMPLETED,
                processing_stage='completed',
                working_source_path=None if cleanup_on_success else working_source_path,
                working_processed_path=None  # Already moved
            )
            
            if self.database:
                self.database.update_album(
                    album_id=album_id,
                    processing_stage='completed',
                    working_source_path=None,
                    working_processed_path=None
                )
            
            self.stats['files_converted'] += files_converted
            self.stats['files_failed'] += files_failed
            
            return files_failed == 0
            
        except Exception as e:
            self.logger.error(f"  Error processing album: {e}", exc_info=True)
            self.state_manager.update_album_status(
                album.root_path,
                AlbumStatus.FAILED,
                error_message=str(e),
                processing_stage='failed_convert'
            )
            
            # Record failure in database
            if self.database:
                total_duration = (datetime.now() - start_time).total_seconds()
                self.database.add_processing_history(
                    album_id=album_id,
                    operation_type='convert',
                    status='failed',
                    error_message=str(e),
                    duration_seconds=total_duration
                )
            
            # Cleanup working directories if configured
            if not self.dry_run and cleanup_on_failure:
                self.working_dir_manager.cleanup_working_dirs(working_source_path, working_processed_path)
            
            return False
    
    def _extract_track_metadata(
        self,
        source_file_path: Path,
        output_file_path: Path,
        is_from_iso: bool = False,
        sacd_metadata: Optional[dict] = None,
        track_number: Optional[int] = None
    ) -> dict:
        """
        Extract metadata from audio file for database storage.
        
        For FLAC sources: Extracts metadata from source file (before conversion)
        For ISO sources: Extracts metadata from converted file (after conversion)
        Priority: SACD metadata > embedded tags > filename parsing
        
        Args:
            source_file_path: Path to source audio file
            output_file_path: Path to converted output file
            is_from_iso: Whether the track came from an ISO file
            sacd_metadata: Optional parsed SACD metadata dictionary
            track_number: Optional track number for matching SACD metadata
            
        Returns:
            Dictionary with extracted metadata fields
        """
        metadata = {
            'title': None,
            'track_number': None,
            'duration_seconds': None,
            'artist': None,
            'album': None,
            'date': None,
            'genre': None,
            'musicians': None
        }
        
        # Priority 1: Use SACD metadata if available
        if sacd_metadata and track_number is not None:
            # Find the matching track in SACD metadata
            sacd_track = None
            if 'tracks' in sacd_metadata:
                for track in sacd_metadata['tracks']:
                    if track.get('track_number') == track_number:
                        sacd_track = track
                        break
            
            # Apply SACD track metadata
            if sacd_track:
                if 'title' in sacd_track:
                    metadata['title'] = sacd_track['title']
                if 'artist' in sacd_track:
                    metadata['artist'] = sacd_track['artist']
                if 'duration_seconds' in sacd_track:
                    metadata['duration_seconds'] = sacd_track['duration_seconds']
                metadata['track_number'] = track_number
            
            # Apply SACD album/disc metadata
            sacd_info = sacd_metadata.get('album', {}) or sacd_metadata.get('disc', {})
            if sacd_info:
                if not metadata['artist'] and 'artist' in sacd_info:
                    metadata['artist'] = sacd_info['artist']
                if 'album' in sacd_info or 'title' in sacd_info:
                    metadata['album'] = sacd_info.get('album') or sacd_info.get('title')
                if 'genre' in sacd_info:
                    metadata['genre'] = sacd_info['genre']
        
        # Priority 2: Determine which file to extract metadata from
        # For FLAC sources, use source file (preserves original metadata)
        # For ISO sources, use output file (ISO may not have embedded metadata)
        metadata_file = output_file_path if is_from_iso else source_file_path
        
        # Extract metadata from FLAC file using mutagen (only fill in missing values)
        if MutagenFLAC and metadata_file.exists() and metadata_file.suffix.lower() == '.flac':
            try:
                audio = MutagenFLAC(str(metadata_file))
                
                # Extract basic tags (only if not already set by SACD metadata)
                if not metadata['title'] and 'title' in audio:
                    metadata['title'] = audio['title'][0]
                if not metadata['track_number'] and 'tracknumber' in audio:
                    # Handle formats like "1" or "1/12"
                    track_str = audio['tracknumber'][0]
                    metadata['track_number'] = int(track_str.split('/')[0])
                if not metadata['artist'] and 'artist' in audio:
                    metadata['artist'] = audio['artist'][0]
                if not metadata['album'] and 'album' in audio:
                    metadata['album'] = audio['album'][0]
                if not metadata['date'] and 'date' in audio:
                    metadata['date'] = audio['date'][0]
                if not metadata['genre'] and 'genre' in audio:
                    metadata['genre'] = audio['genre'][0]
                
                # Extract musicians information if available (only if not already set)
                if not metadata['musicians']:
                    musicians_list = []
                    for tag in ['performer', 'composer', 'conductor', 'orchestra']:
                        if tag in audio:
                            for value in audio[tag]:
                                musicians_list.append({
                                    'role': tag,
                                    'name': value
                                })
                    
                    if musicians_list:
                        metadata['musicians'] = musicians_list
                    
            except Exception as e:
                self.logger.debug(f"Could not extract mutagen metadata from {metadata_file}: {e}")
        
        # Priority 3: Fallback - Parse track number and title from filename if not found
        if metadata['track_number'] is None:
            import re
            match = re.match(r'^(\d+)', metadata_file.stem)
            if match:
                metadata['track_number'] = int(match.group(1))
        
        if metadata['title'] is None:
            # Use filename as title, cleaning up common patterns
            title = metadata_file.stem
            # Remove leading track numbers (e.g., "01 - Title" -> "Title")
            title = re.sub(r'^\d+\s*[-.]?\s*', '', title)
            metadata['title'] = title if title else metadata_file.stem
        
        # Get duration from ffprobe if not already set
        if not metadata['duration_seconds'] and output_file_path.exists():
            file_info = self.converter.get_file_info(output_file_path)
            if file_info and 'format' in file_info:
                try:
                    duration = float(file_info['format'].get('duration', 0))
                    metadata['duration_seconds'] = round(duration, 2) if duration > 0 else None
                except (ValueError, TypeError):
                    pass
        
        return metadata

@click.command()
@click.argument('input_dir', type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option('--output', '-o', 'output_dir', type=click.Path(path_type=Path),
              help='Output directory (default: same as input)')
@click.option('--archive', '-a', 'archive_dir', type=click.Path(path_type=Path),
              help='Archive directory for backups (required)')
@click.option('--mode', '-m', type=click.Choice(['iso_dsf_to_flac', 'iso_to_dsf']),
              help='Conversion mode')
@click.option('--sample-rate', '-r', type=click.Choice(['88200', '96000', '176400', '192000']),
              help='Sample rate in Hz')
@click.option('--bit-depth', '-b', type=click.Choice(['16', '24', '32']),
              help='Bit depth')
@click.option('--config', '-c', 'config_file', type=click.Path(exists=True, path_type=Path),
              help='Configuration file path')
@click.option('--enrich-metadata', is_flag=True,
              help='Enable metadata enrichment')
@click.option('--resume', is_flag=True,
              help='Resume previous conversion')
@click.option('--pause', is_flag=True,
              help='Create pause signal file and exit')
@click.option('--dry-run', is_flag=True,
              help='Simulate conversion without actually converting')
@click.option('--log-level', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
              help='Logging level')
@click.option('--single-album', is_flag=True,
              help='Treat INPUT_DIR as a single album (preserves internal structure like CD1, CD2)')
def main(
    input_dir: Path,
    output_dir: Optional[Path],
    archive_dir: Optional[Path],
    mode: Optional[str],
    sample_rate: Optional[str],
    bit_depth: Optional[str],
    config_file: Optional[Path],
    enrich_metadata: bool,
    resume: bool,
    pause: bool,
    dry_run: bool,
    log_level: Optional[str],
    single_album: bool
):
    """
    DSD Music Converter - Convert ISO/DSF files to FLAC or DSF.
    
    INPUT_DIR: Directory containing music files to convert
    """
    
    # Handle pause signal
    if pause:
        state_mgr = StateManager()
        state_mgr.create_pause_signal()
        click.echo("Pause signal created. Conversion will stop after current album.")
        return
    
    try:
        # Load configuration
        config = Config(config_file)
        
        # Override with CLI arguments
        config.update_from_args(
            output_dir=str(output_dir) if output_dir else None,
            archive_dir=str(archive_dir) if archive_dir else None,
            mode=mode,
            sample_rate=int(sample_rate) if sample_rate else None,
            bit_depth=int(bit_depth) if bit_depth else None,
            enrich_metadata=enrich_metadata,
            log_level=log_level
        )
        
        # Validate configuration
        is_valid, errors = config.validate()
        if not is_valid:
            click.echo("Configuration errors:", err=True)
            for error in errors:
                click.echo(f"  - {error}", err=True)
            sys.exit(1)
        
        # Set up logging
        logger = setup_logger(
            log_file=config.get('logging.log_file'),
            error_log_file=config.get('logging.error_log_file'),
            level=config.get('logging.level'),
            console_timestamps=config.get('logging.console_timestamps')
        )
        
        # Create orchestrator and run
        orchestrator = ConversionOrchestrator(
            config=config,
            logger=logger,
            dry_run=dry_run,
            resume=resume,
            single_album=single_album
        )
        
        success = orchestrator.run(input_dir)
        
        sys.exit(0 if success else 1)
        
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

