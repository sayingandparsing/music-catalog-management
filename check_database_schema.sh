#!/bin/bash
# Quick script to check database schema

DB_FILE="${1:-music_catalog.duckdb}"

if [ ! -f "$DB_FILE" ]; then
    echo "Database not found: $DB_FILE"
    exit 1
fi

echo "=================================================="
echo "Database Schema Check"
echo "=================================================="
echo "Database: $DB_FILE"
echo ""

echo "Albums table columns:"
duckdb "$DB_FILE" -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'albums' ORDER BY ordinal_position;" -markdown

echo ""
echo "Processing History table columns:"
duckdb "$DB_FILE" -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'processing_history' ORDER BY ordinal_position;" -markdown

echo ""
echo "Sample data from albums (first 3):"
duckdb "$DB_FILE" -c "SELECT album_id, artist, album_name FROM albums LIMIT 3;" -markdown

echo ""
echo "Sample data from processing_history (first 3):"
duckdb "$DB_FILE" -c "SELECT operation_type, status, album_id_origin, album_id_processed FROM processing_history ORDER BY processed_at DESC LIMIT 3;" -markdown

echo ""
echo "Statistics:"
duckdb "$DB_FILE" -c "SELECT COUNT(*) as total_albums, COUNT(artist) as albums_with_artist FROM albums;"
duckdb "$DB_FILE" -c "SELECT COUNT(*) as total_processing_records FROM processing_history;"
duckdb "$DB_FILE" -c "SELECT COUNT(*) as records_with_origin_id FROM processing_history WHERE album_id_origin IS NOT NULL;"
duckdb "$DB_FILE" -c "SELECT COUNT(*) as records_with_processed_id FROM processing_history WHERE album_id_processed IS NOT NULL;"

echo ""
echo "=================================================="

