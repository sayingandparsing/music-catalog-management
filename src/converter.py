"""
Audio converter for DSD music files.
Uses ffmpeg for conversion from ISO/DSF to FLAC or DSF.
"""

import subprocess
import shutil
from pathlib import Path
from typing import Optional, Tuple
import time


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
        ffmpeg_threads: int = 0
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
        """
        self.sample_rate = sample_rate
        self.bit_depth = bit_depth
        self.mode = mode
        self.resampler = resampler
        self.soxr_precision = soxr_precision
        self.dither_method = dither_method
        self.lowpass_freq = lowpass_freq
        self.flac_compression_level = flac_compression_level
        self.preserve_metadata = preserve_metadata
        self.ffmpeg_threads = ffmpeg_threads
        
        # Verify ffmpeg is available
        if not self._check_ffmpeg():
            raise RuntimeError(
                "ffmpeg not found. Please install ffmpeg to use this tool."
            )
    
    def _check_ffmpeg(self) -> bool:
        """
        Check if ffmpeg is available.
        
        Returns:
            True if ffmpeg is available
        """
        return shutil.which('ffmpeg') is not None
    
    def convert_file(
        self,
        input_path: Path,
        output_path: Path,
        overwrite: bool = False
    ) -> Tuple[bool, Optional[str], float]:
        """
        Convert a single audio file.
        
        Args:
            input_path: Input file path
            output_path: Output file path
            overwrite: Whether to overwrite existing output file
            
        Returns:
            Tuple of (success, error_message, duration_seconds)
        """
        # Validate input
        if not input_path.exists():
            return False, f"Input file not found: {input_path}", 0.0
        
        # Check output
        if output_path.exists() and not overwrite:
            return False, f"Output file already exists: {output_path}", 0.0
        
        # Create output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Determine conversion based on file type and mode
        input_ext = input_path.suffix.lower()
        
        start_time = time.time()
        
        try:
            if self.mode == "iso_dsf_to_flac":
                if input_ext in ['.iso']:
                    success, error = self._convert_iso_to_flac(input_path, output_path)
                elif input_ext in ['.dsf', '.dff']:
                    success, error = self._convert_dsf_to_flac(input_path, output_path)
                else:
                    return False, f"Unsupported input format: {input_ext}", 0.0
            
            elif self.mode == "iso_to_dsf":
                if input_ext in ['.iso']:
                    success, error = self._convert_iso_to_dsf(input_path, output_path)
                else:
                    return False, f"Unsupported input format for iso_to_dsf: {input_ext}", 0.0
            
            else:
                return False, f"Unknown conversion mode: {self.mode}", 0.0
            
            duration = time.time() - start_time
            
            # Verify output was created
            if success and not output_path.exists():
                return False, "Conversion completed but output file not found", duration
            
            return success, error, duration
            
        except Exception as e:
            duration = time.time() - start_time
            return False, f"Unexpected error: {e}", duration
    
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
    
    def _convert_iso_to_flac(
        self,
        input_path: Path,
        output_path: Path
    ) -> Tuple[bool, Optional[str]]:
        """
        Convert ISO (SACD) to FLAC using ffmpeg.
        Uses configurable resampling settings for high-quality conversion.
        
        Note: ISO files may contain multiple streams/tracks.
        This extracts the first audio stream.
        
        Args:
            input_path: Input ISO file
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
            '-i', str(input_path),
            '-map', '0:a:0'  # Select first audio stream
        ]
        
        # Add thread count if specified
        if self.ffmpeg_threads > 0:
            cmd.extend(['-threads', str(self.ffmpeg_threads)])
        
        # Add audio filters if any
        if filters:
            cmd.extend(['-af', ','.join(filters)])
        
        # Add output options
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
    
    def _convert_iso_to_dsf(
        self,
        input_path: Path,
        output_path: Path
    ) -> Tuple[bool, Optional[str]]:
        """
        Convert ISO (SACD) to DSF using ffmpeg.
        
        Args:
            input_path: Input ISO file
            output_path: Output DSF file
            
        Returns:
            Tuple of (success, error_message)
        """
        cmd = [
            'ffmpeg',
            '-i', str(input_path),
            '-map', '0:a:0',  # Select first audio stream
        ]
        
        # Add thread count if specified
        if self.ffmpeg_threads > 0:
            cmd.extend(['-threads', str(self.ffmpeg_threads)])
        
        cmd.extend([
            '-c:a', 'dsd_lsbf_planar',  # DSD codec
            '-y',
            str(output_path)
        ])
        
        return self._run_ffmpeg(cmd)
    
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

