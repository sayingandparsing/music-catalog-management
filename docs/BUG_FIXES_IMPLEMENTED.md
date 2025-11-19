# Bug Fixes Implemented

This document details all bug fixes implemented from the comprehensive bug review.

## Summary

**Total Fixes: 18 bugs**
- **Critical Priority: 2 bugs**
- **High Priority: 4 bugs**  
- **Medium Priority: 3 bugs**
- **Low Priority: 9 bugs**

---

## Critical Priority Fixes

### Bug #1: Source Directory Deletion Bug
**File:** `src/main.py`  
**Severity:** CRITICAL (Data Loss Risk)

**Problem:**  
During resume scenarios, `album.root_path` could point to a working directory instead of the original source, potentially deleting temporary working directories or the wrong directory entirely.

**Fix:**
- Introduced `original_source_path` variable at the start of `_process_album()` method
- Added logic to detect when `album.root_path` is a working directory by checking session state
- Used `original_source_path` consistently for database updates, output path construction, and source cleanup
- Added safety check to prevent deletion of paths ending with `_source` or `_processed`
- Enhanced logging to track which path is being used for cleanup

**Impact:**  
Prevents accidental deletion of working directories and ensures correct source path is used for all operations.

---

### Bug #2: Original Album Path Resolution Failure
**File:** `src/main.py`  
**Severity:** CRITICAL (Data Integrity)

**Problem:**  
If no match was found when resolving the original album path (e.g., state corrupted or paths mismatched), the code would use a working directory path, leading to incorrect output paths and metadata file locations.

**Fix:**
- Implemented comprehensive path resolution logic that checks both `working_source_path` and `album_path` in session state
- Used resolved `original_source_path` for output directory naming
- Added debug logging to track path resolution during resume operations
- Ensured database records store the correct original source path, not working directory paths

**Impact:**  
Ensures correct output paths and metadata locations even during complex resume scenarios.

---

## High Priority Fixes

### Bug #3: Working Directory Cleanup Without Path Clearing
**File:** `src/state_manager.py`  
**Severity:** HIGH (State Management)

**Problem:**  
The `update_album_status()` method couldn't explicitly clear working paths by setting them to `None` because it only updated truthy values. This caused resume logic to look for non-existent directories after cleanup.

**Fix:**
- Introduced sentinel value `_NOT_SET = object()` to distinguish "not provided" from "explicitly None"
- Updated method signature to use sentinel as default for optional parameters
- Modified update logic to check against sentinel instead of truthiness
- Working paths can now be explicitly cleared from state after successful cleanup

**Impact:**  
Proper state management after working directory cleanup, preventing resume errors.

---

### Bug #4: Archive Existence Assumed Valid
**File:** `src/archiver.py`  
**Severity:** HIGH (Data Integrity)

**Problem:**  
If a previous archiving operation was interrupted, a partial/corrupted archive directory might exist. The code assumed any existing archive was valid without verification.

**Fix:**
- Added verification check using existing `_verify_copy()` method when archive already exists
- If verification fails, the corrupted archive is removed and archiving is retried
- Enhanced logging to warn when corrupted archives are detected
- Ensures archive integrity before trusting existing archives

**Impact:**  
Protects against relying on corrupted or incomplete archives, ensuring data backup integrity.

---

### Bug #7: SQL Field Name Injection Risk
**File:** `src/database.py`  
**Severity:** HIGH (Security)

**Problem:**  
While SQL values were parameterized, field names came from kwargs keys without validation, allowing potential SQL injection through malicious or buggy field names.

**Fix:**
- Added `VALID_ALBUM_FIELDS` whitelist with all legitimate album field names
- Added `VALID_TRACK_FIELDS` whitelist with all legitimate track field names
- Implemented validation in `update_album()` and `update_track()` methods
- Invalid field names are logged as warnings and skipped
- SQL queries are now constructed only with validated field names

