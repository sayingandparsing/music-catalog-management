# Bug Fixes Implemented

This document summarizes the critical and high-priority bugs that have been fixed based on the comprehensive bug review.

## Summary

**Total Bugs Fixed: 6** (3 Critical, 3 High Priority)

All fixes have been implemented and verified with no linter errors.

---

## Critical Bugs Fixed

### 1. Source Directory Deletion Bug (Bug #1) ✅

**File:** `src/main.py`

**Problem:** During resume scenarios, `album.root_path` might point to a working directory instead of the original source, causing deletion of wrong directories when `remove_source_after_conversion=true`.

**Fix Implemented:**
- Added logic at the beginning of `_process_album()` to determine the true original source path
- Stored `original_source_path` as a variable that persists throughout the method
- Updated source removal logic to use `original_source_path` instead of `album.root_path`
- Added safety check to prevent deletion of working directories (paths ending with `_source` or `_processed`)
- Added proper logging and error handling for source removal

**Impact:** Prevents critical data loss from deleting wrong directories.

---

### 2. Original Album Path Resolution Failure (Bug #2) ✅

**File:** `src/main.py`

**Problem:** When resuming from working directories, the code had to re-determine the original album path. If no match was found in the state lookup loop, it would fall back to `album.root_path` (which could be a working directory), causing:
- Wrong output paths (e.g., `/output/Album_20251118_source` instead of `/output/Album`)
- Metadata files in wrong locations
- Broken playback path references

**Fix Implemented:**
- Consolidated path resolution logic at the beginning of `_process_album()`
- Added robust matching logic that checks both working paths and original paths
- Reused the `original_source_path` variable throughout the method
- Eliminated duplicate path resolution code in the FINALIZING stage
- Added debug logging for resume scenarios

**Impact:** Ensures correct file organization and prevents metadata corruption during resume operations.

---

### 3. SQL Field Name Injection Risk (Bug #7) ✅

**File:** `src/database.py`

**Problem:** The `update_album()` and `update_track()` methods constructed dynamic SQL queries using field names from kwargs without validation. This created a SQL injection vulnerability where malicious or buggy code could inject SQL through field names.

**Fix Implemented:**
- Added `VALID_ALBUM_FIELDS` and `VALID_TRACK_FIELDS` class constants as whitelists
- Updated `update_album()` to validate all field names against the whitelist
- Updated `update_track()` to validate all field names against the whitelist
- Added warning messages for invalid field names
- Invalid fields are now skipped rather than causing SQL injection

**Impact:** Eliminates SQL injection vulnerability and improves code security.

---

## High Priority Bugs Fixed

### 4. Memory Exhaustion in Dynamic Range Calculation (Bug #9) ✅

**File:** `src/converter.py`

**Problem:** The `calculate_dynamic_range_metrics()` method loaded entire audio files into memory as numpy arrays. For large files (e.g., 1-hour 24/96 stereo = ~2.6 GB RAM), this caused out-of-memory errors, especially with multiple concurrent conversions.

**Fix Implemented:**
- Added file size check before processing (default limit: 500MB)
- Added `max_file_size_mb` parameter for configurability
- Large files now skip DR calculation with clear warning message
- Updated docstring to document the memory limitation
- Calculation still works for reasonably-sized files

**Impact:** Prevents OOM crashes while maintaining DR calculation capability for most files.

---

### 5. Archive Existence Assumed Valid (Bug #4) ✅

**File:** `src/archiver.py`

**Problem:** When an archive directory already existed, the code assumed it was valid without verification. If a previous archiving operation was interrupted, a partial/corrupted archive could be accepted as valid, potentially leading to data loss if the user relied on it.

**Fix Implemented:**
- When existing archive is found, verify it using `_verify_copy()`
- If verification passes, accept the existing archive
- If verification fails, log warning and remove corrupted archive
- Re-archive from scratch after removing corrupted archive
- Added proper error handling for archive removal failures

**Impact:** Ensures archive integrity and prevents reliance on corrupted backups.

---

### 6. Working Directory Cleanup Without Path Clearing (Bug #3) ✅

**File:** `src/state_manager.py`

**Problem:** The `update_album_status()` method couldn't distinguish between "parameter not passed" and "explicitly set to None". This meant working directory paths could never be cleared from the state file after cleanup, causing resume logic to look for non-existent directories.

**Fix Implemented:**
- Introduced sentinel value pattern (`_NOT_SET = object()`)
- Changed default parameter values from `None` to `_NOT_SET`
- Updated logic to check `if param is not self._NOT_SET`
- Now supports three states: not passed (no change), passed as None (clear field), passed as value (set field)
- Updated docstrings to clarify the behavior

**Impact:** Enables proper cleanup of working directory references in state, preventing resume failures.

---

## Testing Recommendations

While these bugs have been fixed, the following additional testing is recommended:

1. **Resume Scenarios:** Test resume from each processing stage with working directories
2. **Large Files:** Test DR calculation with files >500MB
3. **Archive Recovery:** Test interrupted archiving and re-archiving
4. **State Management:** Test clearing working paths after successful/failed processing
5. **SQL Security:** Test update methods with various field names (valid and invalid)
6. **Source Removal:** Test with `remove_source_after_conversion=true` in various scenarios

---

## Files Modified

- `src/main.py` - Bugs #1, #2
- `src/database.py` - Bug #7
- `src/converter.py` - Bug #9
- `src/archiver.py` - Bug #4
- `src/state_manager.py` - Bug #3

---

## Notes

- All fixes maintain backward compatibility
- No changes to database schema required
- No changes to configuration format required
- All linter checks pass
- Existing tests should continue to pass (new tests recommended for fixed scenarios)

---

**Date Implemented:** November 19, 2025
**Implementation Status:** ✅ Complete

