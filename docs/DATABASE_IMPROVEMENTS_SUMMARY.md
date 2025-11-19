# Database Improvements Summary

## Overview
This document summarizes the database improvements made to enhance data persistence and metadata extraction.

## Changes Made

### 1. Database Persistence Fix ✅
**Problem:** Database was not persisting data after runs.

**Solution:** Added explicit `commit()` calls throughout the codebase:
- Added `commit()` method to `MusicDatabase` class
- Modified `close()` to commit before closing connection
- Added commits after all database operations (~20 locations)
- Added commits in both success and failure paths

**Files Modified:**
- `src/database.py`
- `src/main.py`
- `src/deduplication.py`

**Documentation:** [DATABASE_PERSISTENCE_FIX.md](DATABASE_PERSISTENCE_FIX.md)

---

### 2. Metadata Extraction Improvements ✅
**Problem:** 
- Artist field was not populated in albums table
- Album name was always just the folder name
- No tracking of album transformations (origin → processed)

**Solution:** 

#### A. Album-Level Metadata Extraction
Created `_extract_album_metadata()` method with priority system:
1. SACD metadata files (Disc_summary.txt, foo_dr.txt)
2. FLAC embedded tags (artist, albumartist, album)
3. Folder name (fallback for album name)

#### B. Database Schema Updates
Added to `processing_history` table:
- `album_id_origin` - Original album ID (source files)
- `album_id_processed` - Processed album ID (converted files)

#### C. Processing History Enhancements
Updated all `add_processing_history()` calls to include:
- `album_id_origin` - Always populated with source album ID
- `album_id_processed` - Populated after conversion completes

**Files Modified:**
- `src/database.py` - Schema and method updates
- `src/main.py` - Metadata extraction and tracking

**Documentation:** [METADATA_EXTRACTION_IMPROVEMENTS.md](METADATA_EXTRACTION_IMPROVEMENTS.md)

---

### 3. Migration Tool ✅
Created `migrate_database.py` script to:
- Extract and populate metadata for existing albums
- Support dry-run mode for safe testing
- Check playback, archive, and source paths for metadata
- Provide detailed progress and summary

**Usage:**
```bash
# Dry run (preview changes)
python3 migrate_database.py --dry-run

# Apply changes
python3 migrate_database.py

# Custom database path
python3 migrate_database.py --db /path/to/database.duckdb
```

---

## Benefits

### Data Persistence
✅ All database operations reliably persist to disk  
✅ Crash-safe - committed data preserved even on failures  
✅ Resume capability - properly persisted state enables reliable resume  

### Metadata Quality
✅ Albums searchable by artist  
✅ Album names reflect actual metadata, not just folders  
✅ Prioritizes authoritative sources (SACD metadata)  
✅ Graceful fallbacks when metadata unavailable  

### Provenance Tracking
✅ Full lineage from source to processed albums  
✅ Can trace which processed album came from which source  
✅ Useful for reprocessing decisions  
✅ Better debugging and audit trail  

---

## Verification

### Test Database Persistence
```bash
python3 verify_db_persistence.py
```

### Check Current Database
```bash
duckdb music_catalog.duckdb
```

```sql
-- Check album metadata
SELECT album_id, artist, album_name, source_path 
FROM albums 
LIMIT 5;

-- Check processing history with IDs
SELECT 
    operation_type, 
    status, 
    album_id_origin, 
    album_id_processed,
    processed_at
FROM processing_history 
ORDER BY processed_at DESC 
LIMIT 10;

-- Find albums with artist populated
SELECT COUNT(*) as albums_with_artist 
FROM albums 
WHERE artist IS NOT NULL;
```

---

## Migration Steps

### For Existing Databases

#### Step 1: Apply Schema Migration (Add New Columns)

The schema migration is **automatic** - it will run the first time you open your database with the new code. However, you can also manually trigger it:

```bash
# This will add the new columns if they don't exist
python3 apply_schema_migration.py
```

Or simply run any command that uses the database - it will auto-migrate:

```bash
# This will also trigger the migration
python3 -c "from src.database import MusicDatabase; db = MusicDatabase('music_catalog.duckdb'); db.close()"
```

#### Step 2: Populate Metadata for Existing Albums

After the schema is updated, extract and populate metadata for existing albums:

1. **Backup your database:**
   ```bash
   cp music_catalog.duckdb music_catalog.duckdb.backup
   ```

