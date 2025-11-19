# Input Directory Configuration Feature

## Overview

The input directory can now be specified in the configuration file (`config.yaml`) instead of requiring it as a command-line parameter. This makes the tool more convenient for repeated use with the same input directory.

## Changes Made

### 1. Configuration Files

**Files Modified:**
- `config.yaml`
- `config.example.yaml`

Added `input_dir` field to the `paths` section:

```yaml
paths:
  # Input directory containing music files to convert (required)
  input_dir: /path/to/your/input
  
  # Archive location for original files (required)
  archive_dir: /path/to/your/archive
  
  # Output directory (null = same as input)
  output_dir: null
  
  # Working directory for temporary processing
  working_dir: ./working
```

### 2. Configuration Module

**File Modified:** `src/config.py`

#### Updated `update_from_args()` method:
- Added `'input_dir': 'paths.input_dir'` to the argument mapping
- Now CLI `--input` parameter can override config file value

#### Updated `validate()` method:
- Added validation to ensure `input_dir` is provided
- Checks both config file and CLI arguments

### 3. Main CLI Module

**File Modified:** `src/main.py`

#### Updated CLI Interface:
- Made positional `INPUT_DIR` argument optional (`required=False`)
- Added new `--input` / `-i` option as alternative way to specify input directory
- Input directory can now be provided in three ways (in order of precedence):
  1. As positional argument: `python src/main.py /path/to/music`
  2. As option: `python src/main.py --input /path/to/music`
  3. In config file: `paths.input_dir: /path/to/music`

#### Updated `main()` function:
- Added logic to determine input directory from CLI or config
- Falls back to config file if no CLI input provided
- Added validation to ensure input directory exists and is a directory
- Better error messages for missing or invalid input directory

### 4. Documentation

**File Modified:** `README.md`

Updated the following sections:
- **Quick Start**: Added example showing config-based usage
- **Configuration File Example**: Added `input_dir` field with comment
- **Command-Line Options**: Updated to show `INPUT_DIR` as optional
- **Usage Examples**: Added example showing both config and CLI approaches

## Usage Examples

### Option 1: Using Configuration File (Recommended)

Set up your `config.yaml`:
```yaml
paths:
  input_dir: /Volumes/PrimaryHD_8TB/ConversionTest/Input
  archive_dir: /Volumes/PrimaryHD_8TB/ConversionTest/Archive
```

Run the converter:
```bash
python src/main.py
```

### Option 2: Using CLI Positional Argument

```bash
python src/main.py /path/to/music --archive /path/to/archive
```

### Option 3: Using CLI Option

```bash
python src/main.py --input /path/to/music --archive /path/to/archive
```

### Option 4: Mix Config and CLI (CLI overrides config)

Config file:
```yaml
paths:
  input_dir: /default/path
  archive_dir: /archive/path
```

Override with CLI:
```bash
python src/main.py --input /different/path
```

## Benefits

1. **Convenience**: No need to type the input path every time
2. **Consistency**: Use the same input directory across multiple runs
3. **Flexibility**: Can still override via CLI when needed
4. **Better Automation**: Easier to set up scheduled/automated conversions
5. **Cleaner Scripts**: Simpler command lines in batch scripts

## Backward Compatibility

✅ **Fully backward compatible** - Existing command-line usage still works:

```bash
# Old way (still works)
python src/main.py /path/to/music --archive /path/to/archive

# New way (also works)
python src/main.py  # Uses config.yaml
```

## Validation

The tool validates that:
1. Input directory is provided (either via CLI or config)
2. Input directory exists
3. Input directory is actually a directory (not a file)

Error messages guide the user if validation fails:
```
Error: Input directory must be provided either via CLI or config file
Error: Input directory does not exist: /invalid/path
Error: Input path is not a directory: /some/file.txt
```

## Testing Recommendations

1. Test with input in config only
2. Test with input via CLI only (positional)
3. Test with input via CLI only (`--input`)
4. Test with CLI overriding config
5. Test error cases (missing input, non-existent path, file instead of directory)

## Implementation Details

### Precedence Order

When determining the input directory, the code checks in this order:

```python
# 1. CLI positional argument
input_dir: Path

# 2. CLI --input option
input_dir_option: Path

# 3. Config file
config.get('paths.input_dir')
```

The first non-None value is used.

### Code Flow

```python
# Load config
config = Config(config_file)

# Determine input_dir: CLI argument takes precedence, then CLI option, then config
final_input_dir = input_dir or input_dir_option

# Override config with CLI arguments (if provided)
config.update_from_args(
    input_dir=str(final_input_dir) if final_input_dir else None,
    # ... other args
)

# Get input_dir from config if not provided via CLI
if not final_input_dir:
    input_dir_str = config.get('paths.input_dir')
    if input_dir_str:
        final_input_dir = Path(input_dir_str)

# Validate configuration
is_valid, errors = config.validate()
if not is_valid:
    # Show errors
    sys.exit(1)

# Ensure we have an input directory
if not final_input_dir:
    click.echo("Error: Input directory must be provided either via CLI or config file", err=True)
    sys.exit(1)

# Verify input directory exists and is a directory
if not final_input_dir.exists():
    click.echo(f"Error: Input directory does not exist: {final_input_dir}", err=True)
    sys.exit(1)

if not final_input_dir.is_dir():
    click.echo(f"Error: Input path is not a directory: {final_input_dir}", err=True)
    sys.exit(1)

# Run conversion
orchestrator.run(final_input_dir)
```

## Migration Guide

### For Existing Users

If you're currently using the tool with CLI arguments, no changes are needed. Your existing commands will continue to work.

### To Use Config-Based Input

1. Edit your `config.yaml`:
   ```yaml
   paths:
     input_dir: /your/music/directory
     archive_dir: /your/archive/directory
   ```

2. Run without arguments:
   ```bash
   python src/main.py
   ```

### For Automated Scripts

Before:
```bash
#!/bin/bash
python src/main.py /Volumes/Music/DSD --archive /Volumes/Archive
```

After (option 1 - simpler):
```bash
#!/bin/bash
# Paths are in config.yaml
python src/main.py
```

After (option 2 - explicit):
```bash
#!/bin/bash
python src/main.py --input /Volumes/Music/DSD --archive /Volumes/Archive
```

## Date

November 19, 2025

## Related Files

- `src/main.py` - Main entry point
- `src/config.py` - Configuration management
- `config.yaml` - User configuration
- `config.example.yaml` - Example configuration template
- `README.md` - User documentation

