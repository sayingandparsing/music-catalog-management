"""
Configuration management for DSD Music Converter.
Handles loading from YAML files and CLI argument overrides.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml


class Config:
    """Configuration manager for the music converter."""
    
    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration.
        
        Args:
            config_path: Path to custom config file, or None for default
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self):
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}"
            )
        
        with open(self.config_path, 'r') as f:
            self._config = yaml.safe_load(f) or {}
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path (e.g., 'conversion.sample_rate')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any):
        """
        Set configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path (e.g., 'conversion.sample_rate')
            value: Value to set
        """
        keys = key_path.split('.')
        config = self._config
        
        # Navigate to the parent dictionary
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # Set the final value
        config[keys[-1]] = value
    
    def update_from_args(self, **kwargs):
        """
        Update configuration from CLI arguments.
        Only non-None values will override config.
        
        Args:
            **kwargs: Keyword arguments from CLI
        """
        # Map CLI argument names to config paths
        arg_mapping = {
            'input_dir': 'paths.input_dir',
            'output_dir': 'paths.output_dir',
            'archive_dir': 'paths.archive_dir',
            'mode': 'conversion.mode',
            'sample_rate': 'conversion.sample_rate',
            'bit_depth': 'conversion.bit_depth',
            'enrich_metadata': 'metadata.enabled',
            'log_level': 'logging.level',
        }
        
        for arg_name, config_path in arg_mapping.items():
            if arg_name in kwargs and kwargs[arg_name] is not None:
                self.set(config_path, kwargs[arg_name])
    
    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate configuration.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check required fields
        input_dir = self.get('paths.input_dir')
        if not input_dir:
            errors.append("Input directory is required (paths.input_dir)")
        
        archive_dir = self.get('paths.archive_dir')
        if not archive_dir:
            errors.append("Archive directory is required (paths.archive_dir)")
        
        # Validate conversion mode
        mode = self.get('conversion.mode')
        valid_modes = ['iso_dsf_to_flac', 'iso_to_dsf']
        if mode not in valid_modes:
            errors.append(
                f"Invalid conversion mode: {mode}. "
                f"Must be one of {valid_modes}"
            )
        
        # Validate FLAC standardization settings
        flac_std_enabled = self.get('conversion.flac_standardization.enabled', False)
        if flac_std_enabled:
            higher_quality_behavior = self.get(
                'conversion.flac_standardization.higher_quality_behavior',
                'skip'
            )
            valid_behaviors = ['skip', 'downsample']
            if higher_quality_behavior not in valid_behaviors:
                errors.append(
                    f"Invalid higher_quality_behavior: {higher_quality_behavior}. "
                    f"Must be one of {valid_behaviors}"
                )
        
        # Validate sample rate
        sample_rate = self.get('conversion.sample_rate')
        valid_rates = [88200, 96000, 176400, 192000]
        if sample_rate not in valid_rates:
            errors.append(
                f"Invalid sample rate: {sample_rate}. "
                f"Must be one of {valid_rates}"
            )
        
        # Validate bit depth
        bit_depth = self.get('conversion.bit_depth')
        valid_depths = [16, 24, 32]
        if bit_depth not in valid_depths:
            errors.append(
                f"Invalid bit depth: {bit_depth}. "
                f"Must be one of {valid_depths}"
            )
        
        # Validate log level
        log_level = self.get('logging.level', 'INFO')
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if log_level not in valid_levels:
            errors.append(
                f"Invalid log level: {log_level}. "
                f"Must be one of {valid_levels}"
            )
        
        return (len(errors) == 0, errors)
    
    def to_dict(self) -> Dict[str, Any]:
        """Return configuration as dictionary."""
        return self._config.copy()
    
    def __repr__(self) -> str:
        """String representation of config."""
        return f"Config(path={self.config_path})"

