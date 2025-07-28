# Schema Diff Pro

A professional MySQL database schema comparison and synchronization tool with a modern web interface.

## Features

### 🔍 Comprehensive Schema Comparison
- **Tables & Columns**: Structure, data types, defaults, constraints
- **Indexes**: All index types with column order and uniqueness
- **Constraints**: Primary keys, foreign keys, unique, check constraints
- **Routines**: Stored procedures, functions
- **Views**: View definitions and dependencies
- **Triggers**: Trigger definitions and events

### 🚀 Advanced Features
- **Real-time Progress**: WebSocket-based live progress updates
- **SQL Sync Scripts**: Automated generation with dependency ordering
- **Smart Filtering**: Filter by severity, object type, or search
- **Profile Management**: Save and reuse comparison configurations
- **Export Options**: JSON, CSV, SQL formats
- **Monaco Editor**: Professional SQL editing experience

### 🎨 Modern UI/UX
- **Responsive Design**: Works on all devices
- **Dark Mode Support**: Easy on the eyes
- **Interactive Diff Viewer**: Side-by-side and inline views
- **Progress Tracking**: Real-time comparison progress
- **Intuitive Navigation**: Clean, modern interface

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd schema-diff-pro

# Start all services
docker-compose up -d

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
```

### Manual Setup

#### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your configuration

# Run the server
uvicorn main:app --reload
```

#### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

## Configuration

### Backend Configuration (.env)

```env
# Security
SECRET_KEY=your-secret-key-here

# Database Connection Pool
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# CORS Origins
BACKEND_CORS_ORIGINS=http://localhost:3000
```

### Frontend Configuration

Edit `next.config.js` to update API endpoints if needed.

## Usage

1. **Configure Databases**
   - Enter source database credentials
   - Enter target database credentials
   - Test connections

2. **Set Comparison Options**
   - Choose object types to compare
   - Configure comparison settings
   - Set filters if needed

3. **Run Comparison**
   - Click "Start Comparison"
   - Monitor real-time progress
   - View results when complete

4. **Review Results**
   - Summary tab: Overview and statistics
   - Differences tab: Detailed difference list
   - Sync Script tab: Generated SQL scripts

5. **Generate Sync Script**
   - Click "Generate Sync Script"
   - Review warnings and impact analysis
   - Download or copy script

## Architecture

```
┌─────────────────────────┐     ┌─────────────────────────┐
│   Next.js Frontend      │────▶│   FastAPI Backend       │
│   - React Query         │     │   - Async SQLAlchemy    │
│   - Monaco Editor       │     │   - WebSocket Support   │
│   - Tailwind CSS        │     │   - Connection Pooling  │
└─────────────────────────┘     └─────────────────────────┘
                                           │
                                           ▼
                                ┌─────────────────────────┐
                                │   MySQL Databases       │
                                │   - Source DB           │
                                │   - Target DB           │
                                └─────────────────────────┘
```

## API Documentation

Once running, access the interactive API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Development

### Running Tests

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

### Code Quality

```bash
# Backend
black .
flake8
mypy .

# Frontend
npm run lint
npm run type-check
```

## Deployment

### Production Build

```bash
# Build Docker images
docker-compose -f docker-compose.prod.yml build

# Run in production
docker-compose -f docker-compose.prod.yml up -d
```

### Environment Variables

Ensure all production environment variables are properly set:
- Use strong SECRET_KEY
- Configure proper CORS origins
- Configure connection pooling
- Configure database connection pools

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failed**
   - Check CORS settings
   - Ensure WebSocket proxy is configured
   - Verify firewall rules

2. **Database Connection Timeout**
   - Verify MySQL server is accessible
   - Check credentials and permissions
   - Ensure proper network connectivity

3. **High Memory Usage**
   - Adjust DATABASE_POOL_SIZE
   - Optimize database connection pools
   - Limit concurrent comparisons

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is proprietary software. All rights reserved.

## Support

For issues and support, please contact the development team.