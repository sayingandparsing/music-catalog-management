"""
Unit tests for config module (Config class).
"""

import pytest
import yaml
from pathlib import Path
from config import Config


class TestConfigInitialization:
    """Tests for Config initialization."""
    
    def test_config_init_default(self):
        """Test Config initialization with default config file."""
        # This assumes config.yaml exists in the workspace
        config_path = Path(__file__).parent.parent / "config.yaml"
        if not config_path.exists():
            pytest.skip("Default config.yaml not found")
        
        config = Config()
        
        assert config.config_path == config_path
        assert isinstance(config._config, dict)
    
    def test_config_init_custom_path(self, sample_config_file):
        """Test Config initialization with custom config file."""
        config = Config(config_path=sample_config_file)
        
        assert config.config_path == sample_config_file
        assert isinstance(config._config, dict)
    
    def test_config_init_nonexistent_file(self, temp_dir):
        """Test Config initialization with non-existent file."""
        nonexistent = temp_dir / "nonexistent.yaml"
        
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            Config(config_path=nonexistent)
    
    def test_config_loads_yaml_data(self, sample_config_file):
        """Test that Config loads YAML data correctly."""
        config = Config(config_path=sample_config_file)
        
        # Check that some expected keys exist
        assert 'conversion' in config._config
        assert 'paths' in config._config


class TestConfigGet:
    """Tests for get method."""
    
    def test_get_simple_key(self, sample_config_file):
        """Test getting a simple top-level key."""
        config = Config(config_path=sample_config_file)
        
        conversion = config.get('conversion')
        
        assert conversion is not None
        assert isinstance(conversion, dict)
    
    def test_get_nested_key(self, sample_config_file):
        """Test getting nested key with dot notation."""
        config = Config(config_path=sample_config_file)
        
        sample_rate = config.get('conversion.sample_rate')
        
        assert sample_rate == 88200
    
    def test_get_deeply_nested_key(self, sample_config_file):
        """Test getting deeply nested key."""
        config = Config(config_path=sample_config_file)
        
        resampler = config.get('conversion.audio_filter.resampler')
        
        assert resampler == 'soxr'
    
    def test_get_nonexistent_key(self, sample_config_file):
        """Test getting non-existent key returns None."""
        config = Config(config_path=sample_config_file)
        
        result = config.get('nonexistent.key')
        
        assert result is None
    
    def test_get_with_default(self, sample_config_file):
        """Test getting non-existent key with default value."""
        config = Config(config_path=sample_config_file)
        
        result = config.get('nonexistent.key', default='default_value')
        
        assert result == 'default_value'
    
    def test_get_partial_path(self, sample_config_file):
        """Test getting with partial path that doesn't exist."""
        config = Config(config_path=sample_config_file)
        
        result = config.get('conversion.nonexistent.nested')
        
        assert result is None
    
    def test_get_different_types(self, sample_config_file):
        """Test getting different data types."""
        config = Config(config_path=sample_config_file)
        
        # Integer
        sample_rate = config.get('conversion.sample_rate')
        assert isinstance(sample_rate, int)
        
        # String
        mode = config.get('conversion.mode')
        assert isinstance(mode, str)
        
        # Boolean
        preserve = config.get('conversion.preserve_metadata')
        assert isinstance(preserve, bool)


class TestConfigSet:
    """Tests for set method."""
    
    def test_set_simple_key(self, sample_config_file):
        """Test setting a simple key."""
        config = Config(config_path=sample_config_file)
        
        config.set('test_key', 'test_value')
        
        assert config.get('test_key') == 'test_value'
    
    def test_set_nested_key(self, sample_config_file):
        """Test setting a nested key with dot notation."""
        config = Config(config_path=sample_config_file)
        
        config.set('conversion.sample_rate', 96000)
        
        assert config.get('conversion.sample_rate') == 96000
    
    def test_set_creates_nested_structure(self, sample_config_file):
        """Test that set creates nested dictionaries as needed."""
        config = Config(config_path=sample_config_file)
        
        config.set('new.nested.key', 'value')
        
        assert config.get('new.nested.key') == 'value'
        assert isinstance(config.get('new'), dict)
        assert isinstance(config.get('new.nested'), dict)
    
    def test_set_overwrites_existing(self, sample_config_file):
        """Test that set overwrites existing values."""
        config = Config(config_path=sample_config_file)
        
        original = config.get('conversion.mode')
        config.set('conversion.mode', 'iso_to_dsf')
        
        assert config.get('conversion.mode') == 'iso_to_dsf'
        assert config.get('conversion.mode') != original


