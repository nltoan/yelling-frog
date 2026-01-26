#!/usr/bin/env python3
"""
Run the Web Crawler API server with frontend
"""
import os
import sys

# Ensure we're in the right directory
sys.path.insert(0, '/app')

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

# Create main app
main_app = FastAPI(
    title="Web Crawler - Screaming Frog Clone",
    description="Complete SEO web crawler with ALL Screaming Frog features",
    version="1.0.0"
)

# Create data directory if it doesn't exist
os.makedirs('/app/data', exist_ok=True)
os.makedirs('/tmp', exist_ok=True)

# Import the API app and mount it
from webcrawler.api.main import app as api_app
main_app.mount("/api", api_app)

# Mount frontend
frontend_path = '/app/frontend'
if os.path.exists(frontend_path):
    # Serve static files
    if os.path.exists(f'{frontend_path}/static'):
        main_app.mount("/static", StaticFiles(directory=f"{frontend_path}/static"), name="static")

    # Serve index.html at root
    @main_app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(f"{frontend_path}/index.html")

if __name__ == "__main__":
    print("=" * 60)
    print("🕷️  Web Crawler - Screaming Frog Clone")
    print("=" * 60)
    print("Web UI: http://0.0.0.0:8000/")
    print("API: http://0.0.0.0:8000/api")
    print("API Docs: http://0.0.0.0:8000/api/docs")
    print("=" * 60)

    uvicorn.run(main_app, host="0.0.0.0", port=8000, log_level="info")
