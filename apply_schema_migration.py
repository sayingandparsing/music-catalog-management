#!/usr/bin/env python3
"""
Apply database schema migration.
This script will add the new columns to your existing database.
"""

from pathlib import Path
from src.database import MusicDatabase
import sys


def apply_migration(db_path: Path):
    """
    Apply schema migration to database.
    
    Args:
        db_path: Path to database file
    """
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        print("No migration needed - will be created on first use.")
        return True
    
    print("="*60)
    print("Database Schema Migration")
    print("="*60)
    print(f"\nDatabase: {db_path}")
    print()
    
    try:
        # Opening the database will automatically run migrations
        print("Opening database and applying migrations...")
        db = MusicDatabase(db_path)
        
        # Verify the new columns exist
        print("\nVerifying schema...")
        result = db.conn.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'processing_history'
            ORDER BY ordinal_position
        """).fetchall()
        
        columns = [col[0] for col in result]
        
        print(f"\nProcessing History columns:")
        for col in columns:
            marker = "✓" if col in ['album_id_origin', 'album_id_processed'] else " "
            highlight = " (NEW)" if col in ['album_id_origin', 'album_id_processed'] else ""
            print(f"  {marker} {col}{highlight}")
        
        # Check for the new columns
        has_origin = 'album_id_origin' in columns
        has_processed = 'album_id_processed' in columns
        
        if has_origin and has_processed:
            print("\n✅ Migration successful!")
            print("   Both new columns are present in the database.")
        else:
            print("\n⚠ Warning: Migration incomplete")
            if not has_origin:
                print("   Missing: album_id_origin")
            if not has_processed:
                print("   Missing: album_id_processed")
        
        # Show some statistics
        print("\nDatabase statistics:")
        stats = db.get_statistics()
        print(f"  Total albums: {stats.get('total_albums', 0)}")
        print(f"  Total tracks: {stats.get('total_tracks', 0)}")
        print(f"  Total processing records: {stats.get('total_processing_records', 0)}")
        
        # Check if any albums have artist populated
        result = db.conn.execute("""
            SELECT COUNT(*) 
            FROM albums 
            WHERE artist IS NOT NULL
        """).fetchone()
        albums_with_artist = result[0] if result else 0
        
        print(f"  Albums with artist: {albums_with_artist}")
        
        if albums_with_artist == 0 and stats.get('total_albums', 0) > 0:
            print("\n💡 Tip: Run migrate_database.py to extract and populate metadata")
            print("   for existing albums:")
            print("   python3 migrate_database.py --dry-run  # Preview changes")
            print("   python3 migrate_database.py            # Apply changes")
        
        db.close()
        
        print("\n" + "="*60)
        print("Migration complete!")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Apply database schema migration'
    )
    parser.add_argument(
        '--db',
        type=Path,
        default=Path('music_catalog.duckdb'),
        help='Path to database file (default: music_catalog.duckdb)'
    )
    
    args = parser.parse_args()
    
    success = apply_migration(args.db)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