class TestUpdateFromArgs:
    """Tests for update_from_args method."""
    
    def test_update_from_args_archive_dir(self, sample_config_file):
        """Test updating archive_dir from arguments."""
        config = Config(config_path=sample_config_file)
        
        config.update_from_args(archive_dir='/new/archive')
        
        assert config.get('paths.archive_dir') == '/new/archive'
    
    def test_update_from_args_multiple(self, sample_config_file):
        """Test updating multiple values from arguments."""
        config = Config(config_path=sample_config_file)
        
        config.update_from_args(
            archive_dir='/new/archive',
            output_dir='/new/output',
            sample_rate=96000,
            bit_depth=16
        )
        
        assert config.get('paths.archive_dir') == '/new/archive'
        assert config.get('paths.output_dir') == '/new/output'
        assert config.get('conversion.sample_rate') == 96000
        assert config.get('conversion.bit_depth') == 16
    
    def test_update_from_args_ignores_none(self, sample_config_file):
        """Test that None values don't override config."""
        config = Config(config_path=sample_config_file)
        
        original_mode = config.get('conversion.mode')
        
        config.update_from_args(mode=None)
        
        assert config.get('conversion.mode') == original_mode
    
    def test_update_from_args_enrich_metadata(self, sample_config_file):
        """Test updating metadata enrichment setting."""
        config = Config(config_path=sample_config_file)
        
        config.update_from_args(enrich_metadata=True)
        
        assert config.get('metadata.enabled') is True
    
    def test_update_from_args_log_level(self, sample_config_file):
        """Test updating log level."""
        config = Config(config_path=sample_config_file)
        
        config.update_from_args(log_level='DEBUG')
        
        assert config.get('logging.level') == 'DEBUG'
    
    def test_update_from_args_unknown_arg(self, sample_config_file):
        """Test that unknown arguments are ignored."""
        config = Config(config_path=sample_config_file)
        
        # Should not raise error
        config.update_from_args(unknown_arg='value')
        
        # Unknown arg should not be in config
        assert config.get('unknown_arg') is None


class TestValidation:
    """Tests for validate method."""
    
    def test_validate_valid_config(self, sample_config_file):
        """Test validation with valid configuration."""
        config = Config(config_path=sample_config_file)
        
        is_valid, errors = config.validate()
        
        assert is_valid is True
        assert errors == []
    
    def test_validate_missing_archive_dir(self, sample_config_file):
        """Test validation fails when archive_dir is missing."""
        config = Config(config_path=sample_config_file)
        config.set('paths.archive_dir', None)
        
        is_valid, errors = config.validate()
        
        assert is_valid is False
        assert len(errors) > 0
        assert any('archive' in e.lower() for e in errors)
    
    def test_validate_invalid_mode(self, sample_config_file):
        """Test validation fails with invalid conversion mode."""
        config = Config(config_path=sample_config_file)
        config.set('conversion.mode', 'invalid_mode')
        
        is_valid, errors = config.validate()
        
        assert is_valid is False
        assert any('conversion mode' in e.lower() for e in errors)
    
    def test_validate_invalid_sample_rate(self, sample_config_file):
        """Test validation fails with invalid sample rate."""
        config = Config(config_path=sample_config_file)
        config.set('conversion.sample_rate', 44100)  # Not in valid list
        
        is_valid, errors = config.validate()
        
        assert is_valid is False
        assert any('sample rate' in e.lower() for e in errors)
    
    def test_validate_invalid_bit_depth(self, sample_config_file):
        """Test validation fails with invalid bit depth."""
        config = Config(config_path=sample_config_file)
        config.set('conversion.bit_depth', 8)  # Not in valid list
        
        is_valid, errors = config.validate()
        
        assert is_valid is False
        assert any('bit depth' in e.lower() for e in errors)
    
    def test_validate_invalid_log_level(self, sample_config_file):
        """Test validation fails with invalid log level."""
        config = Config(config_path=sample_config_file)
        config.set('logging.level', 'INVALID')
        
        is_valid, errors = config.validate()
        
        assert is_valid is False
        assert any('log level' in e.lower() for e in errors)
    
    def test_validate_multiple_errors(self, sample_config_file):
        """Test validation with multiple errors."""
        config = Config(config_path=sample_config_file)
        config.set('paths.archive_dir', None)
        config.set('conversion.mode', 'invalid')
        config.set('conversion.sample_rate', 44100)
        
        is_valid, errors = config.validate()
        
        assert is_valid is False
        assert len(errors) >= 3
    
    def test_validate_all_valid_modes(self, sample_config_file):
        """Test that all valid modes pass validation."""
        config = Config(config_path=sample_config_file)
        
        valid_modes = ['iso_dsf_to_flac', 'iso_to_dsf']
        
        for mode in valid_modes:
            config.set('conversion.mode', mode)
            is_valid, errors = config.validate()
            assert is_valid is True, f"Mode {mode} should be valid"
    
    def test_validate_all_valid_sample_rates(self, sample_config_file):
        """Test that all valid sample rates pass validation."""
        config = Config(config_path=sample_config_file)
        
        valid_rates = [88200, 96000, 176400, 192000]
        
        for rate in valid_rates:
            config.set('conversion.sample_rate', rate)
            is_valid, errors = config.validate()
            assert is_valid is True, f"Sample rate {rate} should be valid"
    
    def test_validate_all_valid_bit_depths(self, sample_config_file):
        """Test that all valid bit depths pass validation."""
        config = Config(config_path=sample_config_file)
        
        valid_depths = [16, 24, 32]
        
        for depth in valid_depths:
            config.set('conversion.bit_depth', depth)
            is_valid, errors = config.validate()
            assert is_valid is True, f"Bit depth {depth} should be valid"


