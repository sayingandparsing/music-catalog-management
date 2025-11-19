# Working Directory Architecture Implementation

## Summary

Successfully implemented a robust working directory-based conversion workflow with atomic operations and detailed status tracking for each processing stage.

## Implementation Date

November 19, 2025

## Changes Made

### 1. New Module: `src/working_directory.py`

Created a comprehensive `WorkingDirectoryManager` class that handles:
- Creating `_source` and `_processed` working directories
- Copying source albums to working directories
- Creating empty directory structures for processed output
- Moving/copying to archive and output locations atomically
- Disk space checking before operations
- Cleanup of working directories
- Verification of copied files

**Key Methods:**
- `create_working_dirs()` - Creates working directory pair
- `copy_to_source()` - Copies original to `_source`
- `create_processed_structure()` - Creates empty structure in `_processed`
- `get_converted_tracks()` - Lists already-converted tracks (for resume)
- `copy_to_archive()` - Copies `_source` to archive
- `move_to_output()` - Moves `_processed` to output
- `cleanup_working_dirs()` - Removes working directories
- `check_disk_space()` - Validates sufficient space

### 2. Database Schema Updates: `src/database.py`

**Albums Table:**
- Added `processing_stage` VARCHAR - Current processing stage
- Added `working_source_path` VARCHAR - Path to `_source` working dir
- Added `working_processed_path` VARCHAR - Path to `_processed` working dir

**Processing History Table:**
- Added `working_source_path` VARCHAR - Path to `_source` working dir
- Added `working_processed_path` VARCHAR - Path to `_processed` working dir

Updated `create_album()` and `add_processing_history()` methods to accept new parameters.

### 3. State Manager Updates: `src/state_manager.py`

**AlbumConversionState Dataclass:**
- Added `processing_stage: Optional[str]` - Current stage
- Added `working_source_path: Optional[str]` - Working source path
- Added `working_processed_path: Optional[str]` - Working processed path

**New Methods:**
- `get_resumable_albums()` - Find albums with working directories that can resume
- `get_albums_needing_cleanup()` - Find albums needing cleanup

**Updated Methods:**
- `update_album_status()` - Now accepts working directory paths and processing stage

### 4. Converter Updates: `src/converter.py`

**AudioConverter.convert_file():**
- Added `skip_existing: bool = False` parameter
- If `skip_existing=True`, skips conversion if output already exists (for resume)
- Returns success with "Already converted (skipped)" message for skipped files

### 5. Configuration Updates

**config.yaml and config.example.yaml:**

Added to `paths` section:
```yaml
working_dir: ./working  # Default working directory
```

Added to `processing` section:
```yaml
cleanup_working_on_success: true   # Remove working dirs after success
cleanup_working_on_failure: false   # Keep working dirs after failure for debugging
resume_from_working: true           # Resume from working directories
```

### 6. Main Orchestrator Refactor: `src/main.py`

**ConversionOrchestrator.__init__():**
- Added `WorkingDirectoryManager` initialization
- Working directory configurable via `paths.working_dir` (default: `./working`)

**_process_album() - Complete Rewrite:**

Implemented multi-stage processing workflow:

#### Stage 1: PREPARING
- Check disk space
- Create working directories (`_source` and `_processed`)
- Copy source album to `_source`
- Create empty directory structure in `_processed`
- Update state and database

#### Stage 2: CONVERTING
- Convert tracks from `_source` to `_processed`
- Skip already-converted tracks (resume capability)
- Track individual file status
- Support for retries
- Record conversion history in database

#### Stage 3: ARCHIVING
- Copy `_source` directory to archive location
- Only after all tracks converted successfully
- Create metadata files in archive
- Update database with archive path

#### Stage 4: FINALIZING
- Move `_processed` directory to output location
- Delete original input directory (if configured)
- Run metadata enrichment (if enabled)
- Update database with playback path

#### Stage 5: COMPLETED
- Cleanup working directories (if configured)
- Mark album as completed
- Clear working paths from database

**Error Handling:**
- Each stage wrapped in error handling
- Records exact failure point with stage-specific status codes:
  - `failed_prepare` - Failed during preparation
  - `failed_convert` - Failed during conversion
  - `failed_archive` - Failed during archiving
  - `failed_finalize` - Failed during finalization
- Cleanup working directories on failure (if configured)

**_get_albums_from_session() - Enhanced Resume:**
- Checks for albums with working directories
- Verifies working directories still exist
- Resumes from working directories if available
- Falls back to re-scanning original if working dirs lost
- Logs resume status for each album

## Processing Stage Status Codes

- `preparing` - Creating working directories
- `converting` - Converting tracks
- `archiving` - Moving to archive
- `finalizing` - Moving to output, removing source
- `completed` - All done, cleaned up
- `failed_prepare` - Failed during preparation
- `failed_convert` - Failed during conversion
- `failed_archive` - Failed during archiving
- `failed_finalize` - Failed during finalization

## Benefits

### 1. Atomic Operations
All-or-nothing commit to archive and output. No partial states left in output directories.

### 2. Precise Resume
- Continue from exact track where interrupted
- Skip already-converted tracks automatically
- Resume from any stage (preparing, converting, archiving, finalizing)

### 3. Clear State
Easy to see progress by inspecting working directories:
- `_source` contains original files
- `_processed` accumulates converted tracks

### 4. Safe Rollback
Just delete working directories to roll back failed conversions.

### 5. Disk Space Aware
Checks available disk space before starting conversion.

### 6. Detailed Tracking
- Know exactly which stage failed
- Working directory paths stored in database and state
- Full processing history with working directory references

## Resume Behavior

When running with `--resume`:

1. Load previous session from state manager
2. Check `resume_from_working` config (default: true)
3. Find albums with working directories
4. For each album:
   - Verify working directories exist
   - If `_processed` exists: Skip already-converted tracks, continue with remaining
   - If `_source` exists but `_processed` doesn't: Re-start conversion
   - If neither exists but original still does: Re-process from scratch
   - If no source available: Skip with warning

## Testing Recommendations

1. **Normal Operation**: Test complete album conversion end-to-end
2. **Resume After Interruption**: Kill process during conversion, verify resume works
3. **Disk Space Handling**: Test with insufficient disk space
4. **Partial Conversion**: Interrupt during track conversion, verify resume continues
5. **Cleanup Behavior**: Verify working directories cleaned up based on config
6. **Archive Failure**: Test archive failure handling and cleanup
7. **Multiple Albums**: Test batch processing with resume
8. **Working Dir Loss**: Delete working dirs, verify fallback to original

## Migration Notes

**Database Migration:**
Existing databases will automatically add new columns when tables are created. No manual migration needed.

**State Files:**
Existing state files will load successfully. Missing fields will default to None.

**Configuration:**
New config options have sensible defaults. Existing configs will work without changes.

## Default Settings

- `paths.working_dir`: `./working`
- `processing.cleanup_working_on_success`: `true`
- `processing.cleanup_working_on_failure`: `false`
- `processing.resume_from_working`: `true`

## Files Modified

1. `src/working_directory.py` (NEW)
2. `src/database.py`
3. `src/state_manager.py`
4. `src/converter.py`
5. `src/main.py`
6. `config.yaml`
7. `config.example.yaml`

## Lines of Code

- New module: ~560 lines (`working_directory.py`)
- Main orchestrator: ~300 lines rewritten
- Database: ~30 lines added
- State manager: ~60 lines added
- Converter: ~10 lines added
- Config: ~15 lines added

**Total: ~975 lines of new/modified code**

