# Test Fixtures for DSD Music Converter

This directory contains fixtures and setup instructions for running the comprehensive test suite.

## Test Data Requirements

To run the full test suite, you need to provide a real ISO/DSF album for integration testing.

### Setup Instructions

1. **Set the TEST_ALBUM_PATH environment variable** pointing to a directory containing at least one ISO or DSF album:

   ```bash
   export TEST_ALBUM_PATH="/path/to/your/test/album"
   ```

2. **Minimum Requirements for Test Album:**
   - At least 1 album directory
   - At least 1-2 ISO or DSF files
   - Optional: Additional files like artwork (JPG, PDF), cue sheets, etc.

3. **Example Directory Structure:**
   ```
   /path/to/your/test/album/
   └── Test Artist - Test Album/
       ├── 01 - Track One.dsf
       ├── 02 - Track Two.dsf
       ├── cover.jpg
       └── booklet.pdf
   ```

### Alternative: Skip Integration Tests

If you don't have a test ISO/DSF album available, you can run only the unit tests:

```bash
pytest tests/ -m "not integration"
```

This will skip the integration tests that require real audio files.

## Running Tests

### Run All Tests
```bash
pytest tests/
```

### Run with Coverage
```bash
pytest tests/ --cov=src --cov-report=html
```

### Run Specific Test Module
```bash
pytest tests/test_scanner.py -v
```

### Run Only Fast Tests (Skip Integration)
```bash
pytest tests/ -m "not integration and not slow"
```

### Run Only Integration Tests
```bash
pytest tests/ -m "integration"
```

## Test Markers

- `integration`: Tests that require real ISO/DSF files
- `slow`: Tests that take >5 seconds to run
- `unit`: Fast unit tests (default)

## Notes

- Tests create temporary directories for outputs and archives
- All temporary files are cleaned up after tests complete
- Integration tests may take several minutes depending on file sizes
- No external API calls are made during tests (all mocked)

