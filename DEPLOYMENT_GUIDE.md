# Enhanced RAG System - Organizational Deployment Guide

This guide provides instructions for deploying the Enhanced RAG system in organizational environments where Docker package downloads are restricted.

## Overview

The deployment consists of:
- **Backend**: Python executable (no Python installation required on target machine)
- **Frontend**: Static files with Python HTTP server
- **Qdrant**: Docker container (vector database)

## Prerequisites

### On Development Machine (where you build)
- Python 3.8+
- Node.js 18+
- Git
- Docker (for Qdrant)

### On Target Machine (where you deploy)
- Python 3.6+ (for frontend server only)
- Docker (for Qdrant only)
- No other dependencies required

## Build Process

### Step 1: Build Backend Executable

```bash
# Navigate to backend directory
cd backend

# Install build dependencies
pip install -r requirements-exe.txt

# Build executable
python build_exe.py
```

This creates:
- `dist/enhanced-rag-backend/` - Executable directory
- `start-backend.bat` - Windows startup script
- `start-backend.sh` - Unix startup script
- `config.env.template` - Configuration template

### Step 2: Build Frontend Package

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Build deployment package
npm run build:deploy
```

This creates:
- `deployment/static/` - Built Angular application
- `deployment/server.py` - Python HTTP server
- `deployment/start-frontend.bat` - Windows startup script
- `deployment/start-frontend.sh` - Unix startup script
- `deployment/README.md` - Deployment instructions

## Deployment Process

### Step 1: Prepare Qdrant (Vector Database)

On the target machine, start Qdrant using Docker:

```bash
# Pull and run Qdrant
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant

# For persistent data, use a volume
docker run -p 6333:6333 -p 6334:6334 -v qdrant_storage:/qdrant/storage qdrant/qdrant
```

### Step 2: Deploy Backend

1. Copy the entire `backend/dist/enhanced-rag-backend/` directory to target machine
2. Copy startup scripts (`start-backend.bat`, `start-backend.sh`)
3. Copy and configure `config.env.template` (rename to `.env`)
4. Ensure Ollama is installed and running on the target machine
5. Run the appropriate startup script

### Step 3: Deploy Frontend

1. Copy the entire `frontend/deployment/` directory to target machine
2. Ensure Python 3.6+ is available on the target machine
3. Run the appropriate startup script:
   - Windows: `start-frontend.bat`
   - Unix: `./start-frontend.sh`

## Directory Structure After Deployment

```
enhanced-rag-deployment/
├── backend/
│   ├── enhanced-rag-backend/          # Executable directory
│   │   ├── enhanced-rag-backend.exe   # Main executable (Windows)
│   │   ├── enhanced-rag-backend       # Main executable (Unix)
│   │   └── _internal/                 # Dependencies
│   ├── start-backend.bat              # Windows startup
│   ├── start-backend.sh               # Unix startup
│   └── .env                          # Configuration
├── frontend/
│   ├── static/                        # Built Angular app
│   ├── server.py                      # HTTP server
│   ├── start-frontend.bat             # Windows startup
│   ├── start-frontend.sh              # Unix startup
│   └── README.md                      # Instructions
└── docker-compose.yml                 # Qdrant setup (optional)
```

## Configuration

### Backend Configuration (.env)

```env
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false

# Qdrant Configuration
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Ollama Configuration
OLLAMA_HOST=localhost
OLLAMA_PORT=11434

# File Upload Configuration
MAX_REQUEST_SIZE=104857600  # 100MB
UPLOAD_FOLDER=uploads

# Model Configuration
EMBEDDING_MODEL=all-MiniLM-L6-v2
CHAT_MODEL=llama2

# Logging
LOG_LEVEL=INFO
```

### Frontend Configuration

The frontend is pre-configured to connect to `http://localhost:8000`. If you need to change this, you'll need to rebuild with updated configuration in `src/environments/environment.ts`.

## Startup Sequence

1. **Start Qdrant**: `docker run -p 6333:6333 qdrant/qdrant`
2. **Start Ollama**: Follow Ollama installation instructions for your OS
3. **Start Backend**: Run `start-backend.bat` or `./start-backend.sh`
4. **Start Frontend**: Run `start-frontend.bat` or `./start-frontend.sh`

The application will be available at:
- Frontend: http://localhost:4200
- Backend API: http://localhost:8000
- Qdrant: http://localhost:6333

## Alternative Deployment Options

### Option 1: Nginx/Apache Deployment

Instead of the Python server, you can serve the frontend using Nginx or Apache:

1. Copy `frontend/deployment/static/` contents to your web server's document root
2. Configure the web server to serve the Angular SPA properly (redirect all routes to index.html)
3. Update CORS settings in the backend to allow your domain

### Option 2: Standalone Deployment

For completely isolated deployment:

1. Use the executable backend (no Python needed)
2. Serve frontend with any HTTP server
3. Run Qdrant with Docker
4. Install Ollama separately

### Option 3: Network Deployment

For deployment across multiple machines:

1. Deploy backend on one server
2. Deploy frontend on another server
3. Update configuration to point to correct backend URL
4. Deploy Qdrant on a database server

## Troubleshooting

### Common Issues

1. **Backend won't start**:
   - Check if Qdrant is running on port 6333
   - Verify Ollama is installed and running
   - Check `.env` configuration file

2. **Frontend can't connect to backend**:
   - Verify backend is running on port 8000
   - Check CORS configuration
   - Ensure no firewall blocking the connection

3. **Qdrant connection issues**:
   - Verify Docker is running
   - Check if port 6333 is available
   - Look at Qdrant container logs

4. **Large file upload issues**:
   - Check `MAX_REQUEST_SIZE` in backend configuration
   - Verify disk space available
   - Check network timeout settings

### Performance Tuning

1. **Backend Performance**:
   - Adjust embedding model based on hardware
   - Configure appropriate batch sizes
   - Monitor memory usage

2. **Frontend Performance**:
   - Use a proper web server (Nginx) for production
   - Enable gzip compression
   - Configure proper caching headers

3. **Qdrant Performance**:
   - Use persistent volumes
   - Configure appropriate collection settings
   - Monitor vector database performance

## Security Considerations

1. **Network Security**:
   - Use HTTPS in production
   - Configure proper CORS origins
   - Implement authentication if required

2. **File Security**:
   - Validate uploaded file types
   - Implement virus scanning
   - Set proper file size limits

3. **Access Control**:
   - Implement user authentication
   - Control API access
   - Monitor usage and access logs

## Support and Maintenance

### Logs and Monitoring

- Backend logs: Check console output or configure log files
- Frontend logs: Check browser console
- Qdrant logs: `docker logs <container_id>`
- System logs: OS-specific log locations

### Updates and Maintenance

- Backend: Rebuild executable with new code
- Frontend: Rebuild deployment package
- Qdrant: Update Docker image
- Models: Update Ollama models as needed

For technical support, please refer to the project documentation or contact the development team.