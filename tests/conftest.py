"""
Shared fixtures and configuration for pytest tests.
"""

import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Generator
from unittest.mock import Mock, MagicMock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ============================================================================
# Test Environment Configuration
# ============================================================================

@pytest.fixture(scope="session")
def test_album_path() -> Path:
    """
    Get path to test album from environment variable.
    
    Set TEST_ALBUM_PATH environment variable to a directory containing
    at least one ISO or DSF album for integration tests.
    
    Returns:
        Path to test album directory
    
    Raises:
        pytest.skip: If TEST_ALBUM_PATH not set (skip integration tests)
    """
    path = os.environ.get("TEST_ALBUM_PATH")
    if not path:
        pytest.skip("TEST_ALBUM_PATH environment variable not set")
    
    album_path = Path(path)
    if not album_path.exists():
        pytest.skip(f"TEST_ALBUM_PATH does not exist: {path}")
    
    return album_path


# ============================================================================
# Temporary Directory Fixtures
# ============================================================================

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    Create a temporary directory for test outputs.
    Automatically cleaned up after test.
    """
    temp_path = Path(tempfile.mkdtemp(prefix="dsd_test_"))
    try:
        yield temp_path
    finally:
        if temp_path.exists():
            shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def temp_input_dir(temp_dir) -> Path:
    """Temporary input directory."""
    input_path = temp_dir / "input"
    input_path.mkdir(parents=True, exist_ok=True)
    return input_path


@pytest.fixture
def temp_output_dir(temp_dir) -> Path:
    """Temporary output directory."""
    output_path = temp_dir / "output"
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


@pytest.fixture
def temp_archive_dir(temp_dir) -> Path:
    """Temporary archive directory."""
    archive_path = temp_dir / "archive"
    archive_path.mkdir(parents=True, exist_ok=True)
    return archive_path


@pytest.fixture
def temp_state_dir(temp_dir) -> Path:
    """Temporary state directory."""
    state_path = temp_dir / ".state"
    state_path.mkdir(parents=True, exist_ok=True)
    return state_path


# ============================================================================
# Sample File Creation Fixtures
# ============================================================================

@pytest.fixture
def sample_album_structure(temp_input_dir) -> Path:
    """
    Create a sample album directory structure with mock files.
    
    Structure:
        Test Artist - Test Album/
            ├── 01 - Track One.dsf
            ├── 02 - Track Two.dsf
            ├── cover.jpg
            └── booklet.pdf
    """
    album_path = temp_input_dir / "Test Artist - Test Album"
    album_path.mkdir(parents=True, exist_ok=True)
    
    # Create mock music files (empty files for unit tests)
    (album_path / "01 - Track One.dsf").write_text("mock dsf content")
    (album_path / "02 - Track Two.dsf").write_text("mock dsf content")
    
    # Create non-music files
    (album_path / "cover.jpg").write_bytes(b"\xff\xd8\xff\xe0")  # JPEG header
    (album_path / "booklet.pdf").write_bytes(b"%PDF-1.4")  # PDF header
    
    return album_path


@pytest.fixture
def sample_multi_album_structure(temp_input_dir) -> Path:
    """
    Create multiple albums for testing batch operations.
    
    Structure:
        input/
            ├── Album 1/
            │   ├── track1.iso
            │   └── cover.jpg
            └── Album 2/
                ├── track1.dsf
                └── track2.dsf
    """
    # Album 1
    album1 = temp_input_dir / "Album 1"
    album1.mkdir(parents=True, exist_ok=True)
    (album1 / "track1.iso").write_text("mock iso content")
    (album1 / "cover.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    
    # Album 2
    album2 = temp_input_dir / "Album 2"
    album2.mkdir(parents=True, exist_ok=True)
    (album2 / "track1.dsf").write_text("mock dsf content")
    (album2 / "track2.dsf").write_text("mock dsf content")
    
    return temp_input_dir


@pytest.fixture
def sample_nested_album_structure(temp_input_dir) -> Path:
    """
    Create album with nested subdirectories (CD1, CD2, etc.).
    
    Structure:
        Artist - Album/
            ├── CD1/
            │   ├── 01 - Track.dsf
            │   └── 02 - Track.dsf
            ├── CD2/
            │   └── 01 - Track.dsf
            └── cover.jpg
    """
    album_path = temp_input_dir / "Artist - Album"
    
    # CD1
    cd1_path = album_path / "CD1"
    cd1_path.mkdir(parents=True, exist_ok=True)
    (cd1_path / "01 - Track.dsf").write_text("mock dsf content")
    (cd1_path / "02 - Track.dsf").write_text("mock dsf content")
    
    # CD2
    cd2_path = album_path / "CD2"
    cd2_path.mkdir(parents=True, exist_ok=True)
    (cd2_path / "01 - Track.dsf").write_text("mock dsf content")
    
    # Root level artwork
    (album_path / "cover.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    
    return album_path


# ============================================================================
# Mock Fixtures for External Dependencies
# ============================================================================

@pytest.fixture
def mock_musicbrainz():
    """Mock MusicBrainz API calls."""
    mock_mb = MagicMock()
    
    # Mock release search
    mock_mb.search_releases.return_value = {
        'release-list': [
            {
                'id': 'test-release-id',
                'title': 'Test Album',
                'artist-credit': [{'artist': {'name': 'Test Artist'}}],
                'date': '2020-01-01',
                'label-info-list': [
                    {'label': {'name': 'Test Label'}}
                ]
            }
        ]
    }
    
    # Mock recording search
    mock_mb.search_recordings.return_value = {
        'recording-list': [
            {
                'id': 'test-recording-id',
                'title': 'Test Track',
                'length': '300000'
            }
        ]
    }
    
    return mock_mb


@pytest.fixture
def mock_discogs():
    """Mock Discogs API client."""
    mock_client = MagicMock()
    
    # Mock search results
    mock_result = Mock()
    mock_result.title = "Test Album"
    mock_result.id = 12345
    mock_result.year = 2020
    mock_result.labels = ["Test Label"]
    mock_result.genres = ["Electronic", "Jazz"]
    mock_result.tracklist = [
        Mock(title="Track 1", position="1"),
        Mock(title="Track 2", position="2")
    ]
    
    mock_client.search.return_value.page.return_value = [mock_result]
    
    return mock_client


@pytest.fixture
def mock_ffmpeg_success(monkeypatch):
    """Mock successful ffmpeg execution."""
    def mock_run(*args, **kwargs):
        result = Mock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result
    
    monkeypatch.setattr("subprocess.run", mock_run)


@pytest.fixture
def mock_ffmpeg_available(monkeypatch):
    """Mock ffmpeg being available in system."""
    monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/ffmpeg" if x == "ffmpeg" else None)


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def sample_config_dict() -> dict:
    """Sample configuration dictionary for testing."""
    return {
        'conversion': {
            'mode': 'iso_dsf_to_flac',
            'sample_rate': 88200,
            'bit_depth': 24,
            'audio_filter': {
                'resampler': 'soxr',
                'soxr_precision': 28,
                'dither_method': 'triangular',
                'lowpass_freq': 40000
            },
            'flac_compression_level': 8,
            'preserve_metadata': True
        },
        'paths': {
            'archive_dir': '/tmp/archive',
            'output_dir': None
        },
        'metadata': {
            'enabled': False,
            'sources': ['musicbrainz', 'discogs'],
            'discogs': {'user_token': None},
            'behavior': 'fill_missing'
        },
        'processing': {
            'max_retries': 3,
            'skip_album_on_error': True,
            'check_pause': True,
            'ffmpeg_threads': 0
        },
        'logging': {
            'level': 'INFO',
            'log_file': 'test_conversion.log',
            'error_log_file': 'test_errors.log',
            'console_timestamps': True
        },
        'files': {
            'music_extensions': ['.iso', '.dsf', '.dff'],
            'copy_extensions': ['.jpg', '.jpeg', '.png', '.pdf', '.txt', '.cue']
        }
    }


@pytest.fixture
def sample_config_file(temp_dir, sample_config_dict) -> Path:
    """Create a temporary YAML config file."""
    import yaml
    
    config_path = temp_dir / "test_config.yaml"
    with open(config_path, 'w') as f:
        yaml.dump(sample_config_dict, f)
    
    return config_path


# ============================================================================
# Logger Fixtures
# ============================================================================

@pytest.fixture
def temp_log_files(temp_dir) -> tuple[Path, Path]:
    """Create temporary log file paths."""
    log_file = temp_dir / "test.log"
    error_log_file = temp_dir / "test_errors.log"
    return log_file, error_log_file


# ============================================================================
# Cleanup Hooks
# ============================================================================

@pytest.fixture(autouse=True)
def cleanup_state_dir():
    """Automatically cleanup .state directory after each test."""
    yield
    # Cleanup after test
    state_dir = Path(".state")
    if state_dir.exists() and state_dir.name == ".state":
        # Only clean if we're in a test context
        if "pytest" in sys.modules:
            for item in state_dir.glob("*"):
                if item.is_file():
                    item.unlink(missing_ok=True)


# ============================================================================
# Pytest Configuration Hooks
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom settings."""
    config.addinivalue_line(
        "markers", "unit: Fast unit tests (default)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests requiring real ISO/DSF files"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take more than 5 seconds"
    )
    config.addinivalue_line(
        "markers", "requires_ffmpeg: Tests that require ffmpeg to be installed"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test items during collection."""
    # Add 'unit' marker to tests without any marker
    for item in items:
        if not any(item.iter_markers()):
            item.add_marker(pytest.mark.unit)

