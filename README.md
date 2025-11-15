# DSD Music Converter

A robust Python CLI utility for converting DSD audio files (ISO/DSF) to FLAC or DSF format with crash recovery, pause/resume capability, and optional metadata enrichment.

## Features

- **Multiple Conversion Modes**: Convert ISO/DSF to FLAC or ISO to DSF
- **High-Quality Audio Processing**: Uses SoX resampler with precision=28, triangular dithering, and 40kHz lowpass filter
- **Crash Recovery**: Automatically resume from where you left off if interrupted
- **Pause/Resume**: Pause conversion between albums and resume later
- **Album-Level Processing**: Preserves directory structure and handles albums as units
- **Automatic Archiving**: Backs up original files before conversion
- **Configurable Sample Rates**: Support for 24/88.2, 24/96, 24/176.4, 24/192
- **Metadata Preservation**: Automatically copies metadata from source files
- **Metadata Enrichment**: Optional integration with MusicBrainz and Discogs
- **Error Handling**: Retry logic with configurable attempts per file
- **Comprehensive Logging**: Detailed logs for tracking progress and debugging
- **State Persistence**: Tracks conversion status and settings for each session

## Requirements

### System Dependencies

- **Python 3.9+**
- **ffmpeg**: Required for audio conversion
  ```bash
  # macOS
  brew install ffmpeg
  
  # Ubuntu/Debian
  sudo apt-get install ffmpeg
  
  # Fedora
  sudo dnf install ffmpeg
  ```

### Python Dependencies

All Python dependencies are listed in `requirements.txt` and can be installed via pip.

## Installation

1. Clone the repository:
   ```bash
   cd music-catalog-management
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Verify ffmpeg is installed:
   ```bash
   ffmpeg -version
   ```

## Quick Start

1. **Basic conversion** (ISO/DSF to FLAC):
   ```bash
   python src/main.py /path/to/music --archive /path/to/archive
   ```

2. **Convert with custom output directory**:
   ```bash
   python src/main.py /path/to/music \
     --archive /path/to/archive \
     --output /path/to/output
   ```

3. **Convert ISO to DSF**:
   ```bash
   python src/main.py /path/to/music \
     --archive /path/to/archive \
     --mode iso_to_dsf
   ```

4. **With metadata enrichment**:
   ```bash
   python src/main.py /path/to/music \
     --archive /path/to/archive \
     --enrich-metadata
   ```

## Configuration

The tool uses a `config.yaml` file for default settings. You can create a custom config file or override settings via command-line options.

### Configuration File Example

```yaml
conversion:
  mode: iso_dsf_to_flac
  sample_rate: 88200  # Hz
  bit_depth: 24

paths:
  archive_dir: /path/to/archive
  output_dir: null  # null = same as input

metadata:
  enabled: false
  sources:
    - musicbrainz
    - discogs
  discogs:
    user_token: YOUR_TOKEN_HERE
  behavior: fill_missing  # or 'overwrite'

processing:
  max_retries: 3
  skip_album_on_error: true
  check_pause: true

logging:
  level: INFO
  log_file: conversion.log
  error_log_file: conversion_errors.log
```

### Custom Configuration

Use a custom config file:
```bash
python src/main.py /path/to/music \
  --config my_config.yaml \
  --archive /path/to/archive
```

## Command-Line Options

```
Usage: main.py [OPTIONS] INPUT_DIR

Options:
  -o, --output PATH              Output directory (default: same as input)
  -a, --archive PATH            Archive directory for backups (required)
  -m, --mode [iso_dsf_to_flac|iso_to_dsf]
                                Conversion mode
  -r, --sample-rate [88200|96000|176400|192000]
                                Sample rate in Hz
  -b, --bit-depth [16|24|32]    Bit depth
  -c, --config PATH             Configuration file path
  --enrich-metadata             Enable metadata enrichment
  --resume                      Resume previous conversion
  --pause                       Create pause signal file and exit
  --dry-run                     Simulate conversion without actually converting
  --log-level [DEBUG|INFO|WARNING|ERROR]
                                Logging level
  --help                        Show this message and exit
```

## Usage Examples

### Example 1: Basic Conversion

Convert all DSD files in a music directory to FLAC:

```bash
python src/main.py ~/Music/DSD \
  --archive ~/Music/Archive
```

**What happens:**
1. Scans `~/Music/DSD` for ISO/DSF files
2. For each album:
   - Archives original files to `~/Music/Archive/AlbumName_TIMESTAMP/`
   - Converts ISO/DSF files to FLAC (24/88.2 by default)
   - Preserves directory structure
   - Copies non-music files (artwork, PDFs, etc.)
   - Saves converted files to original location

### Example 2: Custom Output and Sample Rate

```bash
python src/main.py ~/Music/DSD \
  --archive ~/Music/Archive \
  --output ~/Music/Converted \
  --sample-rate 96000 \
  --bit-depth 24
```

### Example 3: ISO to DSF Conversion

```bash
python src/main.py ~/Music/SACD_ISO \
  --archive ~/Music/Archive \
  --mode iso_to_dsf
