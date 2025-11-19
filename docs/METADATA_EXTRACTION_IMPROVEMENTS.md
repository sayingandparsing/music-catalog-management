# Metadata Extraction and Database Improvements

## Overview
Enhanced metadata extraction and database storage to properly populate artist, album name, and processing history with album IDs.

## Changes Implemented

### 1. Album-Level Metadata Extraction

Created `_extract_album_metadata()` method in `ConversionOrchestrator` that extracts metadata from audio files using a priority system:

**Priority Order:**
1. **SACD Metadata** - From Disc_summary.txt or foo_dr.txt files
2. **FLAC Tags** - From embedded metadata in FLAC files  
3. **Folder Name** - Fallback for album name

**Extracted Fields:**
- `artist` - Album artist (also checks albumartist tag)
- `album_name` - Album title

### 2. Database Schema Updates

#### Processing History Table
Added two new fields to track album transformations:

```sql
album_id_origin VARCHAR      -- Original album ID (from source files)
album_id_processed VARCHAR   -- Processed album ID (from converted files)
```

These fields allow tracking the relationship between source and converted albums through the processing pipeline.

### 3. Album Record Improvements

**When Creating Albums:**
- Extracts metadata before creating database record
- Populates `artist` field with extracted artist
- Uses metadata album name instead of just folder name
- Logs extracted metadata for visibility

**When Updating Albums:**
- Updates artist if not already set
- Updates album name if it was just a folder name
- Preserves existing metadata when available

### 4. Processing History Tracking

Updated all `add_processing_history()` calls to include album IDs:

**Early Processing Stages** (before conversion complete):
- `album_id_origin` = album_id (source files ID)
- `album_id_processed` = None

**After Finalization** (after conversion complete):
- `album_id_origin` = album_id (source files ID)  
- `album_id_processed` = processed_album_id (converted files ID)

**Operations Tracked:**
- `convert` - Audio conversion operations
- `archive` - Archiving to backup location
- `finalize` - Moving to output location
- `enrich` - Metadata enrichment
- `cleanup` - Source file removal

## Implementation Details

### Metadata Extraction Logic

```python
def _extract_album_metadata(self, album_path: Path, music_files: list) -> dict:
    """
    Extract album-level metadata from audio files.
    
    Priority: SACD metadata > FLAC tags > folder name
    """
    # 1. Check SACD metadata files
    sacd_metadata_files = find_sacd_metadata_files(album_path)
    if sacd_metadata_files:
        sacd_metadata = parse_sacd_metadata_file(sacd_metadata_files[0])
        # Extract artist and album from SACD metadata
    
    # 2. Check FLAC tags
    if not metadata['artist'] or not metadata['album_name']:
        for music_file in music_files:
            if music_file.extension.lower() == '.flac':
                audio = MutagenFLAC(str(music_file.path))
                # Extract from 'artist', 'albumartist', 'album' tags
    
    # 3. Fallback to folder name
    if not metadata['album_name']:
        metadata['album_name'] = album_path.name
    
    return metadata
```

### Database Updates

**Album Creation:**
```python
self.database.create_album(
    album_id=album_id,
    album_name=album_metadata['album_name'],  # From metadata
    artist=album_metadata['artist'],           # From metadata
    source_path=str(original_source_path),
    audio_files_checksum=audio_checksum,
    ...
)
```

**Processing History:**
```python
self.database.add_processing_history(
    album_id=album_id,
    operation_type='convert',
    status='success',
    album_id_origin=album_id,              # Source ID
    album_id_processed=processed_album_id  # Converted ID (when available)
)
```

## Benefits

### 1. Better Searchability
- Albums can be searched by artist name
- Album names reflect actual metadata, not just folder names

### 2. Provenance Tracking
- Full lineage from source to processed albums
- Can trace which processed album came from which source
- Useful for reprocessing decisions

### 3. Improved User Experience
- More meaningful album names in database queries
- Artist information readily available
- Better organization and categorization

### 4. Data Quality
- Prioritizes authoritative sources (SACD metadata)
- Falls back gracefully when metadata unavailable
- Preserves existing good data when updating

## Usage Examples

### Query Albums by Artist
```sql
SELECT album_name, artist, processed_at 
FROM albums 
WHERE artist LIKE '%Coltrane%'
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
    a2.album_name as processed_album,
    ph.operation_type,
    ph.processed_at
FROM processing_history ph
JOIN albums a1 ON ph.album_id_origin = a1.album_id
LEFT JOIN albums a2 ON ph.album_id_processed = a2.album_id
WHERE ph.album_id_origin = 'source-album-id';
```

## Migration Notes

### For Existing Databases
The schema changes are backward compatible:
- New columns have NULL default values
- Existing records will have NULL for `album_id_origin` and `album_id_processed`
- New processing will populate these fields
- Consider reprocessing albums to populate metadata

### Recommended Steps
1. Backup database before running updated code
2. First run will add new columns automatically
3. Existing albums will not have artist populated
4. Reprocess albums to extract and populate metadata

## Files Modified
- `src/database.py` - Schema and method updates
- `src/main.py` - Metadata extraction and processing logic

## Related Documentation
- [DATABASE_PERSISTENCE_FIX.md](DATABASE_PERSISTENCE_FIX.md) - Database commit improvements
- [SACD_METADATA_ERROR_HANDLING.md](SACD_METADATA_ERROR_HANDLING.md) - SACD metadata parsing

