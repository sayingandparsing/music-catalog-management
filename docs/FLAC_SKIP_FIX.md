# Fix: Skip Albums with No Convertible Files

## Problem

Albums containing only FLAC files were being processed even when FLAC standardization was disabled. This resulted in:

1. Albums being copied to working directories unnecessarily
2. Original files being archived and removed
3. No output files being created in the final location
4. FLAC files "disappearing" from the output

## Root Cause

When `conversion.flac_standardization.enabled` is set to `false`:
- The converter would skip FLAC files (return "skipped" status)
- But the processing workflow would still:
  - Create working directories
  - Copy source files to working directory
  - Archive originals
  - Remove originals from source location
  - Move empty processed directory to output

Result: FLAC-only albums would end up with no music files in the output.

## Solution

Added pre-processing check to skip albums with no convertible files **before** they enter the working directory stage.

### Changes Made

1. **Added `_has_convertible_files()` method** in `src/main.py`:
   - Checks if album has any files that can be converted based on current mode and settings
   - For `iso_dsf_to_flac` mode:
     - Convertible: `.iso`, `.dsf`, `.dff`
     - Convertible: `.flac` (only if `flac_standardization.enabled` is `true`)
   - For `iso_to_dsf` mode:
     - Convertible: `.iso` only

2. **Updated `_process_albums()` method** in `src/main.py`:
   - Added check before processing each album
   - Albums with no convertible files are skipped early
   - Skipped albums are logged with file types found
   - Original files remain completely untouched

### Behavior

**Before Fix:**
```
[1/6] Processing album: Best Album (FLAC)
  [PREPARING] Creating working directories...
  [CONVERTING] Processing tracks...
  [ARCHIVING] Archiving original files...
  [FINALIZING] Moving to output location...
✓ Album completed: Best Album (0 files)  ← Empty output!
```

**After Fix:**
```
[1/6] Skipping album: Best Album (FLAC)
  No convertible files found (contains: .flac)
```

### Configuration

This fix respects your configuration settings:

```yaml
conversion:
  mode: iso_dsf_to_flac
  flac_standardization:
    enabled: false  # FLAC files not convertible
```

With `enabled: true`, FLAC files would be convertible and albums would be processed.

## Testing

Added integration test: `test_skip_albums_with_no_convertible_files`
- Creates album with only FLAC files
- Verifies album is skipped
- Confirms no working directories created
- Confirms original files remain untouched

## Statistics

Skipped albums are tracked in statistics:
- `albums_skipped` counter is incremented
- These albums don't count as "failed"
- Clear logging indicates why album was skipped

## Related Files

- `src/main.py` - Added skip logic
- `tests/test_integration.py` - Added test coverage
- `docs/FLAC_SKIP_FIX.md` - This document

