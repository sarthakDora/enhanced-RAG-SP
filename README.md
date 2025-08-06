# Enhanced RAG System for Financial Institution

A comprehensive Retrieval-Augmented Generation (RAG) system designed specifically for financial institutions, featuring advanced document processing, multi-strategy reranking, and a modern glassmorphism UI.

## 🚀 Features

### Backend (FastAPI + Python)
- **Advanced PDF Processing**: Multi-strategy extraction using PyMuPDF, Camelot, and PDFPlumber
- **Comprehensive Metadata Extraction**: 50+ fields per document chunk including financial metrics
- **Multi-Strategy Reranking**: Semantic, metadata, financial, and hybrid reranking algorithms
- **Vector Database**: Qdrant integration for high-performance similarity search
- **LLM Integration**: Ollama support for local LLM inference (nomic-embed-text, gemma2:7b)
- **Chat Memory**: Persistent conversation management with context awareness
- **Financial Document Types**: Support for financial reports, legal contracts, compliance documents, and performance attribution

### Frontend (Angular + Glassmorphism Design)
- **Modern UI**: Glassmorphism design with backdrop blur effects
- **Drag & Drop Upload**: Multi-file PDF upload with progress tracking
- **Real-time Chat**: WebSocket-based chat with typing indicators
- **Source Attribution**: Confidence scores and document source tracking
- **Advanced Filtering**: Metadata-based search filters
- **Responsive Design**: Mobile-friendly interface

### Infrastructure
- **Docker Compose**: Complete containerized deployment
- **Qdrant Vector DB**: High-performance vector similarity search
- **Ollama Integration**: Local LLM inference without cloud dependencies
- **Windows Compatible**: Optimized for Windows development environment

## 📋 Prerequisites

- **Python 3.12** (installed at: `C:\\Users\\patha\\AppData\\Local\\Programs\\Python\\Python312\\`)
- **Node.js 18+** and **npm**
- **Docker Desktop**
- **Git**

## 🛠️ Quick Start

### 1. Clone and Setup

```bash
cd C:\\Projects\\enhanced-RAG-3
```

### 2. Run Setup Script

```bash
# Run the automated setup script
setup.bat
```

This script will:
- Create Python virtual environment
- Install all dependencies
- Create necessary directories
- Start Docker services (Qdrant)

### 3. Install Ollama Models

```bash
# Install Ollama from https://ollama.ai
# Then pull the required models:
ollama pull nomic-embed-text
ollama pull gemma2:7b
```

### 4. Start Backend

```bash
# Activate virtual environment
venv\\Scripts\\activate

# Start FastAPI server
python backend\\main.py
```

The backend will be available at: `http://localhost:8000`

### 5. Start Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start Angular development server
npm start
```

The frontend will be available at: `http://localhost:4200`

## 📚 API Documentation

Once the backend is running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Key Endpoints

- `POST /api/documents/upload` - Upload financial documents
- `POST /api/documents/search` - Search documents with RAG
- `POST /api/chat/message` - Send chat messages
- `GET /api/health` - System health check

## 🏗️ System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Angular UI    │ ─→ │   FastAPI       │ ─→ │   Qdrant DB     │
│  (Port 4200)    │    │  (Port 8000)    │    │  (Port 6333)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Ollama LLM    │
                       │  (Port 11434)   │
                       └─────────────────┘
```

## 📁 Project Structure

```
enhanced-RAG-3/
├── backend/
│   ├── app/
│   │   ├── core/           # Configuration
│   │   ├── models/         # Pydantic models
│   │   ├── routers/        # API endpoints
│   │   ├── services/       # Business logic
│   │   └── utils/          # Utilities
│   └── main.py            # FastAPI application
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── components/ # Angular components
│   │   │   ├── models/     # TypeScript models
│   │   │   └── services/   # Angular services
│   │   └── styles.scss    # Global styles
├── sample_documents/      # Sample financial documents
├── docker-compose.yml     # Docker services
├── requirements.txt       # Python dependencies
└── setup.bat             # Windows setup script
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the root directory:

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

### Docker Services

Start required services:

```bash
docker-compose up -d
```

This starts:
- **Qdrant**: Vector database on port 6333
- **Qdrant Dashboard**: Web UI on port 6334

## 📄 Document Processing

### Supported Document Types

1. **Financial Reports**: Quarterly/annual earnings, revenue analysis
2. **Legal Contracts**: Investment agreements, fund documents
3. **Compliance Reports**: SOX compliance, regulatory filings
4. **Market Analysis**: Research reports, market assessments
5. **Performance Attribution**: Portfolio performance analysis

### Metadata Extraction

The system extracts 50+ metadata fields including:

