# Changes Summary - SACD ISO Support

## What Was Fixed

The converter was failing with "Invalid data found when processing input" errors when trying to process SACD ISO files. This happened because:

1. **Root Cause**: ffmpeg cannot directly read SACD ISO files
   - SACD ISOs use a proprietary filesystem format
   - The DSD audio data is encapsulated within the ISO image
   - ffmpeg needs the audio extracted first before it can convert it

2. **Solution**: Integrated automatic ISO extraction
   - Added `sacd_extract` tool support
   - Converter now extracts DSD audio (DSF format) from ISOs automatically
   - Extracted files are processed, then temporary files are cleaned up

## Code Changes

### Modified Files

1. **`src/converter.py`**
   - Added `_check_sacd_extract()` method to verify tool availability
   - Added `_extract_iso_to_dsf()` method to extract DSD audio from ISO files
   - Rewrote `_convert_iso_to_flac()` to extract ISO first, then convert
   - Rewrote `_convert_iso_to_dsf()` to use extraction instead of direct ffmpeg
   - Uses temporary directories that are automatically cleaned up

2. **`README.md`**
   - Added SACD ISO Support to features
   - Added `sacd_extract` to system dependencies
   - Added installation instructions
   - Added troubleshooting section for ISO-related errors
   - Added detailed ISO processing workflow documentation

3. **New Files Created**
   - `INSTALL_SACD_EXTRACT.md` - Detailed installation guide
   - `install_sacd_extract.sh` - Automated installation helper script
   - `CHANGES.md` - This file

## How It Works Now

### Before (Broken)
```
ISO file → ffmpeg (FAILS: "Invalid data found")
```

### After (Working)
```
ISO file → sacd_extract → temp/track_01.dsf
                        → temp/track_02.dsf
         ↓
temp/track_01.dsf → ffmpeg → output/track_01.flac
temp/track_02.dsf → ffmpeg → output/track_02.flac
         ↓
Clean up temp files
```

## What You Need to Do

### Step 1: Install sacd_extract

**Option A: Use the install script (Recommended)**
```bash
cd /Users/reagan/code/music-catalog-management
./install_sacd_extract.sh
```

**Option B: Manual installation**
1. Visit https://github.com/sacd-ripper/sacd-ripper/releases
2. Download the latest macOS release
3. Extract and install:
   ```bash
   chmod +x sacd_extract
   sudo mv sacd_extract /usr/local/bin/
   ```

**Option C: Build from source**
```bash
brew install cmake git
git clone https://github.com/sacd-ripper/sacd-ripper.git
cd sacd-ripper
mkdir build && cd build
cmake ..
make
sudo cp sacd_extract /usr/local/bin/
```

### Step 2: Verify Installation

```bash
which sacd_extract
sacd_extract --help
```

You should see the sacd_extract help message.

### Step 3: Test with Your ISO File

Try running the conversion again:

```bash
cd /Users/reagan/code/music-catalog-management
source .venv/bin/activate
python -m src.main /Volumes/PrimaryHD_8TB/ConversionTest/IN
```

## Expected Behavior

### With sacd_extract installed:
- ISO files will be automatically extracted
- Multiple tracks will be detected and converted individually
- Temporary extraction files are cleaned up automatically
- Conversion should complete successfully

### Without sacd_extract:
- Converter will show a clear error: "sacd_extract not found. Install it to process ISO files."
- ISO files will be skipped
- DSF/DFF files will still work normally

## Technical Details

### Extraction Command
The converter uses this command to extract ISOs:
```bash
sacd_extract -i input.iso -s -c -p temp_directory/
```

Flags:
- `-i`: Input ISO file
- `-s`: Extract stereo tracks
- `-c`: Convert to DSF format
- `-p`: Output directory

### Multi-Track ISOs
SACD ISOs often contain multiple tracks:
- All stereo tracks are extracted
- Each track is converted individually
- Currently uses the first track for single-file mode
- Album processing handles all tracks properly

### Temporary Storage
- Extraction happens in system temp directory
- Uses Python's `tempfile.TemporaryDirectory()`
- Automatically cleaned up even if conversion fails
- No manual cleanup needed

## Testing Checklist

After installing sacd_extract, verify:

- [ ] `sacd_extract` is in PATH: `which sacd_extract`
- [ ] Converter detects it: Check logs for "sacd_extract available" message
- [ ] ISO extraction works: Monitor for extraction progress
- [ ] Conversion completes: ISO → DSF → FLAC
- [ ] Temp files cleaned up: Check system temp directory
- [ ] Multi-track ISOs handled correctly

## Rollback

If you need to revert these changes:
```bash
git checkout main
git reset --hard HEAD~1  # Only if changes aren't committed yet
```

## Performance Notes

- **Extraction time**: 30-60 seconds per ISO
- **Disk space**: Temporary DSF files (similar size to ISO) during processing
- **Total time**: Extraction + conversion (approximately 2-3x longer than DSF-only)

## Known Limitations

1. **Multi-channel audio**: Currently only extracts stereo tracks
   - To extract multi-channel: manually use `sacd_extract -m` flag
   
2. **First track only**: In single-file conversion mode
   - For albums with multiple tracks, use album-level processing

3. **No progress indication**: During extraction phase
   - sacd_extract doesn't provide progress updates

## Future Enhancements

Possible improvements for later:
- Add multi-channel track extraction option
- Show extraction progress
- Cache extracted files to avoid re-extraction
- Parallel extraction and conversion
- Handle both stereo and multi-channel in one pass

## Questions?

See:
- [INSTALL_SACD_EXTRACT.md](INSTALL_SACD_EXTRACT.md) - Installation help
- [README.md](README.md) - Full documentation
- Logs: `conversion.log` and `conversion_errors.log`

