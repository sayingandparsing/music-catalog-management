"""
Audio converter for DSD music files.
Uses ffmpeg for conversion from ISO/DSF to FLAC or DSF.
"""

import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
import time
import numpy as np

try:
    import pyloudnorm as pyln
except ImportError:
    pyln = None


class ConversionError(Exception):
    """Exception raised for conversion errors."""
    pass


class AudioConverter:
    """
    Handles audio file conversion using ffmpeg.
    Supports ISO/DSF to FLAC and ISO to DSF conversion.
    """
    
    def __init__(
        self,
        sample_rate: int = 88200,
        bit_depth: int = 24,
        mode: str = "iso_dsf_to_flac",
        resampler: str = "soxr",
        soxr_precision: int = 28,
        dither_method: str = "triangular",
        lowpass_freq: int = 40000,
        flac_compression_level: int = 8,
        preserve_metadata: bool = True,
        ffmpeg_threads: int = 0,
        calculate_dynamic_range: bool = True,
        flac_standardization_enabled: bool = False,
        flac_higher_quality_behavior: str = "skip"
    ):
        """
        Initialize converter.
        
        Args:
            sample_rate: Target sample rate in Hz
            bit_depth: Target bit depth for PCM/FLAC
            mode: Conversion mode ('iso_dsf_to_flac' or 'iso_to_dsf')
            resampler: Resampler to use ('soxr' or 'swr')
            soxr_precision: SoX resampler precision (20-28)
            dither_method: Dithering method ('triangular', 'rectangular', 'none')
            lowpass_freq: Lowpass filter frequency in Hz (0 to disable)
            flac_compression_level: FLAC compression level (0-12)
            preserve_metadata: Whether to preserve source metadata
            ffmpeg_threads: Number of threads for ffmpeg (0 = auto)
            calculate_dynamic_range: Whether to calculate dynamic range metrics
            flac_standardization_enabled: Enable FLAC to FLAC standardization
            flac_higher_quality_behavior: Behavior for higher-quality FLAC ('skip' or 'downsample')
        """
        self.sample_rate = sample_rate
        self.bit_depth = bit_depth
        
        # Validate conversion mode
        valid_modes = ['iso_dsf_to_flac', 'iso_to_dsf']
        if mode not in valid_modes:
            raise ValueError(
                f"Invalid conversion mode: '{mode}'. "
                f"Valid modes are: {', '.join(valid_modes)}"
            )
        self.mode = mode
        
        self.resampler = resampler
        self.soxr_precision = soxr_precision
        self.dither_method = dither_method
        self.lowpass_freq = lowpass_freq
        self.flac_compression_level = flac_compression_level
        self.preserve_metadata = preserve_metadata
        self.ffmpeg_threads = ffmpeg_threads
        self.calculate_dynamic_range = calculate_dynamic_range
        self.flac_standardization_enabled = flac_standardization_enabled
        self.flac_higher_quality_behavior = flac_higher_quality_behavior
        
        # Verify ffmpeg is available
        if not self._check_ffmpeg():
            raise RuntimeError(
                "ffmpeg not found. Please install ffmpeg to use this tool."
            )
        
        # Check for sacd_extract (optional but needed for ISO files)
        self.has_sacd_extract = self._check_sacd_extract()
    
    def _check_ffmpeg(self) -> bool:
        """
        Check if ffmpeg is available.
        
        Returns:
            True if ffmpeg is available
        """
        return shutil.which('ffmpeg') is not None
    
    def _check_sacd_extract(self) -> bool:
        """
        Check if sacd_extract is available.
        
        Returns:
            True if sacd_extract is available
        """
        return shutil.which('sacd_extract') is not None
    
    def convert_file(
        self,
        input_path: Path,
        output_path: Path,
        overwrite: bool = False,
        skip_existing: bool = False
    ) -> Tuple[bool, Optional[str], float, Optional[Dict[str, Any]]]:
        """
        Convert a single audio file.
        
        Args:
            input_path: Input file path
            output_path: Output file path
            overwrite: Whether to overwrite existing output file
            skip_existing: If True, skip conversion if output exists (for resume)
            
        Returns:
            Tuple of (success, error_message, duration_seconds, dynamic_range_metrics)
        """
        # Initialize start_time early to avoid NameError in exception handler
        start_time = time.time()
        
        # Validate input
        if not input_path.exists():
            return False, f"Input file not found: {input_path}", 0.0, None
        
        # Determine input extension
        input_ext = input_path.suffix.lower()
        
        # Check output - special handling for ISO files
        if input_ext == '.iso' and skip_existing:
            # For ISO files, check if output tracks already exist
            # We can't check a single output_path since ISOs create multiple files
            output_ext = '.flac' if self.mode == 'iso_dsf_to_flac' else '.dsf'
            existing_tracks = list(output_path.parent.glob(f'*{output_ext}'))
            
            # Filter to valid non-empty files
            valid_existing = [f for f in existing_tracks if f.exists() and f.stat().st_size > 100]
            
            if valid_existing:
                # Some tracks exist - skip if we have reasonable output already
                # (We can't know exact count without extraction, so we trust existing files)
                return True, f"Already converted (skipped, {len(valid_existing)} tracks found)", 0.0, None
        elif output_path.exists():
            if skip_existing:
                # Skip this file - already converted (resume scenario)
                return True, "Already converted (skipped)", 0.0, None
            elif not overwrite:
                return False, f"Output file already exists: {output_path}", 0.0, None
        
        # Create output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Handle FLAC standardization if enabled
            if input_ext == '.flac' and self.flac_standardization_enabled:
                # Get source FLAC specifications
                source_specs = self._get_flac_specs(input_path)
                
                if not source_specs:
                    return False, "Could not read FLAC file specifications", 0.0, None
                
                # Check if already at target format (24-bit/88.2kHz)
                if (source_specs['sample_rate'] == self.sample_rate and 
                    source_specs['bit_depth'] == self.bit_depth):
                    # Already at target format, skip conversion
                    duration = time.time() - start_time
                    return True, "Already at target format (24/88.2), skipped", duration, None
                
                # Check if higher quality and should skip
                # Use AND logic: both sample rate AND bit depth must be higher
                # to consider source unambiguously "higher quality"
                # (avoids ambiguous cases like 16/192k vs 24/88k)
                is_higher_quality = (
                    source_specs['sample_rate'] > self.sample_rate and
                    source_specs['bit_depth'] > self.bit_depth
                )
                
                if is_higher_quality and self.flac_higher_quality_behavior == 'skip':
                    # Higher quality file and configured to skip
                    duration = time.time() - start_time
                    return True, f"Higher quality ({source_specs['bit_depth']}/{source_specs['sample_rate']//1000}k), skipped", duration, None
                
                # Proceed with FLAC to FLAC conversion
                success, error = self._convert_flac_to_flac(input_path, output_path, source_specs)
            
            # Track expected output count for ISO files
            expected_track_count = 0
            
            if self.mode == "iso_dsf_to_flac":
                if input_ext in ['.iso']:
                    success, error, expected_track_count = self._convert_iso_to_flac(input_path, output_path)
                elif input_ext in ['.dsf', '.dff']:
                    success, error = self._convert_dsf_to_flac(input_path, output_path)
                elif input_ext == '.flac':
                    # FLAC file but standardization not enabled - skip it
                    duration = time.time() - start_time
                    return True, "FLAC file skipped (standardization disabled)", duration, None
                else:
                    return False, f"Unsupported input format: {input_ext}", 0.0, None
            
            elif self.mode == "iso_to_dsf":
                if input_ext in ['.iso']:
                    success, error = self._convert_iso_to_dsf(input_path, output_path)
                else:
                    return False, f"Unsupported input format for iso_to_dsf: {input_ext}", 0.0, None
            
            else:
                return False, f"Unknown conversion mode: {self.mode}", 0.0, None
            
            duration = time.time() - start_time
            
            # Verify output was created
            if success:
                if input_ext == '.iso':
                    # Enhanced verification for ISO files
                    output_ext = '.flac' if self.mode == 'iso_dsf_to_flac' else '.dsf'
                    output_files = list(output_path.parent.glob(f'*{output_ext}'))
                    
                    # Filter to only newly created files (non-empty, reasonable size)
                    valid_files = [f for f in output_files if f.exists() and f.stat().st_size > 100]
                    
                    if not valid_files:
                        return False, "Conversion completed but no output files found", duration, None
                    
                    # Verify expected track count if available
                    if expected_track_count > 0 and len(valid_files) != expected_track_count:
                        return False, (
                            f"Track count mismatch: expected {expected_track_count}, "
                            f"found {len(valid_files)} files"
                        ), duration, None
                else:
                    # For non-ISO files, verify single output file exists
                    if not output_path.exists():
                        return False, "Conversion completed but output file not found", duration, None
                    
                    # Verify output file is not empty
                    if output_path.stat().st_size == 0:
                        return False, "Conversion completed but output file is empty", duration, None
            
            # Calculate dynamic range if enabled and conversion successful
            dynamic_range = None
            if success and self.calculate_dynamic_range and output_path.exists():
                dynamic_range = self.calculate_dynamic_range_metrics(output_path)
            
            return success, error, duration, dynamic_range
            
        except Exception as e:
            duration = time.time() - start_time
            return False, f"Unexpected error: {e}", duration, None
    
    def _convert_dsf_to_flac(
        self,
        input_path: Path,
        output_path: Path
    ) -> Tuple[bool, Optional[str]]:
        """
        Convert DSF/DFF to FLAC using ffmpeg.
        Uses configurable resampling settings for high-quality conversion.
        
        Args:
            input_path: Input DSF/DFF file
            output_path: Output FLAC file
            
        Returns:
            Tuple of (success, error_message)
        """
        # Build audio filter chain
        filters = []
        
        # Add resampling filter
        if self.resampler == 'soxr':
            filter_parts = [f'resampler={self.resampler}']
            if self.soxr_precision:
                filter_parts.append(f'precision={self.soxr_precision}')
            if self.dither_method and self.dither_method != 'none':
                filter_parts.append(f'dither_method={self.dither_method}')
            filters.append('aresample=' + ':'.join(filter_parts))
        elif self.resampler == 'swr':
            filters.append('aresample=resampler=swr')
        
        # Add lowpass filter if configured
        if self.lowpass_freq > 0:
            filters.append(f'lowpass={self.lowpass_freq}')
        
        # Build ffmpeg command
        cmd = [
            'ffmpeg',
            '-i', str(input_path)
        ]
        
        # Add thread count if specified
        if self.ffmpeg_threads > 0:
            cmd.extend(['-threads', str(self.ffmpeg_threads)])
        
        # Add audio filters if any
        if filters:
            cmd.extend(['-af', ','.join(filters)])
        
        # Add output options
        # Note: For DSD/DSF input, we need to use s32 or s16 format, not s24
        # FLAC encoder will handle the bit depth internally
        if self.bit_depth == 24:
            # Use s32 for 24-bit target (FLAC will use 24-bit internally)
            cmd.extend([
                '-sample_fmt', 's32',
                '-ar', str(self.sample_rate),
                '-compression_level', str(self.flac_compression_level)
            ])
        else:
            cmd.extend([
                '-sample_fmt', f's{self.bit_depth}',
                '-ar', str(self.sample_rate),
                '-compression_level', str(self.flac_compression_level)
            ])
        
        
        # Preserve metadata if configured
        if self.preserve_metadata:
            cmd.extend(['-map_metadata', '0'])
        
        # Overwrite output and add output path
        cmd.extend(['-y', str(output_path)])
        
        return self._run_ffmpeg(cmd)
    
    def _convert_flac_to_flac(
        self,
        input_path: Path,
        output_path: Path,
        source_specs: Dict[str, int]
    ) -> Tuple[bool, Optional[str]]:
        """
        Convert FLAC to FLAC with standardized settings (24-bit/88.2kHz).
        Uses configurable resampling settings for high-quality conversion.
        
        Args:
            input_path: Input FLAC file
            output_path: Output FLAC file
            source_specs: Source file specifications (sample_rate, bit_depth, channels)
            
        Returns:
            Tuple of (success, error_message)
        """
        # Build audio filter chain
        filters = []
        
        # Only add resampling filter if sample rate is different
        if source_specs['sample_rate'] != self.sample_rate:
            if self.resampler == 'soxr':
                filter_parts = [f'resampler={self.resampler}']
                if self.soxr_precision:
                    filter_parts.append(f'precision={self.soxr_precision}')
                if self.dither_method and self.dither_method != 'none':
                    filter_parts.append(f'dither_method={self.dither_method}')
                filters.append('aresample=' + ':'.join(filter_parts))
            elif self.resampler == 'swr':
                filters.append('aresample=resampler=swr')
        
        # Add lowpass filter if configured and downsampling
        # Only apply during downsampling to prevent aliasing; upsampling doesn't need it
        is_downsampling = source_specs['sample_rate'] > self.sample_rate
        if self.lowpass_freq > 0 and is_downsampling:
            filters.append(f'lowpass={self.lowpass_freq}')
        
        # Build ffmpeg command
        cmd = [
            'ffmpeg',
            '-i', str(input_path)
        ]
        
        # Add thread count if specified
        if self.ffmpeg_threads > 0:
            cmd.extend(['-threads', str(self.ffmpeg_threads)])
        
        # Add audio filters if any
        if filters:
            cmd.extend(['-af', ','.join(filters)])
        
        # Add output options
        if self.bit_depth == 24:
            # Use s32 for 24-bit target (FLAC will use 24-bit internally)
            cmd.extend([
                '-sample_fmt', 's32',
                '-ar', str(self.sample_rate),
                '-compression_level', str(self.flac_compression_level)
            ])
        else:
            cmd.extend([
                '-sample_fmt', f's{self.bit_depth}',
                '-ar', str(self.sample_rate),
                '-compression_level', str(self.flac_compression_level)
            ])
        
        # Preserve metadata if configured
        if self.preserve_metadata:
            cmd.extend(['-map_metadata', '0'])
        
        # Overwrite output and add output path
        cmd.extend(['-y', str(output_path)])
        
        return self._run_ffmpeg(cmd)
    
    def _extract_iso_to_dsf(
        self,
        input_path: Path,
        temp_dir: Path
    ) -> Tuple[bool, Optional[str], List[Path], Optional[Path]]:
        """
        Extract DSD audio from SACD ISO to DSF files using sacd_extract.
        
        Args:
            input_path: Input ISO file
            temp_dir: Temporary directory for extraction
            
        Returns:
            Tuple of (success, error_message, list_of_extracted_dsf_files, metadata_file_path)
        """
        if not self.has_sacd_extract:
            return False, "sacd_extract not found. Install it to process ISO files.", [], None
        
        try:
            # Extract stereo tracks to DSF format
            # -i: input ISO file
            # -s: extract stereo tracks
            # -c: convert to DSF format
            # -p: output directory
            cmd = [
                'sacd_extract',
                '-i', str(input_path.resolve()),  # Use absolute path
                '-s',  # stereo tracks
                '-c',  # convert to DSF
                '-p', str(temp_dir.resolve())  # Use absolute path
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=1800,  # 30 minute timeout for large ISOs
                cwd=str(temp_dir)  # Run in temp directory so sacd_extract writes there
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                return False, f"sacd_extract failed: {error_msg}", [], None
            
            # Find all extracted DSF files (sacd_extract creates them in a subdirectory)
            dsf_files = sorted(temp_dir.rglob('*.dsf'))
            
            if not dsf_files:
                # Debug: show what we found and the sacd_extract output
                all_files = list(temp_dir.rglob('*'))
                return False, f"No DSF files were extracted from ISO. Found {len(all_files)} files in temp dir. Output: {result.stdout[:200]}", [], None
            
            # Look for SACD metadata text files
            metadata_file = None
            txt_files = list(temp_dir.rglob('*.txt'))
            for txt_file in txt_files:
                # Check if it contains SACD metadata markers
                try:
                    with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(1000)
                        if any(marker in content for marker in ['Disc Information:', 'Album Information:', 'Track list']):
                            metadata_file = txt_file
                            break
                except Exception:
                    continue
            
            return True, None, dsf_files, metadata_file
            
        except subprocess.TimeoutExpired:
            return False, "ISO extraction timeout (exceeded 30 minutes)", [], None
        except Exception as e:
            return False, f"Error extracting ISO: {e}", [], None
    
    def _convert_iso_to_flac(
        self,
        input_path: Path,
        output_path: Path
    ) -> Tuple[bool, Optional[str], int]:
        """
        Convert ISO (SACD) to FLAC using sacd_extract + ffmpeg.
        
        This method:
        1. Extracts DSD audio from ISO to DSF files (using sacd_extract)
        2. Converts ALL DSF files to FLAC (handles multi-track ISOs)
        3. Creates properly named output files for each track
        
        Args:
            input_path: Input ISO file
            output_path: Output FLAC file (used as base path for multi-track)
            
        Returns:
            Tuple of (success, error_message, expected_track_count)
        """
        # Create temporary directory for extraction
        # Note: The context manager ensures cleanup on normal exit or exceptions,
        # but temp directories may accumulate if process receives SIGKILL.
        # Cleanup can be done manually: rm -rf /tmp/sacd_extract_*
        with tempfile.TemporaryDirectory(prefix='sacd_extract_') as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            
            # Extract ISO to DSF files
            success, error, dsf_files, metadata_file = self._extract_iso_to_dsf(input_path, temp_dir)
            
            if not success:
                return False, error, 0
            
            track_count = len(dsf_files)
            
            # Handle multi-track ISOs
            if track_count > 1:
                # Convert each track to its own FLAC file
                all_success = True
                errors = []
                
                for dsf_file in dsf_files:
                    # Use the DSF filename for the FLAC output
                    # e.g., "01 - II B.S.dsf" -> "01 - II B.S.flac"
                    track_output_path = output_path.parent / dsf_file.name.replace('.dsf', '.flac')
                    
                    track_success, track_error = self._convert_dsf_to_flac(dsf_file, track_output_path)
                    
                    if not track_success:
                        all_success = False
                        errors.append(f"{dsf_file.name}: {track_error}")
                
                if not all_success:
                    return False, f"Failed to convert {len(errors)} tracks: {'; '.join(errors[:3])}", track_count
                
                return True, None, track_count
            else:
                # Single track ISO - use the provided output path
                dsf_success, dsf_error = self._convert_dsf_to_flac(dsf_files[0], output_path)
                return dsf_success, dsf_error, track_count
    
    def _convert_iso_to_dsf(
        self,
        input_path: Path,
        output_path: Path
    ) -> Tuple[bool, Optional[str]]:
        """
        Convert ISO (SACD) to DSF using sacd_extract.
        
        This extracts the DSD audio directly from the ISO to DSF format,
        then copies the first extracted file to the output path.
        
        Args:
            input_path: Input ISO file
            output_path: Output DSF file
            
        Returns:
            Tuple of (success, error_message)
        """
        # Create temporary directory for extraction
        # Note: The context manager ensures cleanup on normal exit or exceptions,
        # but temp directories may accumulate if process receives SIGKILL.
        # Cleanup can be done manually: rm -rf /tmp/sacd_extract_*
        with tempfile.TemporaryDirectory(prefix='sacd_extract_') as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            
            # Extract ISO to DSF files
            success, error, dsf_files, metadata_file = self._extract_iso_to_dsf(input_path, temp_dir)
            
            if not success:
                return False, error
            
            # Copy the first extracted DSF file to output location
            try:
                shutil.copy2(dsf_files[0], output_path)
                return True, None
            except Exception as e:
                return False, f"Error copying extracted DSF: {e}"
    
    def _run_ffmpeg(self, cmd: list) -> Tuple[bool, Optional[str]]:
        """
        Run ffmpeg command.
        
        Args:
            cmd: Command list
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Run ffmpeg
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3600  # 1 hour timeout for large files
            )
            
            if result.returncode == 0:
                return True, None
            else:
                # Extract error from stderr
                error_lines = result.stderr.split('\n')
                # Get last few non-empty lines
                error_msg = '\n'.join([
                    line for line in error_lines[-10:]
                    if line.strip()
                ])
                return False, f"ffmpeg error: {error_msg}"
                
        except subprocess.TimeoutExpired:
            return False, "Conversion timeout (exceeded 1 hour)"
        except FileNotFoundError:
            return False, "ffmpeg not found"
        except Exception as e:
            return False, f"Error running ffmpeg: {e}"
    
    def get_file_info(self, file_path: Path) -> Optional[dict]:
        """
        Get audio file information using ffprobe.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Dictionary with file info or None on error
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(file_path)
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                import json
                return json.loads(result.stdout)
            else:
                return None
                
        except Exception:
            return None
    
    def _get_flac_specs(self, file_path: Path) -> Optional[Dict[str, int]]:
        """
        Get FLAC file specifications (sample rate, bit depth, channels).
        
        Args:
            file_path: Path to FLAC file
            
        Returns:
            Dictionary with 'sample_rate', 'bit_depth', 'channels' or None on error
        """
        try:
            file_info = self.get_file_info(file_path)
            if not file_info or 'streams' not in file_info:
                return None
            
            # Find the audio stream
            audio_stream = next(
                (s for s in file_info['streams'] if s['codec_type'] == 'audio'),
                None
            )
            
            if not audio_stream:
                return None
            
            # Extract specifications
            sample_rate = int(audio_stream.get('sample_rate', 0))
            
            # Try to get bit depth from multiple possible fields
            bit_depth = None
            if 'bits_per_sample' in audio_stream:
                bit_depth = int(audio_stream['bits_per_sample'])
            elif 'bits_per_raw_sample' in audio_stream:
                bit_depth = int(audio_stream['bits_per_raw_sample'])
            
            channels = int(audio_stream.get('channels', 2))
            
            if sample_rate > 0 and bit_depth and bit_depth > 0:
                return {
                    'sample_rate': sample_rate,
                    'bit_depth': bit_depth,
                    'channels': channels
                }
            
            return None
            
        except Exception as e:
            print(f"Warning: Error getting FLAC specs: {e}")
            return None
    
    def estimate_output_size(
        self,
        input_path: Path,
        compression_ratio: float = 0.5
    ) -> int:
        """
        Estimate output file size.
        
        Args:
            input_path: Input file path
            compression_ratio: Estimated compression ratio (0-1)
            
        Returns:
            Estimated size in bytes
        """
        if not input_path.exists():
            return 0
        
        input_size = input_path.stat().st_size
        
        # For DSD to PCM/FLAC conversion, estimate based on:
        # - DSD is 1-bit at high sample rate (e.g., 2.8 MHz)
        # - PCM is multi-bit at lower sample rate (e.g., 24-bit at 88.2 kHz)
        # - FLAC provides ~50% compression
        
        if self.mode == "iso_dsf_to_flac":
            # Rough estimate: similar size or slightly smaller
            return int(input_size * compression_ratio)
        else:
            # ISO to DSF might be similar size
            return int(input_size * 0.8)
    
    def calculate_dynamic_range_metrics(
        self,
        audio_file: Path,
        max_file_size_mb: int = 500
    ) -> Optional[Dict[str, float]]:
        """
        Calculate dynamic range metrics for an audio file.
        
        Calculates:
        - Crest factor (peak to RMS ratio in dB)
        - R128 loudness range (if pyloudnorm is available)
        
        Note: This method loads the entire audio file into memory for analysis.
        Files larger than max_file_size_mb will be skipped to prevent memory exhaustion.
        
        Args:
            audio_file: Path to audio file (FLAC or other format supported by ffmpeg)
            max_file_size_mb: Maximum file size in MB to process (default: 500MB)
            
        Returns:
            Dict with dynamic_range_crest and dynamic_range_r128, or None if calculation fails
        """
        try:
            # Check file size to prevent memory exhaustion
            # A 1-hour 24/96 stereo file is ~2.5 GB of raw PCM data in memory
            if not audio_file.exists():
                return None
                
            file_size_mb = audio_file.stat().st_size / (1024 * 1024)
            if file_size_mb > max_file_size_mb:
                print(f"Warning: Skipping DR calculation for {audio_file.name} "
                      f"({file_size_mb:.1f}MB exceeds {max_file_size_mb}MB limit)")
                return None
            
            # Extract raw audio data using ffmpeg
            cmd = [
                'ffmpeg',
                '-i', str(audio_file),
                '-f', 'f32le',  # 32-bit float PCM
                '-acodec', 'pcm_f32le',
                '-ac', '2',  # Stereo
                '-'
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                print(f"Warning: Could not extract audio data for DR calculation")
                return None
            
            # Convert bytes to numpy array
            audio_data = np.frombuffer(result.stdout, dtype=np.float32)
            
            if len(audio_data) == 0:
                return None
            
            # Reshape to stereo (2 channels)
            try:
                audio_data = audio_data.reshape(-1, 2)
            except ValueError:
                # If reshape fails, audio might be mono or different channel count
                # Try to work with it as-is
                pass
            
            # Calculate crest factor
            # Crest factor = 20 * log10(peak / RMS)
            peak = np.abs(audio_data).max()
            rms = np.sqrt(np.mean(audio_data ** 2))
            
            if rms > 0:
                crest_db = 20 * np.log10(peak / rms)
            else:
                crest_db = None
            
            # Calculate R128 loudness range if pyloudnorm is available
            r128_range = None
            if pyln is not None:
                try:
                    # Get sample rate from file info
                    file_info = self.get_file_info(audio_file)
                    if file_info and 'streams' in file_info:
                        audio_stream = next(
                            (s for s in file_info['streams'] if s['codec_type'] == 'audio'),
                            None
                        )
                        if audio_stream:
                            sample_rate = int(audio_stream.get('sample_rate', self.sample_rate))
                            
                            # Create loudness meter
                            meter = pyln.Meter(sample_rate)
                            
                            # Measure integrated loudness
                            loudness = meter.integrated_loudness(audio_data)
                            
                            # For R128 range, we calculate the difference between
                            # loudest and quietest moments (simplified approach)
                            # A proper implementation would use the EBU R128 algorithm
                            # Here we use the standard deviation as a proxy
                            if audio_data.ndim > 1:
                                # Average channels
                                mono = np.mean(audio_data, axis=1)
                            else:
                                mono = audio_data
                            
                            # Calculate RMS in overlapping windows
                            window_size = sample_rate  # 1 second windows
                            hop_size = window_size // 2
                            
                            rms_values = []
                            for i in range(0, len(mono) - window_size, hop_size):
                                window = mono[i:i+window_size]
                                window_rms = np.sqrt(np.mean(window ** 2))
                                if window_rms > 0:
                                    rms_values.append(20 * np.log10(window_rms))
                            
                            if len(rms_values) > 1:
                                # R128 range is approximately the range between percentiles
                                rms_values = np.array(rms_values)
                                p10 = np.percentile(rms_values, 10)
                                p95 = np.percentile(rms_values, 95)
                                r128_range = p95 - p10
                
                except Exception as e:
                    print(f"Warning: R128 calculation failed: {e}")
                    r128_range = None
            
            return {
                'dynamic_range_crest': float(round(crest_db, 2)) if crest_db is not None else None,
                'dynamic_range_r128': float(round(r128_range, 2)) if r128_range is not None else None
            }
        
        except subprocess.TimeoutExpired:
            print(f"Warning: DR calculation timeout for {audio_file}")
            return None
        except Exception as e:
            print(f"Warning: Error calculating dynamic range: {e}")
            return None