**Impact:**  
Prevents SQL injection attacks and protects against bugs from invalid field names.

---

### Bug #9: Memory Exhaustion in Dynamic Range Calculation
**File:** `src/converter.py`  
**Severity:** HIGH (Resource Management)

**Problem:**  
The `calculate_dynamic_range_metrics()` function loaded entire audio files into memory as numpy arrays. For large DSD files converted to 24/96, this could consume 2+ GB of RAM per file, causing OOM errors.

**Fix:**
- Added `max_file_size_mb` parameter (default: 500MB) to `calculate_dynamic_range_metrics()`
- Added file size check before loading audio into memory
- Files exceeding the limit are skipped with a clear warning message
- Updated docstring to document memory considerations and size limit

**Impact:**  
Prevents out-of-memory errors when processing large audio files, improving stability.

---

## Medium Priority Fixes

### Bug #6: ISO Output Verification Incomplete
**File:** `src/converter.py`  
**Severity:** MEDIUM (Data Integrity)

**Problem:**  
ISO file output verification had multiple issues:
- Didn't verify files were non-empty
- Didn't check if expected number of tracks were created
- Could pass if unrelated FLAC/DSF files already existed
- Single-track ISO files weren't verified at all

**Fix:**
- Modified `_convert_iso_to_flac()` to return expected track count
- Updated return type to `Tuple[bool, Optional[str], int]`
- Enhanced verification to check:
  - Files are non-empty (>100 bytes)
  - Track count matches expected count from extraction
  - Single-track ISOs are also verified
- Added specific error messages for track count mismatches
- Applied verification to both multi-track and single-track scenarios

**Impact:**  
Ensures ISO conversions produce complete and valid output files.

---

### Bug #15: Skip Existing Logic Flawed for ISO Files
**File:** `src/converter.py`  
**Severity:** MEDIUM (Logic Error)

**Problem:**  
For ISO files that create multiple output tracks, checking if a single `output_path` exists didn't make sense. The actual outputs are individual track files, not the generic `output_path`. This could skip entire ISOs even if some tracks were missing.

**Fix:**
- Added special handling for ISO files in skip_existing logic
- For ISOs, checks if any valid output tracks exist in the output directory
- Searches for all files matching expected extension (`.flac` or `.dsf`)
- Filters to non-empty files (>100 bytes)
- If valid tracks exist, skips conversion with informative message showing track count
- Non-ISO files continue to use standard single-file check

**Impact:**  
Proper resume behavior for multi-track ISO files, preventing incomplete conversions.

---

### Bug #10: Disk Space Estimation Inaccurate for ISO
**File:** `src/working_directory.py`  
**Severity:** MEDIUM (Resource Management)

**Problem:**  
Space estimation used 3x multiplier for all files, but ISO workflow requires more:
1. Copy ISO to working_source (1x)
2. Extract ISO to DSF files in temp (1x+, can be larger)
3. Convert DSF to FLAC in working_processed (0.5x)
4. Copy to archive (1x)
5. Temporary buffers (1x)

Actual requirement could be 4x-5x, causing "insufficient disk space" errors even when estimate passed.

**Fix:**
- Updated `estimate_required_space()` to detect ISO files during directory scan
- Tracks whether album contains any `.iso` files
- Uses 5x multiplier for ISO-containing albums
- Uses 3x multiplier for regular files (unchanged)
- Enhanced docstring to document ISO-specific space requirements

**Impact:**  
Accurate disk space checks prevent conversion failures mid-process for large ISO files.

---

## Low Priority Fixes

### Bug #5: Duplicate Album ID Reused Without Validation
**File:** `src/deduplication.py`  
**Severity:** LOW (Data Integrity)

**Problem:**  
When a duplicate album was found by checksum, its ID was reused without checking if the original processing completed successfully. If the duplicate existed but processing failed (no `playback_path`), reusing its ID could cause confusion.

