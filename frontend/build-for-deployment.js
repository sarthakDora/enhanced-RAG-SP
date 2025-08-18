const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

console.log('Enhanced RAG Frontend Deployment Builder');
console.log('=' .repeat(40));

// Check if we're in the frontend directory
if (!fs.existsSync('package.json')) {
    console.error('Error: package.json not found. Please run this script from the frontend directory.');
    process.exit(1);
}

// Install dependencies if node_modules doesn't exist
if (!fs.existsSync('node_modules')) {
    console.log('Installing dependencies...');
    try {
        execSync('npm install', { stdio: 'inherit' });
    } catch (error) {
        console.error('Failed to install dependencies:', error.message);
        process.exit(1);
    }
}

// Build the application
console.log('Building application for production...');
try {
    execSync('npm run build', { stdio: 'inherit' });
} catch (error) {
    console.error('Build failed:', error.message);
    process.exit(1);
}

// Create deployment package
const deployDir = 'deployment';
const distDir = 'dist';

console.log('Creating deployment package...');

// Remove existing deployment directory
if (fs.existsSync(deployDir)) {
    fs.rmSync(deployDir, { recursive: true, force: true });
}

// Create deployment directory structure
fs.mkdirSync(deployDir, { recursive: true });
fs.mkdirSync(path.join(deployDir, 'static'), { recursive: true });

// Copy built files
console.log('Copying built files...');
if (fs.existsSync(distDir)) {
    // Copy all files from dist to deployment/static
    const copyRecursiveSync = (src, dest) => {
        const exists = fs.existsSync(src);
        const stats = exists && fs.statSync(src);
        const isDirectory = exists && stats.isDirectory();
        
        if (isDirectory) {
            if (!fs.existsSync(dest)) {
                fs.mkdirSync(dest);
            }
            fs.readdirSync(src).forEach(childItemName => {
                copyRecursiveSync(
                    path.join(src, childItemName),
                    path.join(dest, childItemName)
                );
            });
        } else {
            fs.copyFileSync(src, dest);
        }
    };
    
    // Find the actual build output directory (usually dist/enhanced-rag-frontend)
    const distContents = fs.readdirSync(distDir);
    let buildOutputDir = distDir;
    
    if (distContents.length === 1 && fs.statSync(path.join(distDir, distContents[0])).isDirectory()) {
        buildOutputDir = path.join(distDir, distContents[0]);
    }
    
    copyRecursiveSync(buildOutputDir, path.join(deployDir, 'static'));
} else {
    console.error('Build output directory not found. Make sure the build completed successfully.');
    process.exit(1);
}

// Create simple HTTP server script for deployment
const serverScript = `#!/usr/bin/env python3
"""
Simple HTTP server for Enhanced RAG Frontend
Serves the static files and provides basic routing for Angular SPA
"""
import os
import sys
import http.server
import socketserver
from urllib.parse import urlparse
import webbrowser
from pathlib import Path

class SPAHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler for Single Page Applications"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory='static', **kwargs)
    
    def end_headers(self):
        """Add CORS headers and cache control"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        
        # Cache control for static assets
        if self.path.endswith(('.js', '.css', '.png', '.jpg', '.gif', '.svg', '.ico', '.woff', '.woff2')):
            self.send_header('Cache-Control', 'public, max-age=86400')  # 1 day
        else:
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        
        super().end_headers()
    
    def do_GET(self):
        """Handle GET requests with SPA routing"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # Remove leading slash
        if path.startswith('/'):
            path = path[1:]
        
        # If path is empty, serve index.html
        if not path or path == '/':
            path = 'index.html'
        
        # Check if file exists
        file_path = os.path.join('static', path)
        if os.path.isfile(file_path):
            # File exists, serve it
            self.path = '/' + path
            super().do_GET()
        else:
            # File doesn't exist, check if it's a directory with index.html
            if os.path.isdir(file_path):
                index_path = os.path.join(file_path, 'index.html')
                if os.path.isfile(index_path):
                    self.path = '/' + path + '/index.html'
                    super().do_GET()
                    return
            
            # For SPA routing, serve index.html for non-file requests
            if not os.path.splitext(path)[1]:  # No file extension
                self.path = '/index.html'
                super().do_GET()
            else:
                # File request that doesn't exist - return 404
                super().do_GET()
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS"""
        self.send_response(200)
        self.end_headers()

def main():
    """Start the HTTP server"""
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 4200
    
    print(f"Enhanced RAG Frontend Server")
    print(f"Serving at http://localhost:{port}")
    print(f"Serving files from: {os.path.abspath('static')}")
    print("")
    print("Make sure the backend is running at http://localhost:8000")
    print("Press Ctrl+C to stop the server")
    print("")
    
    try:
        with socketserver.TCPServer(("", port), SPAHandler) as httpd:
            # Open browser
            try:
                webbrowser.open(f'http://localhost:{port}')
            except:
                pass  # Browser opening is optional
            
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\\nServer stopped")
    except OSError as e:
        if e.errno == 48:  # Port already in use
            print(f"Port {port} is already in use. Try a different port:")
            print(f"python server.py 8080")
        else:
            print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
`;