```

### Example 4: With Metadata Enrichment

First, configure your Discogs token in `config.yaml`:

```yaml
metadata:
  enabled: true
  discogs:
    user_token: YOUR_DISCOGS_TOKEN
```

Then run:

```bash
python src/main.py ~/Music/DSD \
  --archive ~/Music/Archive \
  --enrich-metadata
```

### Example 5: Dry Run (Test Mode)

Test the conversion without actually converting files:

```bash
python src/main.py ~/Music/DSD \
  --archive ~/Music/Archive \
  --dry-run
```

### Example 6: Resume After Interruption

If the conversion is interrupted (crash, Ctrl+C, etc.):

```bash
python src/main.py ~/Music/DSD \
  --archive ~/Music/Archive \
  --resume
```

The tool will:
- Load the previous session state
- Skip already-completed albums
- Resume from where it left off

### Example 7: Pause and Resume

To pause conversion after the current album:

```bash
# In another terminal, create pause signal
python src/main.py ~/Music/DSD --pause
```

The running conversion will stop after completing the current album. To resume:

```bash
# Remove pause signal and resume
rm .state/PAUSE
python src/main.py ~/Music/DSD \
  --archive ~/Music/Archive \
  --resume
```

## Directory Structure Example

**Input:**
```
/home/user/Music/
└── Miles Davis - Bitches Brew/
    ├── Art/
    │   ├── cover.jpg
    │   └── booklet.pdf
    ├── CD1/
    │   ├── 01 - Pharaoh's Dance.dsf
    │   └── 02 - Bitches Brew.dsf
    └── CD2/
        ├── 01 - Spanish Key.dsf
        └── 02 - John McLaughlin.dsf
```

**Output (after conversion):**
```
/home/user/Music/
└── Miles Davis - Bitches Brew/
    ├── Art/
    │   ├── cover.jpg        (copied)
    │   └── booklet.pdf      (copied)
    ├── CD1/
    │   ├── 01 - Pharaoh's Dance.flac  (converted)
    │   └── 02 - Bitches Brew.flac     (converted)
    └── CD2/
        ├── 01 - Spanish Key.flac       (converted)
        └── 02 - John McLaughlin.flac   (converted)
```

**Archive:**
```
/path/to/archive/
└── Miles Davis - Bitches Brew_20250115_143022/
    ├── Art/
    │   ├── cover.jpg
    │   └── booklet.pdf
    ├── CD1/
    │   ├── 01 - Pharaoh's Dance.dsf
    │   └── 02 - Bitches Brew.dsf
    └── CD2/
        ├── 01 - Spanish Key.dsf
        └── 02 - John McLaughlin.dsf
```

## State Management

The tool maintains state in the `.state/` directory:

- **`.state/conversion_state.json`**: Current session state
  - Input/output directories
  - Conversion settings
  - Album and file status
  - Timestamps

- **`.state/PAUSE`**: Pause signal file
  - Created with `--pause` option
  - Checked between albums
  - Removed manually or with resume

### State File Structure

```json
{
  "session_id": "20250115_143022",
  "input_dir": "/home/user/Music",
  "conversion_mode": "iso_dsf_to_flac",
  "sample_rate": 88200,
  "albums": [
    {
      "album_path": "/home/user/Music/Album1",
      "status": "completed",
      "archive_path": "/archive/Album1_20250115_143022",
      "files": [
        {
          "source_path": "/home/user/Music/Album1/track.dsf",
          "output_path": "/home/user/Music/Album1/track.flac",
          "status": "completed",
          "attempts": 1
        }
      ]
    }
  ]
}
```

## Logging

The tool generates detailed logs:

- **`conversion.log`**: All log messages (INFO level and above)
- **`conversion_errors.log`**: Only errors and critical messages

### Log Format

```
2025-01-15 14:30:22 - INFO - Starting Conversion Process
2025-01-15 14:30:23 - INFO - [1/5] Processing album: Miles Davis - Bitches Brew
2025-01-15 14:30:25 - INFO -   ✓ 01 - Pharaoh's Dance.dsf -> 01 - Pharaoh's Dance.flac (12.3s)
2025-01-15 14:30:38 - INFO -   ✓ 02 - Bitches Brew.dsf -> 02 - Bitches Brew.flac (13.1s)
2025-01-15 14:30:40 - INFO - ✓ Album completed: Miles Davis - Bitches Brew (2 files)
```

## Metadata Enrichment

### MusicBrainz (Free)

No configuration required. Automatically searches for:
- Artist name
- Album title
- Track titles and numbers
- Release date
- Label and catalog number

### Discogs (Requires API Token)

1. Get a Discogs user token:
   - Go to https://www.discogs.com/settings/developers
   - Generate a new token

2. Add to `config.yaml`:
   ```yaml
   metadata:
     enabled: true
     discogs:
       user_token: YOUR_TOKEN_HERE
   ```

### Metadata Behavior

- **`fill_missing`** (default): Only add metadata to empty fields
- **`overwrite`**: Replace all existing metadata

## Error Handling

### File-Level Errors

- Automatic retry (3 attempts by default)
- Detailed error logging
- Configurable via `processing.max_retries`

### Album-Level Errors

- If any file in an album fails after all retries:
  - Album is marked as failed
  - Album is skipped (configurable)
  - Conversion continues with next album
  - Error details logged

### Configuration

```yaml
processing:
  max_retries: 3              # Attempts per file
  skip_album_on_error: true   # Skip album if any file fails
