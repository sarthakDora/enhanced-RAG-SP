# Docker Setup Guide

This project is fully containerized with Docker, allowing developers to run the entire stack without installing dependencies locally.

## Prerequisites

- Docker Desktop (latest version)
- Docker Compose (included with Docker Desktop)
- At least 8GB RAM available for Docker
- For GPU acceleration: NVIDIA Docker runtime (optional)

## Quick Start

1. **Clone and navigate to the project:**
   ```bash
   git clone <repository-url>
   cd enhanced-RAG-3
   ```

2. **Start all services:**
   ```bash
   docker-compose up --build
   ```

3. **Access the application:**
   - Frontend: http://localhost
   - Backend API: http://localhost:8000
   - Qdrant Dashboard: http://localhost:6333/dashboard
   - Ollama API: http://localhost:11434

## Services Overview

The Docker setup includes four main services:

### 1. Frontend (Port 80)
- **Technology**: Angular 17 + Nginx
- **Container**: `enhanced_rag_frontend`
- **Features**: 
  - Production-optimized build
  - Nginx reverse proxy for API calls
  - Automatic routing for SPA

### 2. Backend (Port 8000)
- **Technology**: FastAPI + Python 3.11
- **Container**: `enhanced_rag_backend`
- **Features**:
  - RESTful API endpoints
  - File upload handling
  - Integration with Qdrant and Ollama
  - Health checks

### 3. Qdrant (Ports 6333, 6334)
- **Technology**: Vector database
- **Container**: `enhanced_rag_qdrant`
- **Features**:
  - Persistent vector storage
  - Web dashboard
  - HTTP and gRPC APIs

### 4. Ollama (Port 11434)
- **Technology**: Local LLM server
- **Container**: `enhanced_rag_ollama`
- **Features**:
  - GPU acceleration (if available)
  - Model management
  - API endpoint for LLM inference

## Configuration

### Environment Variables

The application uses `.env.docker` for configuration:

```bash
# Copy and customize environment file
cp .env.docker .env.local
# Edit .env.local with your specific settings
```

Key variables:
- `QDRANT_HOST=qdrant` - Vector database host
- `OLLAMA_HOST=ollama` - LLM service host
- `API_PORT=8000` - Backend API port
- `MAX_FILE_SIZE=100MB` - Upload limit

### Development Mode

For development with hot reload:

```bash
docker-compose -f docker-compose.yml -f docker-compose.override.yml up
```

This enables:
- Source code mounting for live changes
- Debug logging
- Development-specific configurations

## Data Persistence

The following data is persisted across container restarts:

- **Qdrant data**: `qdrant_storage` volume
- **Ollama models**: `ollama_data` volume
- **Uploads**: `./backend/uploads` directory
- **Processed files**: `./backend/processed` directory
- **Logs**: `./backend/logs` directory

## Common Commands

### Initial Setup
```bash
# Build and start all services
docker-compose up --build -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f [service-name]
```

### Model Management
```bash
# Pull a model in Ollama container
docker-compose exec ollama ollama pull llama2

# List available models
docker-compose exec ollama ollama list
```

### Database Operations
```bash
# Access Qdrant container
docker-compose exec qdrant /bin/bash

# Backup Qdrant data
docker-compose exec qdrant tar -czf /qdrant/storage/backup.tar.gz /qdrant/storage
```

### Development Workflow
```bash
# Rebuild specific service
docker-compose build backend
docker-compose up -d backend

# View real-time logs
docker-compose logs -f backend frontend

# Execute commands in containers
docker-compose exec backend python -c "import sys; print(sys.version)"
docker-compose exec frontend nginx -t
```

## Troubleshooting

### Common Issues

1. **Port conflicts:**
   ```bash
   # Check if ports are in use
   netstat -an | grep :80
   netstat -an | grep :8000
   
   # Modify ports in docker-compose.yml if needed
   ```

2. **Memory issues:**
   ```bash
   # Increase Docker memory limit in Docker Desktop settings
   # Recommended: 8GB+ for full stack
   ```

3. **GPU not detected:**
   ```bash
   # Install NVIDIA Docker runtime
   # Remove GPU configuration from docker-compose.yml if not needed
   ```

4. **Build failures:**
   ```bash
   # Clean build cache
   docker-compose build --no-cache
   
   # Remove orphaned containers
   docker-compose down --remove-orphans
   ```

### Health Checks

All services include health checks:

```bash
# Check health status
docker-compose ps

# Manual health check
curl http://localhost:8000/health
curl http://localhost:6333/dashboard
curl http://localhost:11434/api/tags
```

### Reset Environment

To completely reset the environment:

```bash
# Stop and remove all containers, networks, and volumes
docker-compose down -v --remove-orphans

# Remove built images (optional)
docker-compose down --rmi all

# Rebuild from scratch
docker-compose up --build
```

## Performance Optimization

### Resource Allocation
- **Minimum**: 4GB RAM, 2 CPU cores
- **Recommended**: 8GB RAM, 4 CPU cores
- **GPU**: NVIDIA GPU with CUDA support for Ollama

### Production Deployment
```bash
# Use production compose file
docker-compose -f docker-compose.yml up -d

# Enable resource limits
# Edit docker-compose.yml to add resource constraints
```

## Security Considerations

1. **Change default secrets** in `.env.docker`
2. **Use HTTPS** in production (configure nginx SSL)
3. **Restrict network access** using Docker networks
4. **Regular updates** of base images
5. **Scan images** for vulnerabilities

## Monitoring

View service metrics:
```bash
# Container stats
docker stats

# Service logs
docker-compose logs --tail=100 -f

# Health monitoring
docker-compose exec backend curl localhost:8000/health
```

## Backup and Recovery

### Backup Script
```bash
#!/bin/bash
# backup.sh
docker-compose exec qdrant tar -czf /tmp/qdrant-backup.tar.gz /qdrant/storage
docker cp $(docker-compose ps -q qdrant):/tmp/qdrant-backup.tar.gz ./backups/
docker-compose exec ollama tar -czf /tmp/ollama-backup.tar.gz /root/.ollama
docker cp $(docker-compose ps -q ollama):/tmp/ollama-backup.tar.gz ./backups/
```

### Recovery
```bash
# Restore Qdrant data
docker cp ./backups/qdrant-backup.tar.gz $(docker-compose ps -q qdrant):/tmp/
docker-compose exec qdrant tar -xzf /tmp/qdrant-backup.tar.gz -C /

# Restore Ollama models
docker cp ./backups/ollama-backup.tar.gz $(docker-compose ps -q ollama):/tmp/
docker-compose exec ollama tar -xzf /tmp/ollama-backup.tar.gz -C /
```