#!/bin/bash
echo "Enhanced RAG System - Stop All Services"
echo "======================================="
echo ""
echo "Stopping all Enhanced RAG services..."
echo ""

echo "Stopping Qdrant container..."
docker stop enhanced-rag-qdrant 2>/dev/null
docker rm enhanced-rag-qdrant 2>/dev/null
echo "Qdrant stopped."
echo ""

echo "Stopping backend and frontend processes..."
echo ""

# Kill processes by name and command line
pkill -f "enhanced-rag-backend" 2>/dev/null
pkill -f "python.*main.py" 2>/dev/null
pkill -f "python.*server.py" 2>/dev/null
pkill -f "node.*ng serve" 2>/dev/null
pkill -f "npm.*start" 2>/dev/null

echo ""
echo "======================================="
echo "All Enhanced RAG services stopped!"
echo "======================================="
echo ""
echo "Services that were stopped:"
echo "- Qdrant vector database"
echo "- Backend API server"
echo "- Frontend web server"
echo ""