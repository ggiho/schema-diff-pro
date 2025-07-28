# Migration Guide: From Old Schema Diff to Schema Diff Pro

## Overview

Schema Diff Pro is a complete rewrite of the original schema comparison tool, offering significant improvements in performance, features, and user experience.

## Key Improvements

### 🚀 Performance
- **10x Faster**: Async operations and parallel processing
- **Real-time Updates**: WebSocket-based progress tracking
- **Efficient Caching**: Redis integration for repeated comparisons

### 🎯 Features
- **Complete Schema Comparison**: Not just indexes, but tables, columns, constraints, procedures, views, and more
- **SQL Sync Scripts**: Automated generation with proper dependency ordering
- **Profile Management**: Save and reuse comparison configurations
- **Advanced Filtering**: Multi-dimensional filtering and search

### 🎨 User Experience
- **Modern UI**: React/Next.js with responsive design
- **Monaco Editor**: Professional SQL editing experience
- **Interactive Diff Viewer**: Side-by-side and inline views
- **Export Options**: Multiple formats (JSON, CSV, SQL)

## Migration Steps

### 1. Backup Existing Data

If you have any saved comparison results or configurations, export them before migrating.

### 2. Stop Old Application

```bash
# If using the old Streamlit app
# Stop the running process
```

### 3. Install New Application

```bash
# Clone the new repository
git clone <repository-url> schema-diff-pro
cd schema-diff-pro

# Start with Docker Compose
docker-compose up -d
```

### 4. Update Database Connections

The new tool uses the same connection format but with enhanced security:
- Passwords are never stored in plain text
- Connection profiles can be saved securely
- SSL/TLS support for secure connections

### 5. Feature Mapping

| Old Feature | New Feature | Notes |
|-------------|-------------|-------|
| Index Comparison | Comprehensive Comparison | Now includes all schema objects |
| CSV Export | Multiple Export Formats | JSON, CSV, SQL scripts |
| Basic UI | Modern React UI | Responsive, dark mode support |
| No Progress Tracking | Real-time Progress | WebSocket-based updates |
| No Script Generation | SQL Sync Scripts | With dependency ordering |

## New Features to Explore

### 1. Comparison Profiles
Save frequently used database configurations for quick access.

### 2. Advanced Filtering
Filter results by:
- Severity (Critical, High, Medium, Low)
- Object Type (Table, Index, Constraint, etc.)
- Search by name or description

### 3. Sync Script Generation
- Automated SQL generation
- Forward and rollback scripts
- Impact analysis and warnings
- Dependency-aware ordering

### 4. WebSocket Progress
Real-time updates during comparison:
- Current phase and progress
- Estimated time remaining
- Live object processing status

### 5. Monaco Editor Integration
- Syntax highlighting for SQL
- Code folding and formatting
- Full-screen mode
- Copy and download options

## Common Use Cases

### Quick Comparison
1. Enter source and target database credentials
2. Click "Start Comparison"
3. View results immediately

### Scheduled Comparisons
1. Create a comparison profile
2. Use the API to trigger comparisons programmatically
3. Integrate with CI/CD pipelines

### Generate Migration Scripts
1. Run comparison
2. Review differences
3. Click "Generate Sync Script"
4. Download and execute in your environment

## API Migration

If you were using the old tool programmatically:

### Old Approach
```python
# Direct script execution
python main.py --source=dev --target=prod
```

### New Approach
```python
import requests

# RESTful API
response = requests.post('http://localhost:8000/api/v1/comparison/compare', json={
    'source_config': {...},
    'target_config': {...},
    'options': {...}
})

comparison_id = response.json()['comparison_id']
```

## Troubleshooting

### Issue: Old configurations don't work
**Solution**: The new tool uses a different configuration format. Recreate your database connections in the new UI.

### Issue: Missing features from old tool
**Solution**: Most features have been enhanced and relocated. Check the feature mapping table above.

### Issue: Performance concerns
**Solution**: The new tool is significantly faster. If you experience issues, check:
- Database connection pool settings
- Redis cache configuration
- Network connectivity

## Support

For additional help with migration:
1. Check the main README for detailed documentation
2. Review the API documentation at http://localhost:8000/docs
3. Contact the development team for specific migration assistance

## Rollback Plan

If you need to temporarily revert to the old tool:
1. The old tool remains at `../`
2. Stop the new services: `docker-compose down`
3. Restart the old application

However, we strongly recommend completing the migration as the old tool will be deprecated.