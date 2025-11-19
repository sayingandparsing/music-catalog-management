#!/usr/bin/env python3
"""
Quick script to verify database persistence.
Tests that records are properly committed and persist across connections.
"""

from pathlib import Path
from src.database import MusicDatabase
from src.album_metadata import AlbumMetadata
import uuid
import tempfile

def test_database_persistence():
    """Test that database records persist across connections."""
    
    # Use a temporary database for testing
    with tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False) as f:
        db_path = Path(f.name)
    
    try:
        print("Testing database persistence...")
        print(f"Using test database: {db_path}")
        
        # Create a test album ID
        test_album_id = str(uuid.uuid4())
        test_album_name = "Test Album"
        test_source_path = "/test/source"
        test_checksum = "test_checksum_123"
        
        # Phase 1: Create and commit a record
        print("\n1. Creating album record...")
        db = MusicDatabase(db_path)
        
        success = db.create_album(
            album_id=test_album_id,
            album_name=test_album_name,
            source_path=test_source_path,
            audio_files_checksum=test_checksum
        )
        
        if not success:
            print("❌ FAILED: Could not create album")
            return False
        
        print("✓ Album record created")
        
        # Explicitly commit
        db.commit()
        print("✓ Changes committed")
        
        # Close the connection
        db.close()
        print("✓ Database connection closed")
        
        # Phase 2: Reopen database and verify record exists
        print("\n2. Reopening database to verify persistence...")
        db2 = MusicDatabase(db_path)
        
        # Try to retrieve the album
        album = db2.get_album_by_id(test_album_id)
        
        if not album:
            print("❌ FAILED: Album record not found after reopening database")
            print("   This indicates the commit did not persist!")
            db2.close()
            return False
        
        print("✓ Album record found!")
        print(f"   Album ID: {album['album_id']}")
        print(f"   Album Name: {album['album_name']}")
        print(f"   Source Path: {album['source_path']}")
        print(f"   Checksum: {album['audio_files_checksum']}")
        
        # Verify the data matches
        if (album['album_id'] == test_album_id and
            album['album_name'] == test_album_name and
            album['source_path'] == test_source_path and
            album['audio_files_checksum'] == test_checksum):
            print("✓ All data matches!")
        else:
            print("❌ FAILED: Data mismatch")
            db2.close()
            return False
        
        # Phase 3: Test update and commit
        print("\n3. Testing update and commit...")
        test_archive_path = "/test/archive"
        
        success = db2.update_album(
            album_id=test_album_id,
            archive_path=test_archive_path
        )
        
        if not success:
            print("❌ FAILED: Could not update album")
            db2.close()
            return False
        
        print("✓ Album updated")
        
        # Commit the update
        db2.commit()
        print("✓ Update committed")
        
        # Close connection
        db2.close()
        print("✓ Database connection closed")
        
        # Phase 4: Verify update persisted
        print("\n4. Verifying update persisted...")
        db3 = MusicDatabase(db_path)
        
        album = db3.get_album_by_id(test_album_id)
        
        if not album or album['archive_path'] != test_archive_path:
            print("❌ FAILED: Update did not persist")
            db3.close()
            return False
        
        print("✓ Update persisted correctly!")
        print(f"   Archive Path: {album['archive_path']}")
        
        db3.close()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\nDatabase persistence is working correctly.")
        print("Records are being committed and persist across connections.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        if db_path.exists():
            db_path.unlink()
            print(f"\nCleaned up test database: {db_path}")


def test_actual_database():
    """Test the actual music catalog database."""
    db_path = Path("music_catalog.duckdb")
    
    if not db_path.exists():
        print(f"\nActual database not found: {db_path}")
        print("This is normal if you haven't run any conversions yet.")
        return
    
    print("\n" + "="*60)
    print("Checking actual database...")
    print("="*60)
    
    db = MusicDatabase(db_path)
    
    # Get statistics
    stats = db.get_statistics()
    
    print(f"\nDatabase Statistics:")
    print(f"  Total Albums: {stats.get('total_albums', 0)}")
    print(f"  Total Tracks: {stats.get('total_tracks', 0)}")
    print(f"  Total Artists: {stats.get('total_artists', 0)}")
    print(f"  Total Labels: {stats.get('total_labels', 0)}")
    print(f"  Total Processing Records: {stats.get('total_processing_records', 0)}")
    
    # Get recent albums
    recent_albums = db.get_all_albums(limit=5)
    
    if recent_albums:
        print(f"\nMost Recent Albums:")
        for album in recent_albums:
            print(f"  - {album.get('artist', 'Unknown')} - {album.get('album_name', 'Unknown')}")
            print(f"    Processed: {album.get('processed_at', 'Unknown')}")
            if album.get('archive_path'):
                print(f"    Archived: ✓")
            if album.get('playback_path'):
                print(f"    Playback: ✓")
    
    db.close()
    print("\n✓ Actual database appears healthy")


if __name__ == '__main__':
    print("="*60)
    print("Database Persistence Verification")
    print("="*60)
    
    # Test with temporary database
    success = test_database_persistence()
    
    # Check actual database
    test_actual_database()
    
    print("\n" + "="*60)
    if success:
        print("Database persistence fix is working correctly!")
    else:
        print("There may be issues with database persistence.")
    print("="*60)