**Fix:**
- Added validation to check if duplicate album has a `playback_path` before reusing ID
- If duplicate is incomplete (no playback_path), generate a new ID instead
- Added warning message when skipping incomplete duplicates
- Ensures only successfully processed albums have their IDs reused

**Impact:**  
Prevents ID reuse from failed/incomplete album processing, ensuring data consistency.

---

### Bug #8: Processing Stage Value Inconsistency
**File:** `src/main.py`  
**Severity:** LOW (Data Consistency)

**Problem:**  
After successful completion, processing stage was set to 'completed', but this didn't match the multi-stage workflow stages (preparing, converting, archiving, finalizing). The 'completed' value was not part of the documented processing stages.

**Fix:**
- Changed `processing_stage='completed'` to `processing_stage='finalized'`
- Now matches the last actual processing stage name
- Maintains consistency with the documented workflow stages

**Impact:**  
Consistent processing stage values that align with the multi-stage workflow design.

---

### Bug #11: Temporary Directory Cleanup Documentation
**File:** `src/converter.py`  
**Severity:** LOW (Documentation)

**Problem:**  
The code used context managers for temp directory cleanup, but didn't document that SIGKILL could leave temp directories behind. This is an inherent limitation of the approach but should be documented.

**Fix:**
- Added comments documenting that context managers ensure cleanup on normal exit and exceptions
- Noted that SIGKILL can leave temp directories (`/tmp/sacd_extract_*`)
- Included manual cleanup command for users: `rm -rf /tmp/sacd_extract_*`

**Impact:**  
Users are now aware of the limitation and know how to clean up orphaned temp directories.

---

### Bug #12: SACD Metadata Discovery Truncation
**File:** `src/sacd_metadata_parser.py`  
**Severity:** LOW (Metadata Parsing)

**Problem:**  
Only the first 1000 characters of potential metadata files were read to check for markers. Files with long headers or preambles (>1000 chars) before metadata markers appeared would not be detected as valid metadata files.

**Fix:**
- Increased read size from 1000 to 50,000 characters
- Added comment explaining the rationale for the larger buffer
- Still maintains 10MB file size limit for safety

**Impact:**  
More robust SACD metadata file detection, handles files with verbose headers.

---

### Bug #13: Lowpass Filter Applied During Upsampling
**File:** `src/converter.py`  
**Severity:** LOW (Audio Processing Logic)

**Problem:**  
The lowpass filter was applied whenever sample rates differed, but this included upsampling scenarios where a lowpass filter serves no purpose and could remove valid high-frequency content. Lowpass filters are only needed during downsampling to prevent aliasing.

**Fix:**
- Added check to determine if operation is downsampling (source rate > target rate)
- Lowpass filter now only applied during downsampling, not upsampling
- Added explanatory comment about why this distinction matters

**Impact:**  
Correct audio processing that only applies lowpass when needed (downsampling).

---

### Bug #16: No Validation of Conversion Mode
**File:** `src/converter.py`  
**Severity:** LOW (Input Validation)

**Problem:**  
The conversion mode parameter accepted any string without validation. Invalid modes were only caught later during `convert_file()`, after the converter was fully initialized, leading to confusing error messages.

**Fix:**
- Added `valid_modes` list: `['iso_dsf_to_flac', 'iso_to_dsf']`
- Validation in `__init__` method before assignment
- Raises `ValueError` with clear message showing valid modes
- Fails fast with helpful error message

**Impact:**  
Better error messages and earlier detection of configuration mistakes.

---

### Bug #17: FLAC Quality Comparison Logic Ambiguous
**File:** `src/converter.py`  
**Severity:** LOW (Logic Clarity)

**Problem:**  
Used OR logic to determine if source FLAC was "higher quality" than target. This created ambiguous cases like 16-bit/192kHz vs 24-bit/88.2kHz (higher sample rate but lower bit depth). With OR logic, this would skip conversion, but user might want the higher bit depth.

