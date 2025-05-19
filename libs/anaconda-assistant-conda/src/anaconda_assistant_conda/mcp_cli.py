# Updated standalone_mcp_server.py
import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Set up file logging
log_file = "standalone_mcp_server.log"
def log(message):
    with open(log_file, "a") as f:
        f.write(f"{datetime.now()}: {message}\n")
    print(message)

async def main():
    log("Starting standalone MCP server...")
    
    try:
        # Import MCP
        from mcp.server import FastMCP
        log(f"MCP SDK imported successfully")
        
        # Create the server
        server = FastMCP(
            name="anaconda-assistant",
            description="Anaconda Assistant MCP Server"
        )
        
        # Register a simple tool
        @server.tool("conda-info")
        async def conda_info():
            """Get information about the conda environment."""
            return {
                "conda_version": "23.3.1",
                "python_version": sys.version,
                "platform": sys.platform,
                "timestamp": str(datetime.now())
            }
        
        log("Server created with tools: conda-info")
        log("Starting server on localhost:8080...")
        
        # Try the suggested get_context method or directly configure
        try:
            context = server.get_context()
            context.host = "127.0.0.1"
            context.port = 8080
        except AttributeError:
            # If get_context doesn't exist, try direct configuration
            server.host = "127.0.0.1"
            server.port = 8080
        
        await server.serve()
        
    except Exception as e:
        log(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        tb = traceback.format_exc()
        log(tb)

if __name__ == "__main__":
    log(f"=== MCP Server Test ===")
    log(f"Python version: {sys.version}")
    log(f"Current directory: {os.getcwd()}")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("Server stopped by user")
    except Exception as e:
        log(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        tb = traceback.format_exc()
        log(tb)
