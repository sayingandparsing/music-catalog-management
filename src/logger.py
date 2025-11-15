"""
Logging configuration for DSD Music Converter.
Provides console and file logging with progress tracking.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        """Format log record with colors."""
        if record.levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelname]}"
                f"{record.levelname}"
                f"{self.RESET}"
            )
        return super().format(record)


class ConversionLogger:
    """
    Logger for the music conversion process.
    Manages both console and file logging.
    """
    
    def __init__(
        self,
        log_file: Path,
        error_log_file: Path,
        level: str = "INFO",
        console_timestamps: bool = True
    ):
        """
        Initialize logging.
        
        Args:
            log_file: Path to main log file
            error_log_file: Path to error log file
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            console_timestamps: Include timestamps in console output
        """
        self.log_file = Path(log_file)
        self.error_log_file = Path(error_log_file)
        self.level = getattr(logging, level.upper())
        self.console_timestamps = console_timestamps
        
        # Create log directory if needed
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.error_log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Set up logger
        self.logger = logging.getLogger("music_converter")
        self.logger.setLevel(logging.DEBUG)  # Capture all levels
        self.logger.handlers = []  # Clear any existing handlers
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Set up logging handlers for console and files."""
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.level)
        
        if self.console_timestamps:
            console_format = '%(asctime)s - %(levelname)s - %(message)s'
        else:
            console_format = '%(levelname)s - %(message)s'
        
        console_formatter = ColoredFormatter(
            console_format,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # Main file handler (all logs)
        file_handler = logging.FileHandler(self.log_file, mode='a')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Error file handler (errors and critical only)
        error_handler = logging.FileHandler(self.error_log_file, mode='a')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        self.logger.addHandler(error_handler)
    
    def debug(self, message: str):
        """Log debug message."""
        self.logger.debug(message)
    
    def info(self, message: str):
        """Log info message."""
        self.logger.info(message)
    
    def warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)
    
    def error(self, message: str, exc_info: bool = False):
        """
        Log error message.
        
        Args:
            message: Error message
            exc_info: Include exception traceback
        """
        self.logger.error(message, exc_info=exc_info)
    
    def critical(self, message: str, exc_info: bool = False):
        """
        Log critical message.
        
        Args:
            message: Critical message
            exc_info: Include exception traceback
        """
        self.logger.critical(message, exc_info=exc_info)
    
    def log_conversion_start(self, input_dir: Path, output_dir: Path, archive_dir: Path):
        """Log conversion process start."""
        self.info("=" * 70)
        self.info("DSD MUSIC CONVERTER - Starting Conversion Process")
        self.info("=" * 70)
        self.info(f"Input Directory:   {input_dir}")
        self.info(f"Output Directory:  {output_dir}")
        self.info(f"Archive Directory: {archive_dir}")
        self.info(f"Started at:        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.info("=" * 70)
    
    def log_conversion_end(self, success: bool, stats: Optional[dict] = None):
        """
        Log conversion process end.
        
        Args:
            success: Whether conversion completed successfully
            stats: Optional statistics dictionary
        """
        self.info("=" * 70)
        if success:
            self.info("DSD MUSIC CONVERTER - Conversion Completed Successfully")
        else:
            self.info("DSD MUSIC CONVERTER - Conversion Ended with Errors")
        
        if stats:
            self.info(f"Albums Processed:  {stats.get('albums_processed', 0)}")
            self.info(f"Albums Skipped:    {stats.get('albums_skipped', 0)}")
            self.info(f"Files Converted:   {stats.get('files_converted', 0)}")
            self.info(f"Files Failed:      {stats.get('files_failed', 0)}")
            self.info(f"Total Duration:    {stats.get('duration', 'N/A')}")
        
        self.info(f"Ended at:          {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.info("=" * 70)
    
    def log_album_start(self, album_path: Path, album_num: int, total_albums: int):
        """Log album processing start."""
        self.info("")
        self.info(f"[{album_num}/{total_albums}] Processing album: {album_path.name}")
        self.info("-" * 70)
    
    def log_album_end(self, album_path: Path, success: bool, files_converted: int):
        """Log album processing end."""
        if success:
            self.info(f"✓ Album completed: {album_path.name} ({files_converted} files)")
        else:
            self.error(f"✗ Album failed: {album_path.name}")
        self.info("-" * 70)
    
    def log_file_conversion(
        self,
        file_path: Path,
        output_path: Path,
        success: bool,
        duration: Optional[float] = None
    ):
        """
        Log individual file conversion.
        
        Args:
            file_path: Source file path
            output_path: Output file path
            success: Whether conversion succeeded
            duration: Conversion duration in seconds
        """
        if success:
            duration_str = f" ({duration:.1f}s)" if duration else ""
            self.info(f"  ✓ {file_path.name} -> {output_path.name}{duration_str}")
        else:
            self.error(f"  ✗ Failed: {file_path.name}")
    
    def get_logger(self) -> logging.Logger:
        """Get the underlying logger instance."""
        return self.logger


def setup_logger(
    log_file: str = "conversion.log",
    error_log_file: str = "conversion_errors.log",
    level: str = "INFO",
    console_timestamps: bool = True
) -> ConversionLogger:
    """
    Set up and return a configured logger.
    
    Args:
        log_file: Path to main log file
        error_log_file: Path to error log file
        level: Logging level
        console_timestamps: Include timestamps in console output
        
    Returns:
        Configured ConversionLogger instance
    """
    return ConversionLogger(
        Path(log_file),
        Path(error_log_file),
        level,
        console_timestamps
    )