**Fix:**
- Changed from OR to AND logic for quality comparison
- Source is now considered "higher quality" only if BOTH sample rate AND bit depth are higher
- Added comment explaining the rationale and avoiding ambiguous cases
- More conservative approach that's less likely to cause issues

**Impact:**  
Clearer quality comparison logic that avoids ambiguous mixed-quality scenarios.

---

### Bug #18: Database Connection Not Closed on Early Exit
**File:** `src/main.py`  
**Severity:** LOW (Resource Cleanup)

**Problem:**  
Database connection was only closed at the end of successful `run()` execution. Early returns (e.g., no albums found) or exceptions would leave the database connection open, potentially causing resource leaks.

**Fix:**
- Wrapped main logic in try-except-finally block
- Moved `database.close()` to finally block
- Ensures database cleanup on all exit paths: success, error, or exception
- Follows proper resource management pattern

**Impact:**  
Proper database connection cleanup regardless of exit path, preventing resource leaks.

---

### Bug #19: Duration Calculation Exception on Early Error
**File:** `src/converter.py`  
**Severity:** LOW (Exception Handling)

**Problem:**  
If an exception occurred in `convert_file()` before `start_time` was set (e.g., during initial validation), the exception handler would fail with `NameError: name 'start_time' is not defined`.

**Fix:**
- Moved `start_time = time.time()` to the very beginning of the method
- Now initialized immediately after docstring, before any validation code
- Ensures start_time exists for all code paths
- Removed duplicate start_time assignment later in the method

**Impact:**  
Exception handler works correctly even for errors during initial validation.

---

## Files Modified

1. **src/main.py**
   - Fixed source directory deletion logic (Bug #1)
   - Fixed original album path resolution (Bug #2)
   - Fixed processing stage values (Bug #8)
   - Added database connection cleanup in finally block (Bug #18)

2. **src/state_manager.py**
   - Fixed working path clearing logic (Bug #3)

3. **src/archiver.py**
   - Added archive validation before use (Bug #4)

4. **src/database.py**
   - Added SQL field name whitelisting (Bug #7)

5. **src/converter.py**
   - Added memory limit for dynamic range calculation (Bug #9)
   - Enhanced ISO output verification (Bug #6)
   - Fixed skip existing logic for ISOs (Bug #15)
   - Added temp directory cleanup documentation (Bug #11)
   - Fixed lowpass filter to only apply during downsampling (Bug #13)
   - Added conversion mode validation (Bug #16)
   - Fixed FLAC quality comparison to use AND logic (Bug #17)
   - Fixed duration calculation exception handling (Bug #19)

6. **src/working_directory.py**
   - Improved disk space estimation for ISOs (Bug #10)

7. **src/deduplication.py**
   - Added validation for duplicate album ID reuse (Bug #5)

8. **src/sacd_metadata_parser.py**
   - Increased metadata file read size from 1000 to 50000 chars (Bug #12)

---

## Testing Recommendations

While these fixes address the identified bugs, comprehensive testing is recommended:

1. **Resume Scenarios**: Test pause/resume at each processing stage
2. **ISO Files**: Test both single-track and multi-track ISOs
3. **Large Files**: Test with files approaching memory and disk limits
4. **Corrupted State**: Test recovery from interrupted operations
5. **Security**: Test with unusual field names (though now protected)
6. **Edge Cases**: Empty files, permission errors, disk full scenarios

---

## Future Considerations

The comprehensive review identified additional potential issues that were not addressed in this implementation:

- **Bug #14**: State file atomic write race conditions (very low risk in single-process usage)
- **Bug #20**: FFmpeg thread count 0 handling documentation
- **Bug #21**: Symlink handling in music directories
- **Bug #22**: File lock mechanism for database (for multi-process scenarios)
- **Bug #23**: Album metadata checksum file order considerations

These are extremely low-priority edge cases that are unlikely to affect normal usage.

---

*Last Updated: 2025-11-19*
*Implementation Session: Comprehensive Bug Review*
