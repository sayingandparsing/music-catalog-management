"""
Unit tests for logger module (ConversionLogger, ColoredFormatter, setup_logger).
"""

import pytest
import logging
from pathlib import Path
from logger import ConversionLogger, ColoredFormatter, setup_logger


class TestColoredFormatter:
    """Tests for ColoredFormatter class."""
    
    def test_colored_formatter_creation(self):
        """Test creating a ColoredFormatter."""
        formatter = ColoredFormatter('%(levelname)s - %(message)s')
        
        assert formatter is not None
    
    def test_format_with_colors(self):
        """Test that formatter adds color codes."""
        formatter = ColoredFormatter('%(levelname)s - %(message)s')
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        
        # Should contain ANSI color codes
        assert '\033[' in formatted
        assert 'Test message' in formatted
    
    def test_format_different_levels(self):
        """Test formatting different log levels."""
        formatter = ColoredFormatter('%(levelname)s')
        
        levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        
        for level_name in levels:
            record = logging.LogRecord(
                name='test',
                level=getattr(logging, level_name),
                pathname='',
                lineno=0,
                msg='',
                args=(),
                exc_info=None
            )
            
            formatted = formatter.format(record)
            # Should have formatted the level name
            assert formatted is not None


class TestConversionLoggerInitialization:
    """Tests for ConversionLogger initialization."""
    
    def test_logger_init(self, temp_log_files):
        """Test ConversionLogger initialization."""
        log_file, error_log_file = temp_log_files
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file,
            level='INFO'
        )
        
        assert logger.log_file == log_file
        assert logger.error_log_file == error_log_file
        assert logger.level == logging.INFO
        assert logger.console_timestamps is True
    
    def test_logger_init_creates_directories(self, temp_dir):
        """Test that logger creates log directories."""
        log_file = temp_dir / "logs" / "test.log"
        error_log_file = temp_dir / "logs" / "errors.log"
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file
        )
        
        assert log_file.parent.exists()
        assert error_log_file.parent.exists()
    
    def test_logger_different_levels(self, temp_log_files):
        """Test logger with different log levels."""
        log_file, error_log_file = temp_log_files
        
        levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        
        for level_str in levels:
            logger = ConversionLogger(
                log_file=log_file,
                error_log_file=error_log_file,
                level=level_str
            )
            
            assert logger.level == getattr(logging, level_str)
    
    def test_logger_without_console_timestamps(self, temp_log_files):
        """Test logger without console timestamps."""
        log_file, error_log_file = temp_log_files
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file,
            console_timestamps=False
        )
        
        assert logger.console_timestamps is False
    
    def test_logger_clears_existing_handlers(self, temp_log_files):
        """Test that logger clears existing handlers."""
        log_file, error_log_file = temp_log_files
        
        logger1 = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file
        )
        
        # Create second logger with same name
        logger2 = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file
        )
        
        # Should have exactly 3 handlers (console, file, error_file)
        assert len(logger2.logger.handlers) == 3


class TestLogMethods:
    """Tests for basic log methods."""
    
    def test_debug_logging(self, temp_log_files):
        """Test debug logging."""
        log_file, error_log_file = temp_log_files
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file,
            level='DEBUG'
        )
        
        logger.debug("Test debug message")
        
        # Check that message was written to log file
        log_content = log_file.read_text()
        assert "Test debug message" in log_content
        assert "DEBUG" in log_content
    
    def test_info_logging(self, temp_log_files):
        """Test info logging."""
        log_file, error_log_file = temp_log_files
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file
        )
        
        logger.info("Test info message")
        
        log_content = log_file.read_text()
        assert "Test info message" in log_content
        assert "INFO" in log_content
    
    def test_warning_logging(self, temp_log_files):
        """Test warning logging."""
        log_file, error_log_file = temp_log_files
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file
        )
        
        logger.warning("Test warning message")
        
        log_content = log_file.read_text()
        assert "Test warning message" in log_content
        assert "WARNING" in log_content
    
    def test_error_logging(self, temp_log_files):
        """Test error logging."""
        log_file, error_log_file = temp_log_files
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file
        )
        
        logger.error("Test error message")
        
        # Error should be in both log files
        log_content = log_file.read_text()
        error_content = error_log_file.read_text()
        
        assert "Test error message" in log_content
        assert "Test error message" in error_content
        assert "ERROR" in log_content
    
    def test_critical_logging(self, temp_log_files):
        """Test critical logging."""
        log_file, error_log_file = temp_log_files
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file
        )
        
        logger.critical("Test critical message")
        
        # Critical should be in both log files
        log_content = log_file.read_text()
        error_content = error_log_file.read_text()
        
        assert "Test critical message" in log_content
        assert "Test critical message" in error_content
        assert "CRITICAL" in log_content
    
    def test_error_with_exc_info(self, temp_log_files):
        """Test error logging with exception info."""
        log_file, error_log_file = temp_log_files
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file
        )
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            logger.error("Error occurred", exc_info=True)
        
        log_content = log_file.read_text()
        
        assert "Error occurred" in log_content
        assert "ValueError" in log_content
        assert "Traceback" in log_content


