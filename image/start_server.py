#!/usr/bin/env python3
"""
Startup script for Smart Invoice Validator API.
This script properly sets up the Python path and starts the FastAPI server.
"""

import sys
import os
from pathlib import Path

# Add the src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

if __name__ == "__main__":
    import uvicorn
    
    # Change working directory to src so .env file is found
    os.chdir(src_path)
    
    # Set environment variables if not already set
    os.environ.setdefault("PYTHONPATH", str(src_path))
    
    # Start the FastAPI application
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(src_path)],
        log_level="info"
    )
