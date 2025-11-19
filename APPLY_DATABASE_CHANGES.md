# How to Apply Database Changes

Your database wasn't seeing the changes because the new columns weren't added to your existing database. I've now added **automatic migration** that will run when you next use the database.

## Quick Start

### Option 1: Automatic Migration (Easiest)
Just run the migration script - it will automatically apply the schema changes:

```bash
python3 apply_schema_migration.py
```

This will:
- ✅ Add `album_id_origin` column to `processing_history` table
- ✅ Add `album_id_processed` column to `processing_history` table  
- ✅ Show you the current schema
- ✅ Display database statistics

### Option 2: Let It Auto-Migrate
The migration will run automatically the next time you:
- Run a conversion
- Open the database with any tool
- Use any database command

The migration code checks if the columns exist and adds them if they're missing.

## Verify the Changes

After migration, check your database schema:

```bash
# Easy way - use the check script
./check_database_schema.sh

# Or manually with duckdb
duckdb music_catalog.duckdb -c "SELECT column_name FROM information_schema.columns WHERE table_name = 'processing_history';"
```

You should now see:
- `album_id_origin` column
- `album_id_processed` column

## Next Steps

### 1. Schema Migration ✅
Already done! The new columns are now in your database.

### 2. Populate Metadata (Optional)
To extract and populate artist/album metadata for existing albums:

```bash
# Preview what would be done
python3 migrate_database.py --dry-run

# Apply metadata extraction
python3 migrate_database.py
```

This will:
- Extract artist from SACD metadata or FLAC tags
- Extract album names from metadata
- Update your existing album records

## What Changed

### Database Schema
Added two new columns to `processing_history` table:
- `album_id_origin` - Tracks the original album ID (from source files)
- `album_id_processed` - Tracks the processed album ID (from converted files)

### Processing Flow
Now when albums are processed:
- Artist is extracted from metadata (SACD → FLAC → fallback)
- Album name uses metadata (SACD → FLAC → folder name)
- Processing history records include both album IDs

## Tools Available

| Tool | Purpose |
|------|---------|
| `apply_schema_migration.py` | Apply schema changes to existing database |
| `migrate_database.py` | Extract and populate metadata for existing albums |
| `check_database_schema.sh` | View current database schema and stats |
| `verify_db_persistence.py` | Test that database commits are working |

## Troubleshooting

### "No such column: album_id_origin"
Run the schema migration:
```bash
python3 apply_schema_migration.py
```

### Want to see the schema changes?
```bash
./check_database_schema.sh
```

### Need to populate metadata for old albums?
```bash
python3 migrate_database.py --dry-run  # Preview first
python3 migrate_database.py            # Then apply
```

## Summary

The database changes are now **automatic**! Just run:

```bash
python3 apply_schema_migration.py
```

And you're done! All future conversions will automatically use the new schema and populate metadata.

