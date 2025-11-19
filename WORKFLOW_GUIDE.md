# Workflow Guide

## Source File Removal Feature

### Overview

The music converter now supports automatic removal of source files from the input directory after successful archiving and conversion. This feature helps maintain a clean directory structure without duplicates.

### How It Works

When `remove_source_after_conversion` is enabled:

1. **Archive**: Original files are copied to the archive directory with timestamp
2. **Convert**: Files are converted and placed in the output directory
3. **Cleanup**: Original files are deleted from the input directory

### Configuration

In your `config.yaml`:

```yaml
processing:
  remove_source_after_conversion: true  # Set to true to enable
```

### Safety Considerations

⚠️ **IMPORTANT**: This feature permanently deletes files from the input directory!

**Recommended workflow for first-time users:**

1. **Start with the feature disabled** (`remove_source_after_conversion: false`)
2. Run a test conversion on a few albums
3. Verify:
   - Archive contains complete original files
   - Converted files are correct quality
   - Archive is in a safe, backed-up location
4. Once confident, enable the feature

### Example Workflows

#### Workflow 1: Separate Directories (Recommended)

```yaml
paths:
  archive_dir: /Volumes/Backup/MusicArchive    # Long-term storage
  output_dir: /Volumes/Music/Playback          # Active music library

processing:
  remove_source_after_conversion: true
```

**Result:**
- Input directory: Cleaned (originals removed)
- Archive: Complete backup of originals
- Output: Converted files for playback

#### Workflow 2: In-Place Conversion

```yaml
paths:
  archive_dir: /Volumes/Backup/MusicArchive    # Long-term storage
  output_dir: null                              # Same as input

processing:
  remove_source_after_conversion: true
```

**Result:**
- Input directory: Contains only converted files (originals replaced)
- Archive: Complete backup of originals

### Dry Run Testing

Test the removal behavior without actually deleting files:

```bash
python -m src.main /path/to/music --dry-run
```

This will show what would be removed without actually deleting anything.

### Failure Handling

The removal step only occurs if:
- Archiving completed successfully
- All files converted successfully (or based on `skip_album_on_error` setting)
- Output files created successfully

If removal fails for any reason:
- A warning is logged
- The album is still marked as successfully processed
- Archive and converted files remain intact

### Recovery

If you need to recover original files:
1. Original files are safely stored in the archive directory
2. Each archive includes a timestamp in its name
3. Use the archive to restore originals if needed

### Database Tracking

When database is enabled, cleanup operations are recorded:
- Success/failure status
- Error messages (if any)
- Timestamp of operation

Query cleanup history:

```sql
SELECT * FROM processing_history 
WHERE operation_type = 'cleanup' 
ORDER BY timestamp DESC;
```

## Best Practices

1. **Backup your archive directory** to a separate drive or cloud storage
2. **Test with dry-run** before enabling removal
3. **Verify a few albums** manually before processing large batches
4. **Monitor disk space** on your archive drive
5. **Keep checksums enabled** for verification (`verify_checksums: true`)

