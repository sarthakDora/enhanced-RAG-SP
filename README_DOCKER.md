# 🐳 Enhanced RAG - Complete Docker Setup

Your Enhanced RAG application is now **fully containerized** and ready to run without any local dependencies!

## ✅ What's Included

- **Backend API** (FastAPI + Python) - Port 8000
- **Frontend Web App** (Angular + Nginx) - Port 80  
- **Vector Database** (Qdrant) - Port 6333
- **LLM Server** (Ollama) - Port 11434

## 🚀 Quick Start

### Option 1: Use the Startup Scripts (Recommended)

**Windows:**
```cmd
docker-start.bat
```

**Linux/Mac:**
```bash
./docker-start.sh
```

### Option 2: Manual Docker Compose

```bash
# Start all services
docker-compose up --build

# Or run in background
docker-compose up --build -d
```

## 📱 Access Your Application

Once running, access:

- **Frontend**: http://localhost
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs  
- **Qdrant Dashboard**: http://localhost:6333/dashboard
- **Ollama API**: http://localhost:11434

## 🔧 Management Commands

```bash
# Check service status
docker-compose ps

# View logs (all services)
docker-compose logs -f

# View logs (specific service)
docker-compose logs -f backend

# Stop everything
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Restart a specific service
docker-compose restart backend
```

## 🎯 Key Benefits

✅ **Zero Dependencies** - No need to install Python, Node.js, or any other tools  
✅ **Complete Isolation** - Everything runs in containers  
✅ **Easy Development** - Hot reload support with dev mode  
✅ **Production Ready** - Optimized builds and configurations  
✅ **Persistent Data** - Your uploads, models, and vector data are preserved  
✅ **Health Monitoring** - Built-in health checks for all services  

## 🛠️ Troubleshooting

### Port Conflicts
If you get port errors, check what's using the ports:
```bash
# Windows
netstat -an | findstr :80
netstat -an | findstr :8000

# Linux/Mac  
lsof -i :80
lsof -i :8000
```

### Memory Issues
- Ensure Docker has at least 8GB RAM allocated
- Check Docker Desktop settings

### Build Issues
```bash
# Clean rebuild everything
docker-compose down --rmi all
docker-compose up --build --force-recreate
```

### Health Check Issues
```bash
# Check container health
docker-compose ps

# Check logs for errors
docker-compose logs backend
docker-compose logs frontend
```

## 📊 Resource Requirements

- **Minimum**: 4GB RAM, 2 CPU cores
- **Recommended**: 8GB RAM, 4 CPU cores  
- **Storage**: ~5GB for containers + your data

## 🔄 Development Mode

For development with hot reload:

```bash
docker-compose -f docker-compose.yml -f docker-compose.override.yml up
```

This enables:
- Live code changes
- Debug logging
- Development configurations

## 🚨 First Time Setup

1. **Install Docker Desktop** and ensure it's running
2. **Clone this repository**
3. **Run the startup script** or `docker-compose up --build`
4. **Wait for all services** to become healthy (2-3 minutes first time)
5. **Access the frontend** at http://localhost

## ⚠️ Important Notes

- **Module Issues Fixed**: The `langchain_ollama` import error has been resolved with the `ollama` package
- **Configuration Changes**: When you modify config files (like Ollama model names), see [DOCKER_CONFIG_CHANGES.md](DOCKER_CONFIG_CHANGES.md) for the proper workflow
- **Dependencies**: All Python packages are containerized - no local Python installation needed

## 🔧 Configuration Changes

If you need to change settings like the Ollama model name in `config.py`:

```bash
# 1. Edit your configuration
nano backend/app/core/config.py

# 2. Rebuild and restart
docker-compose down
docker-compose build backend --no-cache
docker-compose up -d
```

See [DOCKER_CONFIG_CHANGES.md](DOCKER_CONFIG_CHANGES.md) for detailed instructions.

## 🎉 Success!

Your Enhanced RAG application is now running in Docker containers. No more dependency issues - just pure containerized goodness!

For detailed documentation, see [DOCKER_SETUP.md](DOCKER_SETUP.md).