- **Financial Metrics**: Revenue, EBITDA, ROE, ROA, etc.
- **Document Structure**: Page count, tables, charts
- **Company Information**: Name, sector, fiscal year
- **Performance Data**: Attribution periods, benchmarks
- **Content Analysis**: Topics, entities, confidence scores

## 🔍 Search & RAG Features

### Multi-Strategy Reranking

1. **Semantic Reranking**: Content similarity matching
2. **Metadata Reranking**: Document metadata relevance
3. **Financial Reranking**: Financial keyword and metric weighting
4. **Hybrid Reranking**: Combined approach for optimal results

### Advanced Filtering

- Document type filtering
- Fiscal year/quarter selection
- Company name filtering
- Tag-based categorization
- Date range filtering
- Confidence score thresholds

## 💬 Chat Features

### Financial AI Assistant

- **Context-Aware**: Maintains conversation history
- **Source Attribution**: Shows document sources with confidence scores
- **Financial Expertise**: Specialized prompts for financial analysis
- **Real-time**: WebSocket-based communication
- **Multi-modal**: Text and document analysis

### Sample Queries

- "What was the revenue growth in Q4 2023?"
- "Show me compliance issues from the SOX report"
- "Analyze the performance attribution for tech stocks"
- "What are the key risk factors mentioned in contracts?"

## 🎨 UI/UX Features

### Glassmorphism Design

- **Backdrop Blur Effects**: Modern glass-like appearance
- **Gradient Backgrounds**: Smooth color transitions
- **Transparent Elements**: Layered visual depth
- **Smooth Animations**: Fade-in, slide-up, scale effects
- **Responsive Layout**: Mobile and desktop optimized

### Key Components

- **Chat Interface**: Real-time messaging with typing indicators
- **Document Upload**: Drag-and-drop with progress tracking
- **Search Interface**: Advanced filtering options
- **Analytics Dashboard**: Performance metrics (coming soon)

## 🧪 Testing with Sample Documents

The system includes sample financial documents:

1. **financial_report_q4_2023.txt**: Quarterly earnings report
2. **investment_contract_tech_fund.txt**: Investment management agreement
3. **compliance_report_sox_2023.txt**: SOX compliance assessment
4. **performance_attribution_report.txt**: Portfolio performance analysis

Upload these documents to test the system's capabilities.

## 🚀 Production Deployment

### Security Considerations

- Change default secret keys
- Enable HTTPS/TLS encryption
- Implement proper authentication
- Configure firewall rules
- Regular security updates

### Scaling Options

- **Database**: Replace in-memory storage with PostgreSQL
- **Vector Store**: Scale Qdrant with clustering
- **Load Balancing**: Multiple FastAPI instances
- **Caching**: Redis for session management
- **Monitoring**: Implement logging and metrics

## 🛠️ Development

### Adding New Document Types

1. Update `DocumentType` enum in models
2. Create specialized metadata extraction in `document_processor.py`
3. Add type-specific icons in frontend components
4. Update reranking strategies if needed

### Customizing Reranking

1. Modify weights in `reranking_service.py`
2. Add new ranking factors
3. Implement domain-specific scoring
4. A/B test ranking strategies

### Extending Chat Features

1. Add new system prompts in `chat_service.py`
2. Implement custom tools/functions
3. Add conversation templates
4. Integrate external APIs

## 📊 Performance Metrics

### Backend Performance
- Document processing: ~5-10 seconds per PDF
- Vector search: <100ms for typical queries
- Chat response: 2-5 seconds depending on context

### Frontend Performance
- Initial load: <2 seconds
- Chat interactions: <500ms
- File upload: Real-time progress tracking

## 🐛 Troubleshooting

### Common Issues

1. **Ollama connection failed**
   - Ensure Ollama is installed and running
   - Check models are pulled: `ollama list`

2. **Qdrant connection failed**
   - Verify Docker is running: `docker ps`
   - Restart services: `docker-compose restart`

3. **PDF processing errors**
   - Check file size limits (100MB default)
   - Verify supported formats (PDF, DOCX, TXT)

4. **Frontend build errors**
   - Clear node_modules: `rm -rf node_modules && npm install`
   - Check Node.js version: `node --version`

### Health Checks

- Backend: `http://localhost:8000/api/health`
- Qdrant: `http://localhost:6333/dashboard`
- Frontend: Check browser console for errors

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/new-feature`
3. Commit changes: `git commit -m 'Add new feature'`
4. Push to branch: `git push origin feature/new-feature`
5. Submit pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Qdrant** for vector database technology
- **Ollama** for local LLM inference
- **FastAPI** for modern Python web framework
- **Angular** for frontend framework
- **Material Design** for UI components

## 📞 Support

For questions or support:
- Open an issue on GitHub
- Check the troubleshooting section
- Review API documentation

---

**Enhanced RAG System v1.0.0** - Built for Financial Institution Excellence 🏦✨