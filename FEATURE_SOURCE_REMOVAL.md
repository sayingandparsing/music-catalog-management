# Source File Removal Feature - Implementation Summary

## Overview

Added functionality to automatically remove original source files from the input directory after successful archiving and conversion. This addresses the user's request to clean up the input directory while maintaining safe archives of the originals.

## Changes Made

### 1. Configuration Files

#### `config.yaml`
Added new configuration option:
```yaml
processing:
  remove_source_after_conversion: true
```

#### `config.example.yaml`
Added the same option with detailed comments and set to `false` by default for safety:
```yaml
processing:
  remove_source_after_conversion: false  # Start disabled, enable after testing
```

### 2. Main Processing Logic (`src/main.py`)

Modified `_process_album()` method to add cleanup step after successful conversion:

**Location**: Lines 588-617

**Logic**:
1. Only executes if `remove_source_after_conversion: true` in config
2. Runs after all these steps complete successfully:
   - Archiving
   - Conversion
   - Metadata enrichment (if enabled)
3. Uses `shutil.rmtree()` to remove entire album directory
4. Logs success or failure
5. Records operation in database (if enabled)
6. **Does not fail the album** if removal fails (logs warning instead)

### 3. Documentation

#### New Files:
- **`WORKFLOW_GUIDE.md`**: Comprehensive guide covering:
  - How the feature works
  - Safety considerations
  - Example workflows
  - Dry-run testing
  - Failure handling
  - Recovery procedures
  - Best practices

#### Modified Files:
- **`README.md`**: 
  - Added feature to Features list
  - Added configuration example
  - Added safety warnings section

## Safety Features

1. **Opt-in**: Feature is disabled by default
2. **Sequential execution**: Only removes after archive and conversion succeed
3. **Database tracking**: All cleanup operations are logged
4. **Graceful failure**: If removal fails, album is still marked successful
5. **Dry-run support**: Test without actually deleting files
6. **Comprehensive logging**: All operations are logged with timestamps

## Workflow Example

With configuration:
```yaml
paths:
  archive_dir: /Volumes/Archive
  output_dir: /Volumes/Output

processing:
  remove_source_after_conversion: true
```

**Before**:
```
/Input/Album1/       → Original files
/Archive/            → Empty
/Output/             → Empty
```

**After successful processing**:
```
/Input/              → Empty (Album1 removed)
/Archive/Album1_20250115_120000/  → Complete backup
/Output/Album1/      → Converted files
```

## Testing Recommendations

1. **Test with dry-run first**:
   ```bash
   python -m src.main /path/to/music --dry-run
   ```

2. **Test with one album** with feature disabled, verify archive

3. **Enable feature** and test with one album

4. **Verify archive integrity** before processing large batches

5. **Ensure archive is backed up** to separate drive/cloud

## Database Schema Impact

New operation type in `processing_history` table:
- `operation_type: 'cleanup'`
- Records success/failure of source file removal
- Includes error messages if removal fails

## Error Handling

If removal fails:
- Warning logged (not error)
- Database records failure with error message
- Album still marked as successfully processed
- Archive and converted files remain intact
- User can manually clean up source files later

## Rollback Procedure

If needed, originals can be restored from archive:
1. Locate archive with timestamp: `Archive/AlbumName_YYYYMMDD_HHMMSS/`
2. Copy contents back to input directory
3. Archive remains intact for future reference

## Future Enhancements (Not Implemented)

Potential additions for future versions:
- Option to move instead of copy-then-delete
- Trash/recycle bin support instead of permanent deletion
- Selective file removal (keep certain extensions)
- Confirmation prompt for first-time use
- Archive verification before removal

## Implementation Notes

- Uses Python's `shutil.rmtree()` for directory removal
- Import is inline to avoid overhead when feature is disabled
- No performance impact when feature is disabled (config check only)
- Compatible with existing state management and resume functionality

