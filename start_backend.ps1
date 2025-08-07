#!/usr/bin/env powershell
Write-Host "Starting Enhanced RAG Backend Server..."
Write-Host "======================================="

# Change to backend directory relative to script location
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location (Join-Path $scriptDir 'backend')
Write-Host "Working directory: $(Get-Location)"

# Set Python path
$env:PYTHONPATH = (Join-Path $scriptDir 'backend')

# Start the server
Write-Host "Starting uvicorn server on http://localhost:8000..."
& (Join-Path $scriptDir 'venv\Scripts\python.exe') -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info

Write-Host "Server stopped."