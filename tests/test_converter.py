"""
Unit tests for converter module (AudioConverter class).
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from converter import AudioConverter, ConversionError


class TestAudioConverterInitialization:
    """Tests for AudioConverter initialization."""
    
    def test_converter_init_default(self, mock_ffmpeg_available):
        """Test converter initialization with default values."""
        converter = AudioConverter()
        
        assert converter.sample_rate == 88200
        assert converter.bit_depth == 24
        assert converter.mode == "iso_dsf_to_flac"
        assert converter.resampler == "soxr"
        assert converter.soxr_precision == 28
        assert converter.dither_method == "triangular"
        assert converter.lowpass_freq == 40000
        assert converter.flac_compression_level == 8
        assert converter.preserve_metadata is True
        assert converter.ffmpeg_threads == 0
    
    def test_converter_init_custom(self, mock_ffmpeg_available):
        """Test converter initialization with custom values."""
        converter = AudioConverter(
            sample_rate=96000,
            bit_depth=16,
            mode="iso_to_dsf",
            resampler="swr",
            soxr_precision=20,
            dither_method="rectangular",
            lowpass_freq=48000,
            flac_compression_level=5,
            preserve_metadata=False,
            ffmpeg_threads=4
        )
        
        assert converter.sample_rate == 96000
        assert converter.bit_depth == 16
        assert converter.mode == "iso_to_dsf"
        assert converter.resampler == "swr"
        assert converter.soxr_precision == 20
        assert converter.dither_method == "rectangular"
        assert converter.lowpass_freq == 48000
        assert converter.flac_compression_level == 5
        assert converter.preserve_metadata is False
        assert converter.ffmpeg_threads == 4
    
    def test_converter_init_ffmpeg_not_found(self, monkeypatch):
        """Test that initialization fails when ffmpeg is not found."""
        monkeypatch.setattr("shutil.which", lambda x: None)
        
        with pytest.raises(RuntimeError, match="ffmpeg not found"):
            AudioConverter()
    
    def test_check_ffmpeg_available(self, mock_ffmpeg_available):
        """Test _check_ffmpeg method when ffmpeg is available."""
        converter = AudioConverter()
        
        assert converter._check_ffmpeg() is True
    
    def test_check_ffmpeg_not_available(self, monkeypatch):
        """Test _check_ffmpeg method when ffmpeg is not available."""
        monkeypatch.setattr("shutil.which", lambda x: None)
        
        # Can't create converter, but we can test the method indirectly
        with pytest.raises(RuntimeError):
            AudioConverter()


class TestConvertFile:
    """Tests for convert_file method."""
    
    def test_convert_file_input_not_found(self, mock_ffmpeg_available, temp_dir):
        """Test conversion when input file doesn't exist."""
        converter = AudioConverter()
        
        input_path = temp_dir / "nonexistent.dsf"
        output_path = temp_dir / "output.flac"
        
        success, error, duration = converter.convert_file(input_path, output_path)
        
        assert success is False
        assert "Input file not found" in error
        assert duration == 0.0
    
    def test_convert_file_output_exists_no_overwrite(self, mock_ffmpeg_available, temp_dir):
        """Test conversion when output exists and overwrite is False."""
        converter = AudioConverter()
        
        input_path = temp_dir / "input.dsf"
        output_path = temp_dir / "output.flac"
        
        input_path.write_text("mock input")
        output_path.write_text("existing output")
        
        success, error, duration = converter.convert_file(
            input_path, output_path, overwrite=False
        )
        
        assert success is False
        assert "already exists" in error
    
    def test_convert_file_unsupported_format(self, mock_ffmpeg_available, temp_dir):
        """Test conversion with unsupported file format."""
        converter = AudioConverter(mode="iso_dsf_to_flac")
        
        input_path = temp_dir / "input.mp3"
        output_path = temp_dir / "output.flac"
        
        input_path.write_text("mock mp3")
        
        success, error, duration = converter.convert_file(input_path, output_path)
        
        assert success is False
        assert "Unsupported input format" in error
    
    def test_convert_file_creates_output_directory(self, mock_ffmpeg_available, mock_ffmpeg_success, temp_dir):
        """Test that output directory is created if it doesn't exist."""
        converter = AudioConverter()
        
        input_path = temp_dir / "input.dsf"
        output_path = temp_dir / "nested" / "dir" / "output.flac"
        
        input_path.write_text("mock input")
        
        # Mock successful conversion
        with patch.object(converter, '_convert_dsf_to_flac', return_value=(True, None)):
            with patch.object(Path, 'exists', return_value=True):
                success, error, duration = converter.convert_file(input_path, output_path)
        
        # Output directory should be created
        assert output_path.parent.exists()
    
    def test_convert_dsf_to_flac_mode(self, mock_ffmpeg_available, temp_dir):
        """Test DSF to FLAC conversion mode."""
        converter = AudioConverter(mode="iso_dsf_to_flac")
        
        input_path = temp_dir / "track.dsf"
        output_path = temp_dir / "track.flac"
        
        input_path.write_text("mock dsf")
        
        with patch.object(converter, '_convert_dsf_to_flac', return_value=(True, None)) as mock_convert:
            with patch.object(Path, 'exists', return_value=True):
                success, error, duration = converter.convert_file(input_path, output_path)
        
        assert success is True
        mock_convert.assert_called_once_with(input_path, output_path)
    
    def test_convert_iso_to_flac_mode(self, mock_ffmpeg_available, temp_dir):
        """Test ISO to FLAC conversion mode."""
        converter = AudioConverter(mode="iso_dsf_to_flac")
        
        input_path = temp_dir / "track.iso"
        output_path = temp_dir / "track.flac"
        
        input_path.write_text("mock iso")
        
        with patch.object(converter, '_convert_iso_to_flac', return_value=(True, None)) as mock_convert:
            with patch.object(Path, 'exists', return_value=True):
                success, error, duration = converter.convert_file(input_path, output_path)
        
        assert success is True
        mock_convert.assert_called_once_with(input_path, output_path)
    
    def test_convert_iso_to_dsf_mode(self, mock_ffmpeg_available, temp_dir):
        """Test ISO to DSF conversion mode."""
        converter = AudioConverter(mode="iso_to_dsf")
        
        input_path = temp_dir / "track.iso"
        output_path = temp_dir / "track.dsf"
        
        input_path.write_text("mock iso")
        
        with patch.object(converter, '_convert_iso_to_dsf', return_value=(True, None)) as mock_convert:
            with patch.object(Path, 'exists', return_value=True):
                success, error, duration = converter.convert_file(input_path, output_path)
        
        assert success is True
        mock_convert.assert_called_once_with(input_path, output_path)
    
    def test_convert_unknown_mode(self, mock_ffmpeg_available, temp_dir):
        """Test conversion with unknown mode."""
        converter = AudioConverter(mode="iso_dsf_to_flac")
        converter.mode = "unknown_mode"
        
        input_path = temp_dir / "input.dsf"
        output_path = temp_dir / "output.flac"
        
        input_path.write_text("mock")
        
        success, error, duration = converter.convert_file(input_path, output_path)
        
        assert success is False
        assert "Unknown conversion mode" in error
    
    def test_convert_file_measures_duration(self, mock_ffmpeg_available, temp_dir):
        """Test that conversion duration is measured."""
        converter = AudioConverter()
        
        input_path = temp_dir / "input.dsf"
        output_path = temp_dir / "output.flac"
        
        input_path.write_text("mock")
        
        with patch.object(converter, '_convert_dsf_to_flac', return_value=(True, None)):
            with patch.object(Path, 'exists', return_value=True):
                success, error, duration = converter.convert_file(input_path, output_path)
        
        assert duration >= 0.0  # Should have a duration


class TestDSFToFLACConversion:
    """Tests for _convert_dsf_to_flac method."""
    
    def test_dsf_to_flac_command_generation(self, mock_ffmpeg_available, temp_dir):
        """Test that correct ffmpeg command is generated for DSF to FLAC."""
        converter = AudioConverter(
            sample_rate=88200,
            bit_depth=24,
            resampler="soxr",
            soxr_precision=28,
            dither_method="triangular",
            lowpass_freq=40000,
            flac_compression_level=8,
            preserve_metadata=True
        )
        
        input_path = temp_dir / "input.dsf"
        output_path = temp_dir / "output.flac"
        
        with patch.object(converter, '_run_ffmpeg', return_value=(True, None)) as mock_run:
            converter._convert_dsf_to_flac(input_path, output_path)
            
            # Check that _run_ffmpeg was called
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            
            # Verify command components
            assert 'ffmpeg' in cmd
            assert str(input_path) in cmd
            assert str(output_path) in cmd
            assert '-sample_fmt' in cmd
            assert 's24' in cmd
            assert '-ar' in cmd
            assert '88200' in cmd
    
    def test_dsf_to_flac_with_soxr_resampler(self, mock_ffmpeg_available, temp_dir):
        """Test DSF to FLAC with SoXR resampler settings."""
        converter = AudioConverter(resampler="soxr", soxr_precision=28)
        
        input_path = temp_dir / "input.dsf"
        output_path = temp_dir / "output.flac"
        
        with patch.object(converter, '_run_ffmpeg', return_value=(True, None)) as mock_run:
            converter._convert_dsf_to_flac(input_path, output_path)
            
            cmd = mock_run.call_args[0][0]
            cmd_str = ' '.join(cmd)
            
            assert 'aresample' in cmd_str
            assert 'resampler=soxr' in cmd_str
            assert 'precision=28' in cmd_str
    
    def test_dsf_to_flac_with_lowpass_filter(self, mock_ffmpeg_available, temp_dir):
        """Test DSF to FLAC with lowpass filter."""
        converter = AudioConverter(lowpass_freq=40000)
        
        input_path = temp_dir / "input.dsf"
        output_path = temp_dir / "output.flac"
        
        with patch.object(converter, '_run_ffmpeg', return_value=(True, None)) as mock_run:
            converter._convert_dsf_to_flac(input_path, output_path)
            
            cmd = mock_run.call_args[0][0]
            cmd_str = ' '.join(cmd)
            
            assert 'lowpass=40000' in cmd_str
    
    def test_dsf_to_flac_without_lowpass(self, mock_ffmpeg_available, temp_dir):
        """Test DSF to FLAC without lowpass filter (0 = disabled)."""
        converter = AudioConverter(lowpass_freq=0)
        
        input_path = temp_dir / "input.dsf"
        output_path = temp_dir / "output.flac"
        
        with patch.object(converter, '_run_ffmpeg', return_value=(True, None)) as mock_run:
            converter._convert_dsf_to_flac(input_path, output_path)
            
            cmd = mock_run.call_args[0][0]
            cmd_str = ' '.join(cmd)
            
            assert 'lowpass' not in cmd_str
    
    def test_dsf_to_flac_metadata_preservation(self, mock_ffmpeg_available, temp_dir):
        """Test that metadata preservation flag is included."""
        converter = AudioConverter(preserve_metadata=True)
        
        input_path = temp_dir / "input.dsf"
        output_path = temp_dir / "output.flac"
        
        with patch.object(converter, '_run_ffmpeg', return_value=(True, None)) as mock_run:
            converter._convert_dsf_to_flac(input_path, output_path)
            
            cmd = mock_run.call_args[0][0]
            
            assert '-map_metadata' in cmd
            assert '0' in cmd


class TestISOConversion:
    """Tests for ISO conversion methods."""
    
    def test_iso_to_flac_command_generation(self, mock_ffmpeg_available, temp_dir):
        """Test ISO to FLAC command generation."""
        converter = AudioConverter()
        
        input_path = temp_dir / "input.iso"
        output_path = temp_dir / "output.flac"
        
        with patch.object(converter, '_run_ffmpeg', return_value=(True, None)) as mock_run:
            converter._convert_iso_to_flac(input_path, output_path)
            
            cmd = mock_run.call_args[0][0]
            
            # Should map first audio stream
            assert '-map' in cmd
            assert '0:a:0' in cmd
    
    def test_iso_to_dsf_command_generation(self, mock_ffmpeg_available, temp_dir):
        """Test ISO to DSF command generation."""
        converter = AudioConverter()
        
        input_path = temp_dir / "input.iso"
        output_path = temp_dir / "output.dsf"
        
        with patch.object(converter, '_run_ffmpeg', return_value=(True, None)) as mock_run:
            converter._convert_iso_to_dsf(input_path, output_path)
            
            cmd = mock_run.call_args[0][0]
            cmd_str = ' '.join(cmd)
            
            # Should use DSD codec
            assert '-c:a' in cmd
            assert 'dsd_lsbf_planar' in cmd


class TestFFmpegExecution:
    """Tests for _run_ffmpeg method."""
    
    def test_run_ffmpeg_success(self, mock_ffmpeg_available):
        """Test successful ffmpeg execution."""
        converter = AudioConverter()
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        
        with patch('subprocess.run', return_value=mock_result):
            success, error = converter._run_ffmpeg(['ffmpeg', '-version'])
        
        assert success is True
        assert error is None
    
    def test_run_ffmpeg_failure(self, mock_ffmpeg_available):
        """Test failed ffmpeg execution."""
        converter = AudioConverter()
        
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: Invalid input file\nFailed to process"
        
        with patch('subprocess.run', return_value=mock_result):
            success, error = converter._run_ffmpeg(['ffmpeg', 'bad_args'])
        
        assert success is False
        assert "ffmpeg error" in error
    
    def test_run_ffmpeg_timeout(self, mock_ffmpeg_available):
        """Test ffmpeg timeout handling."""
        converter = AudioConverter()
        
        import subprocess
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('ffmpeg', 3600)):
            success, error = converter._run_ffmpeg(['ffmpeg', '-version'])
        
        assert success is False
        assert "timeout" in error.lower()
    
    def test_run_ffmpeg_not_found(self, mock_ffmpeg_available):
        """Test handling when ffmpeg binary is not found during execution."""
        converter = AudioConverter()
        
        with patch('subprocess.run', side_effect=FileNotFoundError()):
            success, error = converter._run_ffmpeg(['ffmpeg', '-version'])
        
        assert success is False
        assert "not found" in error.lower()


class TestFileInfo:
    """Tests for get_file_info method."""
    
    def test_get_file_info_success(self, mock_ffmpeg_available, temp_dir):
        """Test getting file info with ffprobe."""
        converter = AudioConverter()
        
        file_path = temp_dir / "test.dsf"
        file_path.write_text("mock")
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"format": {"duration": "180.0"}}'
        
        with patch('subprocess.run', return_value=mock_result):
            info = converter.get_file_info(file_path)
        
        assert info is not None
        assert 'format' in info
    
    def test_get_file_info_failure(self, mock_ffmpeg_available, temp_dir):
        """Test get_file_info when ffprobe fails."""
        converter = AudioConverter()
        
        file_path = temp_dir / "test.dsf"
        
        mock_result = Mock()
        mock_result.returncode = 1
        
        with patch('subprocess.run', return_value=mock_result):
            info = converter.get_file_info(file_path)
        
        assert info is None
    
    def test_get_file_info_exception(self, mock_ffmpeg_available, temp_dir):
        """Test get_file_info exception handling."""
        converter = AudioConverter()
        
        file_path = temp_dir / "test.dsf"
        
        with patch('subprocess.run', side_effect=Exception("Error")):
            info = converter.get_file_info(file_path)
        
        assert info is None


class TestEstimateOutputSize:
    """Tests for estimate_output_size method."""
    
    def test_estimate_flac_output_size(self, mock_ffmpeg_available, temp_dir):
        """Test output size estimation for FLAC conversion."""
        converter = AudioConverter(mode="iso_dsf_to_flac")
        
        input_path = temp_dir / "input.dsf"
        input_path.write_bytes(b"0" * 1000000)  # 1MB file
        
        estimated = converter.estimate_output_size(input_path, compression_ratio=0.5)
        
        assert estimated == 500000  # 50% of input size
    
    def test_estimate_dsf_output_size(self, mock_ffmpeg_available, temp_dir):
        """Test output size estimation for DSF conversion."""
        converter = AudioConverter(mode="iso_to_dsf")
        
        input_path = temp_dir / "input.iso"
        input_path.write_bytes(b"0" * 1000000)  # 1MB file
        
        estimated = converter.estimate_output_size(input_path)
        
        assert estimated == 800000  # 80% of input size
    
    def test_estimate_nonexistent_file(self, mock_ffmpeg_available, temp_dir):
        """Test size estimation for non-existent file."""
        converter = AudioConverter()
        
        input_path = temp_dir / "nonexistent.dsf"
        
        estimated = converter.estimate_output_size(input_path)
        
        assert estimated == 0


@pytest.mark.integration
@pytest.mark.requires_ffmpeg
@pytest.mark.slow
class TestConverterIntegration:
    """Integration tests with real ffmpeg (if available)."""
    
    def test_ffmpeg_availability(self):
        """Test that ffmpeg is available for integration tests."""
        import shutil
        assert shutil.which('ffmpeg') is not None, "ffmpeg not found for integration tests"
    
    @pytest.mark.skip(reason="Requires real audio files and is very slow")
    def test_real_dsf_conversion(self, test_album_path, temp_output_dir):
        """Test actual DSF to FLAC conversion with real file."""
        # This test is skipped by default as it requires:
        # 1. Real DSF files
        # 2. ffmpeg with DSD support
        # 3. Long execution time
        
        converter = AudioConverter()
        
        # Find first DSF file
        dsf_files = list(test_album_path.rglob("*.dsf"))
        if not dsf_files:
            pytest.skip("No DSF files found in test album")
        
        input_file = dsf_files[0]
        output_file = temp_output_dir / "test_output.flac"
        
        success, error, duration = converter.convert_file(input_file, output_file)
        
        assert success is True, f"Conversion failed: {error}"
        assert output_file.exists()
        assert output_file.stat().st_size > 0
        assert duration > 0

