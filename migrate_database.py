#!/usr/bin/env python3
"""
Database Migration Script
Adds new columns and extracts metadata for existing albums.
"""

from pathlib import Path
from src.database import MusicDatabase
from src.album_metadata import AlbumMetadata
from src.sacd_metadata_parser import find_sacd_metadata_files, parse_sacd_metadata_file
import sys

try:
    from mutagen.flac import FLAC as MutagenFLAC
except ImportError:
    MutagenFLAC = None
    print("Warning: mutagen not installed, FLAC metadata extraction will be limited")


def extract_album_metadata(album_path: Path) -> dict:
    """
    Extract album-level metadata from a directory.
    
    Args:
        album_path: Path to album directory
        
    Returns:
        Dictionary with artist and album_name
    """
    metadata = {
        'artist': None,
        'album_name': None
    }
    
    if not album_path.exists():
        return metadata
    
    # Priority 1: SACD metadata
    sacd_metadata_files = find_sacd_metadata_files(album_path)
    if sacd_metadata_files:
        sacd_metadata = parse_sacd_metadata_file(sacd_metadata_files[0])
        if sacd_metadata:
            sacd_info = sacd_metadata.get('album', {}) or sacd_metadata.get('disc', {})
            if sacd_info:
                if 'artist' in sacd_info:
                    metadata['artist'] = sacd_info['artist']
                if 'album' in sacd_info or 'title' in sacd_info:
                    metadata['album_name'] = sacd_info.get('album') or sacd_info.get('title')
    
    # Priority 2: FLAC tags
    if (not metadata['artist'] or not metadata['album_name']) and MutagenFLAC:
        flac_files = list(album_path.glob('*.flac'))
        if not flac_files:
            # Check subdirectories
            flac_files = list(album_path.rglob('*.flac'))
        
        for flac_file in flac_files[:3]:  # Check first 3 FLAC files
            try:
                audio = MutagenFLAC(str(flac_file))
                
                if not metadata['artist'] and 'artist' in audio:
                    metadata['artist'] = audio['artist'][0]
                if not metadata['artist'] and 'albumartist' in audio:
                    metadata['artist'] = audio['albumartist'][0]
                
                if not metadata['album_name'] and 'album' in audio:
                    metadata['album_name'] = audio['album'][0]
                
                # If we found both, we're done
                if metadata['artist'] and metadata['album_name']:
                    break
            except Exception as e:
                print(f"  Warning: Could not read {flac_file.name}: {e}")
                continue
    
    # Priority 3: Fallback to folder name
    if not metadata['album_name']:
        metadata['album_name'] = album_path.name
    
    return metadata


def migrate_database(db_path: Path, dry_run: bool = False):
    """
    Migrate database to add new fields and extract metadata.
    
    Args:
        db_path: Path to database file
        dry_run: If True, only show what would be done
    """
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        return False
    
    print("="*60)
    print("Database Migration Tool")
    print("="*60)
    print(f"\nDatabase: {db_path}")
    print(f"Mode: {'DRY RUN (no changes will be made)' if dry_run else 'LIVE (will modify database)'}")
    print()
    
    # Open database
    db = MusicDatabase(db_path)
    
    try:
        # Get all albums
        albums = db.get_all_albums()
        
        if not albums:
            print("No albums found in database.")
            return True
        
        print(f"Found {len(albums)} albums\n")
        
        # Process each album
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for i, album in enumerate(albums, 1):
            album_id = album['album_id']
            album_name = album['album_name']
            current_artist = album.get('artist')
            source_path = album.get('source_path')
            playback_path = album.get('playback_path')
            archive_path = album.get('archive_path')
            
            print(f"[{i}/{len(albums)}] {album_name}")
            
            # Determine which path to check for metadata
            check_path = None
            if playback_path and Path(playback_path).exists():
                check_path = Path(playback_path)
                print(f"  Using playback path: {playback_path}")
            elif archive_path and Path(archive_path).exists():
                check_path = Path(archive_path)
                print(f"  Using archive path: {archive_path}")
            elif source_path and Path(source_path).exists():
                check_path = Path(source_path)
                print(f"  Using source path: {source_path}")
            else:
                print("  ⚠ No accessible path found, skipping")
                skipped_count += 1
                continue
            
            # Extract metadata
            try:
                extracted = extract_album_metadata(check_path)
                
                updates = {}
                
                # Check if we need to update artist
                if extracted['artist'] and not current_artist:
                    updates['artist'] = extracted['artist']
                    print(f"  → Will set artist: {extracted['artist']}")
                elif current_artist:
                    print(f"  ✓ Artist already set: {current_artist}")
                else:
                    print(f"  ⚠ No artist found in metadata")
                
                # Check if we need to update album name
                # Only update if current name looks like a folder name and we have better metadata
                if (extracted['album_name'] and 
                    extracted['album_name'] != album_name and
                    album_name == Path(source_path or '').name):
                    updates['album_name'] = extracted['album_name']
                    print(f"  → Will update album name: {album_name} → {extracted['album_name']}")
                
                # Apply updates
                if updates:
                    if not dry_run:
                        success = db.update_album(album_id, **updates)
                        if success:
                            db.commit()
                            print(f"  ✓ Updated")
                            updated_count += 1
                        else:
                            print(f"  ✗ Update failed")
                            error_count += 1
                    else:
                        print(f"  → Would update (dry run)")
                        updated_count += 1
                else:
                    print(f"  ✓ No updates needed")
                    skipped_count += 1
                
            except Exception as e:
                print(f"  ✗ Error: {e}")
                error_count += 1
            
            print()
        
        # Summary
        print("="*60)
        print("Migration Summary")
        print("="*60)
        print(f"Total albums: {len(albums)}")
        print(f"Updated: {updated_count}")
        print(f"Skipped: {skipped_count}")
        print(f"Errors: {error_count}")
        print()
        
        if dry_run:
            print("This was a dry run. No changes were made.")
            print("Run without --dry-run to apply changes.")
        else:
            print("Migration complete!")
        
        return error_count == 0
        
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Migrate database to add metadata fields'
    )
    parser.add_argument(
        '--db',
        type=Path,
        default=Path('music_catalog.duckdb'),
        help='Path to database file (default: music_catalog.duckdb)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    args = parser.parse_args()
    
    # Confirm if not dry run
    if not args.dry_run:
        print("\nWARNING: This will modify your database.")
        print("It is recommended to backup your database first.")
        response = input("\nContinue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Cancelled.")
            sys.exit(0)
        print()
    
    success = migrate_database(args.db, dry_run=args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