class TestStructuredLogging:
    """Tests for structured logging methods."""
    
    def test_log_conversion_start(self, temp_log_files, temp_dir):
        """Test log_conversion_start method."""
        log_file, error_log_file = temp_log_files
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file
        )
        
        input_dir = temp_dir / "input"
        output_dir = temp_dir / "output"
        archive_dir = temp_dir / "archive"
        
        logger.log_conversion_start(input_dir, output_dir, archive_dir)
        
        log_content = log_file.read_text()
        
        assert "Starting Conversion Process" in log_content
        assert str(input_dir) in log_content
        assert str(output_dir) in log_content
        assert str(archive_dir) in log_content
    
    def test_log_conversion_end_success(self, temp_log_files):
        """Test log_conversion_end with success."""
        log_file, error_log_file = temp_log_files
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file
        )
        
        stats = {
            'albums_processed': 5,
            'albums_skipped': 1,
            'files_converted': 20,
            'files_failed': 2,
            'duration': '01:23:45'
        }
        
        logger.log_conversion_end(success=True, stats=stats)
        
        log_content = log_file.read_text()
        
        assert "Successfully" in log_content
        assert "5" in log_content  # albums_processed
        assert "20" in log_content  # files_converted
        assert "01:23:45" in log_content  # duration
    
    def test_log_conversion_end_failure(self, temp_log_files):
        """Test log_conversion_end with failure."""
        log_file, error_log_file = temp_log_files
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file
        )
        
        logger.log_conversion_end(success=False)
        
        log_content = log_file.read_text()
        
        assert "Errors" in log_content
    
    def test_log_album_start(self, temp_log_files, temp_dir):
        """Test log_album_start method."""
        log_file, error_log_file = temp_log_files
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file
        )
        
        album_path = temp_dir / "Test Album"
        album_path.mkdir()
        
        logger.log_album_start(album_path, 1, 5)
        
        log_content = log_file.read_text()
        
        assert "[1/5]" in log_content
        assert "Test Album" in log_content
        assert "Processing album" in log_content
    
    def test_log_album_end_success(self, temp_log_files, temp_dir):
        """Test log_album_end with success."""
        log_file, error_log_file = temp_log_files
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file
        )
        
        album_path = temp_dir / "Test Album"
        album_path.mkdir()
        
        logger.log_album_end(album_path, success=True, files_converted=10)
        
        log_content = log_file.read_text()
        
        assert "completed" in log_content
        assert "Test Album" in log_content
        assert "10 files" in log_content
    
    def test_log_album_end_failure(self, temp_log_files, temp_dir):
        """Test log_album_end with failure."""
        log_file, error_log_file = temp_log_files
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file
        )
        
        album_path = temp_dir / "Test Album"
        album_path.mkdir()
        
        logger.log_album_end(album_path, success=False, files_converted=0)
        
        log_content = log_file.read_text()
        error_content = error_log_file.read_text()
        
        assert "failed" in log_content
        assert "Test Album" in error_content
    
    def test_log_file_conversion_success(self, temp_log_files, temp_dir):
        """Test log_file_conversion with success."""
        log_file, error_log_file = temp_log_files
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file
        )
        
        input_file = temp_dir / "input.dsf"
        output_file = temp_dir / "output.flac"
        
        logger.log_file_conversion(
            input_file,
            output_file,
            success=True,
            duration=12.5
        )
        
        log_content = log_file.read_text()
        
        assert "input.dsf" in log_content
        assert "output.flac" in log_content
        assert "12.5s" in log_content
    
    def test_log_file_conversion_failure(self, temp_log_files, temp_dir):
        """Test log_file_conversion with failure."""
        log_file, error_log_file = temp_log_files
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file
        )
        
        input_file = temp_dir / "input.dsf"
        output_file = temp_dir / "output.flac"
        
        logger.log_file_conversion(
            input_file,
            output_file,
            success=False
        )
        
        log_content = log_file.read_text()
        error_content = error_log_file.read_text()
        
        assert "Failed" in log_content
        assert "input.dsf" in log_content


