#!/usr/bin/env python3
"""
Test script to verify new database schema is created correctly.
"""

from pathlib import Path
from src.database import MusicDatabase
import tempfile
import sys


def test_new_database():
    """Test creating a brand new database and verify schema."""
    
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False) as f:
        test_db_path = Path(f.name)
    
    # Delete it so we start fresh
    test_db_path.unlink()
    
    print("="*60)
    print("Testing New Database Creation")
    print("="*60)
    print(f"\nCreating new database: {test_db_path}")
    
    try:
        # Create database
        db = MusicDatabase(test_db_path)
        
        print("✓ Database created")
        
        # Check processing_history table schema
        print("\nChecking processing_history table schema...")
        
        result = db.conn.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns 
            WHERE table_name = 'processing_history'
            ORDER BY ordinal_position
        """).fetchall()
        
        print("\nColumns in processing_history table:")
        for col_name, col_type in result:
            print(f"  - {col_name}: {col_type}")
        
        # Check for the new columns
        columns = [col[0] for col in result]
        
        has_origin = 'album_id_origin' in columns
        has_processed = 'album_id_processed' in columns
        
        print("\nColumn checks:")
        print(f"  {'✓' if has_origin else '✗'} album_id_origin: {'PRESENT' if has_origin else 'MISSING'}")
        print(f"  {'✓' if has_processed else '✗'} album_id_processed: {'PRESENT' if has_processed else 'MISSING'}")
        
        # Check albums table for artist column
        print("\nChecking albums table schema...")
        
        result = db.conn.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns 
            WHERE table_name = 'albums'
            ORDER BY ordinal_position
        """).fetchall()
        
        print("\nColumns in albums table:")
        for col_name, col_type in result:
            marker = "→" if col_name in ['artist', 'album_name'] else " "
            print(f"  {marker} {col_name}: {col_type}")
        
        # Check for artist column
        albums_columns = [col[0] for col in result]
        has_artist = 'artist' in albums_columns
        
        print("\nColumn checks:")
        print(f"  {'✓' if has_artist else '✗'} artist: {'PRESENT' if has_artist else 'MISSING'}")
        
        # Test adding a processing history record with the new columns
        print("\nTesting add_processing_history with new columns...")
        
        import uuid
        test_album_id = str(uuid.uuid4())
        test_origin_id = str(uuid.uuid4())
        test_processed_id = str(uuid.uuid4())
        
        # First create a test album
        db.create_album(
            album_id=test_album_id,
            album_name="Test Album",
            source_path="/test/path",
            audio_files_checksum="test123",
            artist="Test Artist"
        )
        db.commit()
        
        print("  ✓ Created test album")
        
        # Try to add processing history with new columns
        try:
            success = db.add_processing_history(
                album_id=test_album_id,
                operation_type='test',
                status='success',
                album_id_origin=test_origin_id,
                album_id_processed=test_processed_id
            )
            
            if success:
                db.commit()
                print("  ✓ Added processing history with new columns")
                
                # Verify the data was stored
                result = db.conn.execute("""
                    SELECT album_id_origin, album_id_processed
                    FROM processing_history
                    WHERE album_id = ?
                """, [test_album_id]).fetchone()
                
                if result:
                    stored_origin, stored_processed = result
                    print(f"  ✓ Data stored correctly:")
                    print(f"    - origin: {stored_origin}")
                    print(f"    - processed: {stored_processed}")
                    
                    if stored_origin == test_origin_id and stored_processed == test_processed_id:
                        print("  ✓ Values match!")
                    else:
                        print("  ✗ Values don't match")
                else:
                    print("  ✗ No data found")
            else:
                print("  ✗ Failed to add processing history")
                
        except Exception as e:
            print(f"  ✗ Error adding processing history: {e}")
        
        db.close()
        
        # Summary
        print("\n" + "="*60)
        if has_origin and has_processed and has_artist:
            print("✅ SUCCESS - New database schema is correct!")
            print("   All expected columns are present.")
        else:
            print("❌ FAILURE - New database schema is MISSING columns!")
            if not has_origin:
                print("   Missing: album_id_origin in processing_history")
            if not has_processed:
                print("   Missing: album_id_processed in processing_history")
            if not has_artist:
                print("   Missing: artist in albums")
        print("="*60)
        
        return has_origin and has_processed and has_artist
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        if test_db_path.exists():
            test_db_path.unlink()
            print(f"\nCleaned up test database: {test_db_path}")


def check_existing_database():
    """Check the existing database."""
    db_path = Path('music_catalog.duckdb')
    
    if not db_path.exists():
        print("\nNo existing database found at music_catalog.duckdb")
        return
    
    print("\n" + "="*60)
    print("Checking Existing Database")
    print("="*60)
    print(f"\nDatabase: {db_path}")
    
    try:
        db = MusicDatabase(db_path)
        
        # Check processing_history columns
        result = db.conn.execute("""
            SELECT column_name
            FROM information_schema.columns 
            WHERE table_name = 'processing_history'
            ORDER BY ordinal_position
        """).fetchall()
        
        columns = [col[0] for col in result]
        
        print("\nProcessing history columns:")
        for col in columns:
            marker = "→" if col in ['album_id_origin', 'album_id_processed'] else " "
            print(f"  {marker} {col}")
        
        has_origin = 'album_id_origin' in columns
        has_processed = 'album_id_processed' in columns
        
        print(f"\n{'✓' if has_origin else '✗'} album_id_origin: {'present' if has_origin else 'MISSING'}")
        print(f"{'✓' if has_processed else '✗'} album_id_processed: {'present' if has_processed else 'MISSING'}")
        
        # Check albums columns
        result = db.conn.execute("""
            SELECT column_name
            FROM information_schema.columns 
            WHERE table_name = 'albums'
            ORDER BY ordinal_position
        """).fetchall()
        
        albums_columns = [col[0] for col in result]
        has_artist = 'artist' in albums_columns
        
        print(f"{'✓' if has_artist else '✗'} artist in albums: {'present' if has_artist else 'MISSING'}")
        
        db.close()
        
    except Exception as e:
        print(f"\nError checking existing database: {e}")


if __name__ == '__main__':
    print("="*60)
    print("Database Schema Verification")
    print("="*60)
    
    # Test with a brand new database
    success = test_new_database()
    
    # Check existing database
    check_existing_database()
    
    print("\n" + "="*60)
    if success:
        print("New database schema is CORRECT")
        print("\nIf your existing database doesn't have the columns,")
        print("run: python3 apply_schema_migration.py")
    else:
        print("New database schema has ISSUES")
        print("\nThere may be a problem with the database code.")
    print("="*60)
    
    sys.exit(0 if success else 1)