class TestToDict:
    """Tests for to_dict method."""
    
    def test_to_dict(self, sample_config_file):
        """Test converting config to dictionary."""
        config = Config(config_path=sample_config_file)
        
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert 'conversion' in config_dict
        assert 'paths' in config_dict
    
    def test_to_dict_is_copy(self, sample_config_file):
        """Test that to_dict returns a copy, not reference."""
        config = Config(config_path=sample_config_file)
        
        config_dict = config.to_dict()
        config_dict['test_key'] = 'test_value'
        
        # Original config should not be modified
        assert config.get('test_key') is None


class TestConfigRepr:
    """Tests for __repr__ method."""
    
    def test_repr(self, sample_config_file):
        """Test string representation of Config."""
        config = Config(config_path=sample_config_file)
        
        repr_str = repr(config)
        
        assert 'Config' in repr_str
        assert str(sample_config_file) in repr_str


class TestComplexScenarios:
    """Tests for complex configuration scenarios."""
    
    def test_cli_override_workflow(self, sample_config_file):
        """Test typical workflow: load config, override from CLI, validate."""
        config = Config(config_path=sample_config_file)
        
        # Override from CLI arguments
        config.update_from_args(
            archive_dir='/custom/archive',
            sample_rate=96000,
            enrich_metadata=True
        )
        
        # Validate
        is_valid, errors = config.validate()
        
        assert is_valid is True
        assert config.get('paths.archive_dir') == '/custom/archive'
        assert config.get('conversion.sample_rate') == 96000
        assert config.get('metadata.enabled') is True
    
    def test_empty_config_file(self, temp_dir):
        """Test loading empty config file."""
        empty_config = temp_dir / "empty.yaml"
        empty_config.write_text("")
        
        config = Config(config_path=empty_config)
        
        # Should load without error but fail validation
        assert config._config == {} or config._config is None or len(config._config) == 0
    
    def test_minimal_valid_config(self, temp_dir):
        """Test with minimal valid configuration."""
        minimal_config = {
            'conversion': {
                'mode': 'iso_dsf_to_flac',
                'sample_rate': 88200,
                'bit_depth': 24
            },
            'paths': {
                'archive_dir': '/archive'
            },
            'logging': {
                'level': 'INFO'
            }
        }
        
        config_file = temp_dir / "minimal.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(minimal_config, f)
        
        config = Config(config_path=config_file)
        is_valid, errors = config.validate()
        
        assert is_valid is True
        assert config.get('conversion.mode') == 'iso_dsf_to_flac'
    
    def test_preserve_unvalidated_keys(self, sample_config_file):
        """Test that validation doesn't affect unvalidated keys."""
        config = Config(config_path=sample_config_file)
        
        # Set a custom key that's not validated
        config.set('custom.my_setting', 'my_value')
        
        # Validate
        is_valid, errors = config.validate()
        
        # Custom key should still exist
        assert config.get('custom.my_setting') == 'my_value'
    
    def test_nested_get_set_consistency(self, sample_config_file):
        """Test that get and set are consistent for nested paths."""
        config = Config(config_path=sample_config_file)
        
        test_path = 'test.deeply.nested.value'
        test_value = 'test_data'
        
        config.set(test_path, test_value)
        retrieved = config.get(test_path)
        
        assert retrieved == test_value

