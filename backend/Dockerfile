FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install system dependencies (minimal set for server environment)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    ghostscript \
    default-jre \
    libgomp1 \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set work directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements-minimal.txt .

# Upgrade pip first, then install dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements-minimal.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs uploads processed backend/processed

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Command to run the application with startup delay
CMD ["sh", "-c", "sleep 10 && uvicorn main:app --host 0.0.0.0 --port 8000"]