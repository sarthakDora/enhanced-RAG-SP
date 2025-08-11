# Complete Setup Guide - Enhanced RAG System

This guide provides comprehensive instructions for setting up and running the Enhanced RAG System locally on any machine.

## 📋 Prerequisites

Before starting, ensure you have the following installed:

### Required Software
1. **Python 3.12+** - [Download from python.org](https://www.python.org/downloads/)
2. **Node.js 18+** and **npm** - [Download from nodejs.org](https://nodejs.org/)
3. **Docker Desktop** - [Download from docker.com](https://www.docker.com/products/docker-desktop/)
4. **Git** - [Download from git-scm.com](https://git-scm.com/downloads)
5. **Ollama** - [Download from ollama.ai](https://ollama.ai)

### System Requirements
- **RAM**: Minimum 8GB, Recommended 16GB+
- **Storage**: At least 10GB free space
- **OS**: Windows 10/11, macOS, or Linux

## 🚀 Step-by-Step Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd enhanced-RAG-3
```

### 2. Backend Setup

#### Create Python Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

#### Install Python Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### Backend Dependencies (from requirements.txt)
- **FastAPI & Web Server**: fastapi==0.104.1, uvicorn[standard]==0.24.0
- **LangChain Ecosystem**: langchain==0.1.0, langchain-community==0.0.10
- **Vector Database**: qdrant-client==1.7.0, sentence-transformers==2.2.2  
- **PDF Processing**: PyMuPDF==1.23.14, camelot-py[cv]==0.11.0, pdfplumber==0.10.3, tabula-py==2.8.2
- **Data Processing**: pandas==2.1.4, openpyxl==3.1.2, numpy==1.25.2
- **OCR & Image Processing**: pytesseract==0.3.10, Pillow==10.1.0, opencv-python==4.8.1.78
- **HTTP Clients**: httpx==0.25.2, aiohttp==3.9.1
- **Configuration**: python-dotenv==1.0.0, pydantic==2.5.2
- **Testing**: pytest==7.4.3, pytest-asyncio==0.21.1

### 3. Frontend Setup

```bash
cd frontend

# Install Node.js dependencies
npm install
```

#### Frontend Dependencies (from package.json)
- **Angular Framework**: @angular/core@^17.0.0, @angular/common@^17.0.0
- **Angular Material**: @angular/material@^17.0.0, @angular/cdk@^17.0.0
- **UI Libraries**: marked@^9.1.6, highlight.js@^11.9.0
- **WebSocket**: socket.io-client@^4.7.4
- **Development Tools**: @angular/cli@^17.0.0, typescript@~5.2.0

### 4. Docker Services Setup

#### Start Qdrant Vector Database
```bash
# From project root directory
docker-compose up -d
```

This starts:
- **Qdrant Vector Database** on port 6333
- **Qdrant Web Dashboard** on port 6334

#### Verify Docker Services
```bash
# Check running containers
docker ps

# You should see qdrant_financial_rag container running
```

### 5. Ollama LLM Setup

#### Install Ollama Models
```bash
# Pull required embedding model
ollama pull nomic-embed-text

# Pull required language model  
ollama pull gemma2:7b

# Verify models are installed
ollama list
```

#### Start Ollama Service
```bash
# Ollama should start automatically after installation
# Verify it's running:
ollama serve
```

### 6. Environment Configuration

Create a `.env` file in the project root:

```env
# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text
LLM_MODEL=gemma2:7b

# Qdrant Configuration
QDRANT_URL=http://localhost:6333
COLLECTION_NAME=financial_documents

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=True

# File Processing
MAX_FILE_SIZE=100000000
UPLOAD_DIR=./uploads
```

### 7. Create Required Directories

```bash
# From project root
mkdir -p uploads processed logs
mkdir -p backend/logs
```

## ▶️ Running the Application

### 1. Start Backend Server

```bash
# Make sure virtual environment is activated
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# Start FastAPI server
cd backend
python main.py
```

Backend will be available at: **http://localhost:8000**

### 2. Start Frontend Server

```bash
# In a new terminal, from project root
cd frontend

# Start Angular development server
npm start
```

Frontend will be available at: **http://localhost:4200**

### 3. Verify All Services

Check that all services are running:

- **Frontend**: http://localhost:4200
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Qdrant Dashboard**: http://localhost:6333/dashboard
- **Ollama API**: http://localhost:11434 (curl http://localhost:11434/api/version)

## 🔧 Alternative Setup Scripts

### Windows Batch Script (setup.bat)
```batch
@echo off
echo Setting up Enhanced RAG System...

# Create virtual environment
python -m venv venv
call venv\Scripts\activate.bat

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create directories
mkdir uploads processed logs backend\logs

# Start Docker services
docker-compose up -d

# Install frontend dependencies
cd frontend
npm install
cd ..

echo Setup complete!
echo.
echo Next steps:
echo 1. Install Ollama models: ollama pull nomic-embed-text && ollama pull gemma2:7b
echo 2. Start backend: venv\Scripts\activate && python backend\main.py
echo 3. Start frontend: cd frontend && npm start
```

### Linux/macOS Shell Script (setup.sh)
```bash
#!/bin/bash
echo "Setting up Enhanced RAG System..."

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create directories
mkdir -p uploads processed logs backend/logs

# Start Docker services
docker-compose up -d

# Install frontend dependencies
cd frontend
npm install
cd ..

echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Install Ollama models: ollama pull nomic-embed-text && ollama pull gemma2:7b"
echo "2. Start backend: source venv/bin/activate && python backend/main.py"
echo "3. Start frontend: cd frontend && npm start"
```

## 🧪 Testing the Installation

### 1. Test Backend Health
```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{"status": "healthy", "timestamp": "..."}
```

### 2. Test File Upload
- Navigate to http://localhost:4200
- Use the drag-and-drop interface to upload a PDF
- Check the uploads directory for the uploaded file

### 3. Test Chat Functionality
- Open the chat interface
- Ask a question like "Hello, can you help me?"
- Verify you receive a response

## 🐛 Troubleshooting

### Common Issues and Solutions

#### 1. Python Virtual Environment Issues
```bash
# If venv creation fails, try:
python -m pip install --upgrade pip
python -m pip install virtualenv
python -m virtualenv venv
```

#### 2. Port Already in Use
```bash
# Check what's using the port
netstat -ano | findstr :8000  # Windows
lsof -i :8000  # macOS/Linux

# Kill the process or change port in configuration
```

#### 3. Docker Issues
```bash
# Reset Docker
docker-compose down
docker system prune -f
docker-compose up -d
```

#### 4. Ollama Connection Issues
```bash
# Restart Ollama service
ollama serve

# Check if models are available
ollama list
```

#### 5. Frontend Build Issues
```bash
# Clear npm cache and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

#### 6. Permission Issues (Linux/macOS)
```bash
# Make scripts executable
chmod +x setup.sh

# Fix directory permissions
sudo chown -R $USER:$USER .
```

## 📊 System Resource Requirements

### Minimum Requirements
- **CPU**: 4 cores
- **RAM**: 8GB
- **Storage**: 10GB free space
- **Network**: Internet connection for model downloads

### Recommended Requirements
- **CPU**: 8+ cores
- **RAM**: 16GB+
- **Storage**: 50GB+ SSD
- **GPU**: Optional, for faster LLM inference

## 🔒 Security Considerations

### Development Environment
- Default configuration is for development only
- All services run on localhost
- No authentication required

### Production Deployment
- Change all default passwords and secrets
- Enable HTTPS/TLS encryption
- Implement proper authentication
- Configure firewall rules
- Use environment variables for sensitive data

## 📚 Next Steps

After successful installation:

1. **Upload Sample Documents**: Use the sample_documents folder
2. **Explore API Documentation**: Visit http://localhost:8000/docs
3. **Test Chat Features**: Try various financial queries
4. **Customize Configuration**: Modify .env file as needed
5. **Scale Services**: Consider production deployment options

## 🤝 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Verify all prerequisites are installed
3. Check system logs in the logs/ directory
4. Review the main README.md for additional information

---

**Setup Guide Version 1.0** - Complete dependency management for Enhanced RAG System