fs.writeFileSync(path.join(deployDir, 'server.py'), serverScript);

// Create batch file for Windows
const batchScript = `@echo off
echo Starting Enhanced RAG Frontend...
echo.
echo Make sure the backend is running at http://localhost:8000
echo Opening browser at http://localhost:4200
echo.
python server.py 4200
pause
`;

fs.writeFileSync(path.join(deployDir, 'start-frontend.bat'), batchScript);

// Create shell script for Unix
const shellScript = `#!/bin/bash
echo "Starting Enhanced RAG Frontend..."
echo ""
echo "Make sure the backend is running at http://localhost:8000"
echo "Opening browser at http://localhost:4200"
echo ""
python3 server.py 4200
`;

fs.writeFileSync(path.join(deployDir, 'start-frontend.sh'), shellScript);

// Make shell script executable (Unix systems)
try {
    fs.chmodSync(path.join(deployDir, 'start-frontend.sh'), 0o755);
} catch (error) {
    // Windows doesn't support chmod, ignore error
}

// Create configuration file
const configTemplate = `# Enhanced RAG Frontend Configuration
# This file contains the backend API endpoint configuration

# Backend API Configuration
BACKEND_URL=http://localhost:8000

# Frontend Configuration
FRONTEND_PORT=4200

# Notes:
# - Make sure the backend is running before starting the frontend
# - The backend should be accessible at the BACKEND_URL
# - If you change the backend port, update BACKEND_URL accordingly
# - If port 4200 is in use, you can start with: python server.py 8080
`;

fs.writeFileSync(path.join(deployDir, 'config.txt'), configTemplate);

// Create README for deployment
const readmeContent = `# Enhanced RAG Frontend Deployment

This directory contains the built frontend application ready for deployment.

## Contents
- \`static/\` - Built Angular application files
- \`server.py\` - Python HTTP server for serving the application
- \`start-frontend.bat\` - Windows startup script
- \`start-frontend.sh\` - Unix/Linux/Mac startup script
- \`config.txt\` - Configuration notes

## Requirements
- Python 3.6 or higher (for the HTTP server)
- Running backend server (usually at http://localhost:8000)

## Deployment Instructions

### Method 1: Using Python Server (Recommended)
1. Ensure Python is installed on the target machine
2. Run the appropriate startup script:
   - Windows: Double-click \`start-frontend.bat\`
   - Unix/Linux/Mac: Run \`./start-frontend.sh\`
3. The application will open in your default browser at http://localhost:4200

### Method 2: Custom Port
If port 4200 is in use, you can specify a different port:
\`\`\`
python server.py 8080
\`\`\`

### Method 3: Using Any HTTP Server
The \`static/\` directory contains all the built files and can be served by any HTTP server:
- Apache HTTP Server
- Nginx
- IIS
- Node.js http-server
- Any other static file server

## Important Notes
1. Make sure the backend server is running before accessing the frontend
2. The frontend is configured to connect to the backend at http://localhost:8000
3. If your backend is running on a different host/port, you may need to rebuild with updated configuration
4. For production deployment, consider using a proper web server like Nginx or Apache

## Troubleshooting
- If you get "connection refused" errors, check that the backend is running
- If the page loads but data doesn't appear, verify the backend API is accessible
- For CORS issues, ensure the backend allows requests from your frontend domain
`;

fs.writeFileSync(path.join(deployDir, 'README.md'), readmeContent);

console.log('\\n' + '='.repeat(40));
console.log('Frontend deployment package created successfully!');
console.log('\\nFiles created in deployment/ directory:');
console.log('- static/ (built application files)');
console.log('- server.py (Python HTTP server)');
console.log('- start-frontend.bat (Windows startup script)');
console.log('- start-frontend.sh (Unix startup script)');
console.log('- config.txt (configuration notes)');
console.log('- README.md (deployment instructions)');
console.log('\\nTo deploy:');
console.log('1. Copy the entire "deployment" directory to the target machine');
console.log('2. Ensure Python is installed on the target machine');
console.log('3. Make sure the backend is running');
console.log('4. Run start-frontend.bat (Windows) or start-frontend.sh (Unix)');