```

## Performance Considerations

- **Conversion Speed**: Depends on file size and system performance
  - Typical: 30-60 seconds per track
  - Large files (>1GB): 2-5 minutes

- **Disk Space**: Ensure adequate space
  - Archive: Same size as originals
  - Output: ~50% of original size (FLAC compression)

- **Memory**: Minimal memory usage
  - Processes one file at a time

## Troubleshooting

### ffmpeg Not Found

```
Error: ffmpeg not found. Please install ffmpeg to use this tool.
```

**Solution**: Install ffmpeg (see Requirements section)

### Archive Directory Required

```
Configuration errors:
  - Archive directory is required (paths.archive_dir)
```

**Solution**: Specify archive directory with `--archive` option

### Permission Denied

```
Error: Permission denied: /path/to/file
```

**Solution**: Check file and directory permissions

### Resume Not Working

If `--resume` doesn't find a previous session:

1. Check `.state/conversion_state.json` exists
2. Ensure you're in the same directory
3. Try absolute paths

### Metadata Enrichment Fails

```
Warning: Metadata enrichment disabled: No module named 'musicbrainzngs'
```

**Solution**: Install required packages:
```bash
pip install python-musicbrainzngs python3-discogs-client
```

## Advanced Usage

### Audio Quality Settings

The converter uses high-quality ffmpeg settings that are fully configurable in `config.yaml`:

```yaml
conversion:
  audio_filter:
    resampler: soxr              # High-quality SoX resampler
    soxr_precision: 28           # Maximum precision
    dither_method: triangular    # Best dithering
    lowpass_freq: 40000          # 40kHz lowpass filter
  
  flac_compression_level: 8      # Maximum compression
  preserve_metadata: true        # Keep original metadata
```

This generates ffmpeg commands like:

```bash
ffmpeg -i input.dsf \
  -af "aresample=resampler=soxr:precision=28:dither_method=triangular,lowpass=40000" \
  -sample_fmt s24 \
  -ar 88200 \
  -compression_level 8 \
  -map_metadata 0 \
  output.flac
```

**Configuration Options:**

- **`resampler`**: `soxr` (high quality) or `swr` (standard/faster)
- **`soxr_precision`**: 20-28 (higher = better quality, slower)
- **`dither_method`**: `triangular`, `rectangular`, or `none`
- **`lowpass_freq`**: Frequency in Hz (0 to disable)
  - Recommended: 40000 for 88.2/96kHz output
  - Recommended: 80000 for 176.4/192kHz output
- **`flac_compression_level`**: 0-12 (higher = smaller files, slower)
- **`preserve_metadata`**: `true` or `false`

**Why these settings matter:**
- **SoX Resampler**: Industry-standard, minimizes artifacts
- **Precision 28**: Maximum precision for calculations
- **Triangular Dithering**: Reduces quantization noise when converting to PCM
- **Lowpass Filter**: Removes ultrasonic content that can cause aliasing
- **Metadata Preservation**: Keeps all original tags and artwork

### Example Configurations

**Maximum Quality (slower):**
```yaml
conversion:
  sample_rate: 176400
  bit_depth: 24
  audio_filter:
    resampler: soxr
    soxr_precision: 28
    dither_method: triangular
    lowpass_freq: 80000
  flac_compression_level: 12
```

**Balanced (recommended):**
```yaml
conversion:
  sample_rate: 88200
  bit_depth: 24
  audio_filter:
    resampler: soxr
    soxr_precision: 28
    dither_method: triangular
    lowpass_freq: 40000
  flac_compression_level: 8
```

**Fast (standard quality):**
```yaml
conversion:
  sample_rate: 88200
  bit_depth: 24
  audio_filter:
    resampler: swr
    soxr_precision: 20
    dither_method: rectangular
    lowpass_freq: 40000
  flac_compression_level: 5
```

### Batch Processing Multiple Directories

Create a shell script:

```bash
#!/bin/bash
ARCHIVE="/path/to/archive"

for dir in /path/to/music/*/; do
    python src/main.py "$dir" --archive "$ARCHIVE"
done
```

## Contributing

Contributions are welcome! Areas for improvement:

- Additional audio format support
- GUI interface
- Parallel processing
- Cloud storage integration
- Additional metadata sources

## License

This project is open source. See LICENSE file for details.

## Support

For issues and questions:
1. Check the Troubleshooting section
2. Review logs in `conversion.log` and `conversion_errors.log`
3. Open an issue with detailed information

## Changelog

### Version 1.0.0
- Initial release
- ISO/DSF to FLAC conversion
- ISO to DSF conversion
- Crash recovery and resume
- Pause/resume functionality
- Metadata enrichment (MusicBrainz, Discogs)
- Comprehensive logging
- State persistence