class TestGetLogger:
    """Tests for get_logger method."""
    
    def test_get_logger(self, temp_log_files):
        """Test getting the underlying logger instance."""
        log_file, error_log_file = temp_log_files
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file
        )
        
        underlying_logger = logger.get_logger()
        
        assert isinstance(underlying_logger, logging.Logger)
        assert underlying_logger.name == "music_converter"


class TestSetupLogger:
    """Tests for setup_logger function."""
    
    def test_setup_logger_default(self, temp_dir):
        """Test setup_logger with default parameters."""
        log_file = str(temp_dir / "test.log")
        error_log_file = str(temp_dir / "test_errors.log")
        
        logger = setup_logger(
            log_file=log_file,
            error_log_file=error_log_file
        )
        
        assert isinstance(logger, ConversionLogger)
        assert logger.level == logging.INFO
        assert logger.console_timestamps is True
    
    def test_setup_logger_custom_level(self, temp_dir):
        """Test setup_logger with custom log level."""
        log_file = str(temp_dir / "test.log")
        error_log_file = str(temp_dir / "test_errors.log")
        
        logger = setup_logger(
            log_file=log_file,
            error_log_file=error_log_file,
            level='DEBUG'
        )
        
        assert logger.level == logging.DEBUG
    
    def test_setup_logger_no_timestamps(self, temp_dir):
        """Test setup_logger without console timestamps."""
        log_file = str(temp_dir / "test.log")
        error_log_file = str(temp_dir / "test_errors.log")
        
        logger = setup_logger(
            log_file=log_file,
            error_log_file=error_log_file,
            console_timestamps=False
        )
        
        assert logger.console_timestamps is False


class TestLogFiltering:
    """Tests for log level filtering."""
    
    def test_console_filtering(self, temp_log_files):
        """Test that console handler respects log level."""
        log_file, error_log_file = temp_log_files
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file,
            level='WARNING'
        )
        
        # Log messages at different levels
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        
        # All should be in file (file handler is DEBUG level)
        log_content = log_file.read_text()
        assert "Debug message" in log_content
        assert "Info message" in log_content
        assert "Warning message" in log_content
    
    def test_error_file_filtering(self, temp_log_files):
        """Test that error file only contains errors and above."""
        log_file, error_log_file = temp_log_files
        
        logger = ConversionLogger(
            log_file=log_file,
            error_log_file=error_log_file
        )
        
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        
        # Error file should only have error message
        error_content = error_log_file.read_text()
        assert "Debug message" not in error_content
        assert "Info message" not in error_content
        assert "Warning message" not in error_content
        assert "Error message" in error_content


class TestMultipleLoggerInstances:
    """Tests for multiple logger instances."""
    
    def test_multiple_loggers_different_files(self, temp_dir):
        """Test creating multiple loggers with different files."""
        log1 = temp_dir / "log1.log"
        error1 = temp_dir / "error1.log"
        log2 = temp_dir / "log2.log"
        error2 = temp_dir / "error2.log"
        
        logger1 = ConversionLogger(log1, error1)
        logger2 = ConversionLogger(log2, error2)
        
        logger1.info("Message to logger1")
        logger2.info("Message to logger2")
        
        # Messages should go to respective files
        assert "Message to logger1" in log1.read_text()
        assert "Message to logger2" in log2.read_text()

