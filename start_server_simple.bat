@echo off
echo Starting Enhanced RAG Server...
cd /d "C:\Projects\enhanced-RAG-3\backend"
echo Current directory: %CD%
"C:\Projects\enhanced-RAG-3\venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause