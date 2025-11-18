# Installing sacd_extract for SACD ISO Processing

Your DSD Music Converter now supports automatic SACD ISO extraction using the `sacd_extract` tool.

## What Changed

The converter has been updated to automatically:
1. Extract DSD audio (DSF files) from SACD ISO images using `sacd_extract`
2. Convert the extracted DSF files to FLAC using ffmpeg
3. Clean up temporary files automatically

This solves the "Invalid data found when processing input" error you were seeing with ISO files.

## Installation Instructions for macOS

### Option 1: Download Pre-built Binary (Recommended)

1. **Download sacd_extract for macOS:**
   - Visit: https://github.com/sacd-ripper/sacd-ripper/releases
   - Download the latest macOS release (look for `sacd_extract-macos` or similar)

2. **Install the binary:**
   ```bash
   # Download and extract (adjust version as needed)
   cd ~/Downloads
   # If it's a zip file
   unzip sacd_extract-macos.zip
   
   # Make it executable
   chmod +x sacd_extract
   
   # Move to a location in your PATH
   sudo mv sacd_extract /usr/local/bin/
   
   # Verify installation
   sacd_extract --help
   ```

### Option 2: Build from Source

If a pre-built binary isn't available:

```bash
# Install build dependencies via Homebrew
brew install cmake git

# Clone the repository
git clone https://github.com/sacd-ripper/sacd-ripper.git
cd sacd-ripper

# Build
mkdir build && cd build
cmake ..
make

# Install
sudo cp sacd_extract /usr/local/bin/

# Verify
sacd_extract --help
```

## Verification

After installation, verify both tools are available:

```bash
# Check sacd_extract
which sacd_extract
sacd_extract --help

# Check ffmpeg (should already be installed)
which ffmpeg
ffmpeg -version
```

## Testing the Converter

Once `sacd_extract` is installed, try running your conversion again:

```bash
cd /Users/reagan/code/music-catalog-management
source .venv/bin/activate
python -m src.main /Volumes/PrimaryHD_8TB/ConversionTest/IN
```

## What Happens Now

When the converter encounters an ISO file, it will:

1. **Extract**: Use `sacd_extract` to extract DSF files to a temporary directory
2. **Convert**: Convert the extracted DSF file(s) to FLAC using your configured settings
3. **Cleanup**: Automatically remove temporary files

### Multi-Track ISOs

SACD ISOs often contain multiple tracks. The current implementation:
- Extracts all stereo tracks from the ISO
- For single-file conversions, uses the first track
- For album processing, all tracks should be detected and converted individually

## Troubleshooting

### "sacd_extract not found"
- Verify installation: `which sacd_extract`
- Make sure `/usr/local/bin` is in your PATH
- Try running with full path: `/usr/local/bin/sacd_extract --help`

### "Permission denied" when running sacd_extract
```bash
chmod +x /usr/local/bin/sacd_extract
```

### macOS Security Warning
If macOS blocks the binary:
1. Go to System Preferences → Security & Privacy
2. Click "Allow Anyway" for sacd_extract
3. Try running again

## Alternative: Manual Extraction

If you prefer to manually extract ISOs before conversion:

1. Extract ISOs manually using sacd_extract:
   ```bash
   sacd_extract -i input.iso -s -c -p output_directory/
   ```

2. Then run the converter on the extracted DSF files

## Need Help?

If you encounter issues:
1. Check that sacd_extract is in your PATH: `echo $PATH`
2. Verify the binary is executable: `ls -l /usr/local/bin/sacd_extract`
3. Check converter logs for detailed error messages

