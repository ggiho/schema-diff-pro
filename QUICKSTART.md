# Quick Start Guide

## 🚀 Fastest Way to Start

### Option 1: Development Script (Recommended for First Run)

```bash
# Run the development startup script
./start-dev.sh
```

This will:
- Start Redis in Docker
- Install Python dependencies
- Install Node.js dependencies  
- Start both backend and frontend servers
- Open http://localhost:3000 in your browser

### Option 2: Docker Compose (Production-like)

```bash
# Start all services with Docker
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Option 3: Manual Start

#### Terminal 1: Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

#### Terminal 2: Frontend
```bash
cd frontend
npm install
npm run dev
```

#### Terminal 3: Redis
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

## 🔧 First-Time Setup

1. **Database Access**: Make sure you have access to at least two MySQL databases for comparison

2. **Environment Variables**: Copy and edit the backend `.env` file:
   ```bash
   cd backend
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Test Databases** (Optional): The docker-compose includes test MySQL instances:
   - Source: localhost:3306 (root/rootpassword)
   - Target: localhost:3307 (root/rootpassword)

## 📱 Using the Application

1. **Open the UI**: Navigate to http://localhost:3000

2. **Configure Databases**:
   - Enter your source database credentials
   - Enter your target database credentials
   - Click "Test Connection" to verify

3. **Run Comparison**:
   - Select comparison options
   - Click "Start Comparison"
   - Watch real-time progress

4. **Review Results**:
   - Summary tab: Overview and statistics
   - Differences tab: Detailed list of differences
   - Sync Script tab: Generated SQL migration scripts

## 🛠️ Troubleshooting

### Port Already in Use
```bash
# Kill process on port 3000
lsof -ti:3000 | xargs kill -9

# Kill process on port 8000
lsof -ti:8000 | xargs kill -9
```

### Redis Connection Error
```bash
# Make sure Redis is running
docker ps | grep redis

# If not, start it
docker run -d --name redis-schema-diff -p 6379:6379 redis:7-alpine
```

### Module Not Found Errors
```bash
# Backend
cd backend && pip install -r requirements.txt

# Frontend
cd frontend && npm install
```

## 📚 Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) if migrating from the old tool
- Explore the API docs at http://localhost:8000/docs