2. **Test migration (dry run):**
   ```bash
   python3 migrate_database.py --dry-run
   ```

3. **Apply migration:**
   ```bash
   python3 migrate_database.py
   ```

4. **Verify results:**
   ```bash
   python3 check_database_schema.sh
   # Or manually:
   duckdb music_catalog.duckdb -c "SELECT COUNT(*) FROM albums WHERE artist IS NOT NULL;"
   ```

### For New Installations

No migration needed! New albums will automatically:
- Have metadata extracted during processing
- Have artist and album name properly populated
- Have processing history with album IDs tracked

---

## Database Schema

### Albums Table (Updated)
```sql
CREATE TABLE albums (
    album_id VARCHAR PRIMARY KEY,
    processed_album_id VARCHAR,
    album_name VARCHAR,          -- Now from metadata
    artist VARCHAR,              -- Now populated from metadata
    release_year INTEGER,
    -- ... other fields ...
    processed_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Processing History Table (Updated)
```sql
CREATE TABLE processing_history (
    history_id VARCHAR PRIMARY KEY,
    album_id VARCHAR,
    album_id_origin VARCHAR,     -- NEW: Source album ID
    album_id_processed VARCHAR,  -- NEW: Converted album ID
    operation_type VARCHAR,
    status VARCHAR,
    error_message VARCHAR,
    duration_seconds DECIMAL(10, 2),
    processed_at TIMESTAMP,
    working_source_path VARCHAR,
    working_processed_path VARCHAR
);
```

---

## Example Queries

### Find Albums by Artist
```sql
SELECT album_name, artist, processed_at 
FROM albums 
WHERE artist LIKE '%Miles Davis%'
ORDER BY processed_at DESC;
```

### Trace Album Processing
```sql
SELECT 
    operation_type,
    status,
    album_id_origin,
    album_id_processed,
    processed_at
FROM processing_history
WHERE album_id = 'your-album-id'
ORDER BY processed_at;
```

### Find All Versions of an Album
```sql
SELECT 
    a1.album_name as source_album,
    a1.artist,
    a2.album_name as processed_album,
    ph.operation_type,
    ph.status,
    ph.processed_at
FROM processing_history ph
JOIN albums a1 ON ph.album_id_origin = a1.album_id
LEFT JOIN albums a2 ON ph.album_id_processed = a2.album_id
WHERE ph.album_id_origin = 'source-album-id'
ORDER BY ph.processed_at;
```

### Statistics
```sql
-- Count albums with metadata
SELECT 
    COUNT(*) as total_albums,
    COUNT(artist) as albums_with_artist,
    COUNT(CASE WHEN artist IS NOT NULL THEN 1 END) * 100.0 / COUNT(*) as artist_coverage_pct
FROM albums;

-- Processing success rate
SELECT 
    operation_type,
    status,
    COUNT(*) as count
FROM processing_history
GROUP BY operation_type, status
ORDER BY operation_type, status;
```

---

## Troubleshooting

### Database Not Persisting
1. Check that you're using the updated code with `commit()` calls
2. Verify database file permissions
3. Run verification script: `python3 verify_db_persistence.py`

### Missing Artist/Album Metadata
1. Check if metadata files exist in album directory
2. Run migration: `python3 migrate_database.py`
3. For SACD albums, ensure Disc_summary.txt or foo_dr.txt exists
4. For FLAC albums, ensure files have embedded tags

### Migration Issues
1. Always backup database first
2. Use `--dry-run` to preview changes
3. Check that album paths still exist and are accessible
4. Review migration output for errors

---

## Related Documentation

- [DATABASE_PERSISTENCE_FIX.md](DATABASE_PERSISTENCE_FIX.md) - Commit handling details
- [METADATA_EXTRACTION_IMPROVEMENTS.md](METADATA_EXTRACTION_IMPROVEMENTS.md) - Metadata extraction details
- [SACD_METADATA_ERROR_HANDLING.md](SACD_METADATA_ERROR_HANDLING.md) - SACD parsing
- [ERROR_HANDLING_FIX.md](ERROR_HANDLING_FIX.md) - Error handling improvements

---

## Version History

- **2024-11-19**: Initial database improvements
  - Added commit handling for persistence
  - Added metadata extraction for artist and album name
  - Added processing history tracking with album IDs
  - Created migration tool for existing databases

