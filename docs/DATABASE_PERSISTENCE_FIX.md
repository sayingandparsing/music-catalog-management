# Database Persistence Fix

## Issue
The database was not persisting data after runs. Records would be lost when the application closed.

## Root Cause
The database code was using DuckDB's `execute()` method without explicit `commit()` calls. While DuckDB has auto-commit for individual statements, it's critical to explicitly commit changes, especially before closing the connection, to ensure all changes are flushed to disk.

## Solution
Added explicit commit handling throughout the codebase:

### 1. Database Module (`src/database.py`)
- Added `commit()` method to explicitly commit transactions
- Modified `close()` method to commit before closing the connection
- This ensures all pending changes are written to disk before the connection is closed

```python
def commit(self):
    """Commit current transaction."""
    if self.conn:
        self.conn.commit()

def close(self):
    """Close database connection."""
    if self.conn:
        # Ensure all changes are committed before closing
        self.conn.commit()
        self.conn.close()
        self.conn = None
```

### 2. Main Processing Flow (`src/main.py`)
Added commits at strategic points throughout album processing:

#### Success Paths:
- After creating album records
- After updating album with working paths
- After adding processing history (convert started)
- After creating each track record
- After updating album with SACD metadata
- After successful conversion completion
- After archiving completion
- After updating album with archive path
- After finalizing and updating playback path
- After metadata enrichment
- After cleanup operations
- After marking album as finalized

#### Failure Paths:
- After recording conversion failures
- After recording archive failures
- After recording finalize failures
- After general exception handling

### 3. Deduplication Module (`src/deduplication.py`)
Added commits after database updates in:
- `reconcile_moved_album()` - when updating album paths after moves
- `register_album_location()` - when registering album locations

## Impact
- **Data Persistence**: All database operations now reliably persist to disk
- **Crash Recovery**: Even if the application crashes, committed data is preserved
- **Transaction Safety**: Explicit commits provide clear transaction boundaries
- **Resume Capability**: Properly persisted data enables reliable resume functionality

## Testing
To verify the fix works:

1. Run a conversion on an album
2. Check the database immediately after:
   ```bash
   sqlite3 music_catalog.duckdb "SELECT * FROM albums;"
   ```
   Or use DuckDB CLI:
   ```bash
   duckdb music_catalog.duckdb -c "SELECT * FROM albums;"
   ```

3. The album record should persist even after the application closes

## Files Modified
- `src/database.py` - Added commit() method and commit before close
- `src/main.py` - Added ~15 commit() calls at key points
- `src/deduplication.py` - Added 2 commit() calls after updates

## Best Practices Applied
1. **Explicit Commits**: Always commit after important operations
2. **Commit Before Close**: Ensure data is persisted before closing connections
3. **Commit After Failures**: Record failure states for debugging and recovery
4. **Transaction Boundaries**: Clear separation of operations with commits

## Related Documentation
- See `ERROR_HANDLING_FIX.md` for related error handling improvements
- See `WORKING_DIRECTORY_IMPLEMENTATION.md` for state management details

