"""
MCP CLI module - Direct entry point for MCP commands.
"""
from typing import List
from ..cli import mcp_app

def conda_plugin(args: List[str]) -> int:
    """
    Entry point for MCP commands.
    
    Args:
        args: Command line arguments
        
    Returns:
        int: Exit code
    """
    # Remove the first argument (which is 'conda')
    if len(args) > 1:
        # Pass the remaining arguments to the MCP app
        return mcp_app(args[1:])
    else:
        # If no arguments, show help
        return mcp_app(["--help"])
