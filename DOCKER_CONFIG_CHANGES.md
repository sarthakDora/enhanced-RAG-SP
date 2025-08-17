# 🔧 Docker Configuration Changes Guide

This guide explains how to modify configurations (like Ollama model names) when running the Enhanced RAG application in Docker.

## 📋 Quick Reference

When you change configuration files, you need to:

1. **Stop the containers**
2. **Rebuild the affected service**  
3. **Restart the containers**

## 🎯 Common Configuration Changes

### 1. Changing Ollama Model Name

**Location**: `backend/app/core/config.py`

```python
# Example change in config.py
class Settings(BaseSettings):
    ollama_model: str = "llama3.1:8b"  # Changed from "llama2"
    ollama_host: str = "ollama"
    ollama_port: int = 11434
```

**Steps to apply the change:**

```bash
# 1. Stop all containers
docker-compose down

# 2. Rebuild backend container (since config.py is in backend)
docker-compose build backend

# 3. Start all containers
docker-compose up -d

# 4. Check logs to ensure the new model is loaded
docker-compose logs -f backend
```

### 2. Changing Database Settings

**Location**: `backend/app/core/config.py`

```python
# Example: Change Qdrant collection settings
class Settings(BaseSettings):
    qdrant_collection_name: str = "my_new_collection"
    qdrant_vector_size: int = 1536  # Changed vector dimensions
```

**Steps to apply:**
```bash
docker-compose down
docker-compose build backend
docker-compose up -d
```

### 3. Changing Frontend API URLs

**Location**: `frontend/src/environments/environment.ts`

```typescript
export const environment = {
  production: true,
  apiUrl: 'http://localhost:8000',  // Changed API URL
  wsUrl: 'ws://localhost:8000'
};
```

**Steps to apply:**
```bash
docker-compose down
docker-compose build frontend  # Frontend needs rebuild
docker-compose up -d
```

## 🚀 Step-by-Step Workflows

### Workflow 1: Backend Configuration Changes

```bash
# 1. Edit your config file
nano backend/app/core/config.py

# 2. Stop and rebuild
docker-compose down
docker-compose build backend --no-cache
docker-compose up -d

# 3. Verify changes
docker-compose logs backend | grep -i "model\|config"
```

### Workflow 2: Environment Variable Changes

**Option A: Using .env.docker file**

```bash
# 1. Edit environment variables
nano .env.docker

# Example changes:
# OLLAMA_MODEL=llama3.1:8b
# QDRANT_COLLECTION=new_collection

# 2. Restart containers (no rebuild needed for env vars)
docker-compose down
docker-compose up -d
```

**Option B: Using docker-compose.yml**

```yaml
# Edit docker-compose.yml
services:
  backend:
    environment:
      - OLLAMA_MODEL=llama3.1:8b
      - QDRANT_COLLECTION=new_collection
```

```bash
# Apply changes
docker-compose down
docker-compose up -d
```

### Workflow 3: Adding New Dependencies

**If you add new Python packages:**

```bash
# 1. Edit requirements file
nano backend/requirements-minimal.txt

# 2. Rebuild with no cache
docker-compose down
docker-compose build backend --no-cache
docker-compose up -d
```

**If you add new npm packages:**

```bash
# 1. Add to package.json
nano frontend/package.json

# 2. Rebuild frontend
docker-compose down
docker-compose build frontend --no-cache
docker-compose up -d
```

## 🎯 Quick Commands Reference

```bash
# Stop all services
docker-compose down

# Rebuild specific service
docker-compose build <service-name>

# Rebuild without cache (clean build)
docker-compose build <service-name> --no-cache

# Rebuild all services
docker-compose build

# Start services
docker-compose up -d

# View logs for specific service
docker-compose logs -f <service-name>

# Restart specific service without rebuild
docker-compose restart <service-name>

# Complete reset (removes volumes too)
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

## 🔍 Troubleshooting Configuration Changes

### Issue: Changes not reflected after restart

**Solution:**
```bash
# Force rebuild without cache
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Issue: Ollama model not loading

**Check if model exists in container:**
```bash
# List available models
docker-compose exec ollama ollama list

# Pull new model if needed
docker-compose exec ollama ollama pull llama3.1:8b
```

### Issue: Frontend not connecting to backend

**Check environment variables:**
```bash
# View frontend container environment
docker-compose exec frontend env | grep API

# Check nginx configuration
docker-compose exec frontend cat /etc/nginx/nginx.conf
```

### Issue: Database connection errors

**Check backend logs and restart sequence:**
```bash
# View backend logs
docker-compose logs backend

# Restart with dependency order
docker-compose down
docker-compose up -d qdrant  # Start database first
sleep 10
docker-compose up -d backend  # Then backend
docker-compose up -d frontend  # Finally frontend
```

## 💡 Best Practices

1. **Always stop containers before rebuilding**
2. **Use `--no-cache` flag when dependencies change**
3. **Check logs after changes to verify everything works**
4. **Keep backup of working configurations**
5. **Test changes in development mode first**

## 🔄 Development vs Production Changes

### Development Mode
```bash
# Use override file for live changes
docker-compose -f docker-compose.yml -f docker-compose.override.yml up
```

### Production Mode
```bash
# Always rebuild for production
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## 📝 Example: Complete Model Change Workflow

Let's say you want to change from `llama2` to `llama3.1:8b`:

```bash
# 1. Edit the configuration
nano backend/app/core/config.py
# Change: ollama_model: str = "llama3.1:8b"

# 2. Stop everything
docker-compose down

# 3. Pull the new model (optional, can be done after restart)
docker-compose up -d ollama
docker-compose exec ollama ollama pull llama3.1:8b
docker-compose down

# 4. Rebuild backend with new config
docker-compose build backend --no-cache

# 5. Start all services
docker-compose up -d

# 6. Verify the new model is being used
docker-compose logs backend | grep -i llama
```

This ensures your configuration changes are properly applied and the Docker environment reflects your updates!