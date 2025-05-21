# /libs/anaconda-assistant-sdk/src/anaconda_assistant/integrations/mcp/__init__.py
"""
Model Context Protocol (MCP) client implementation for Anaconda Assistant.

This module provides functionality for connecting to and interacting with MCP servers.
"""

from .client import MCPClient
from .auth import MCPAuth
from .error import MCPError, MCPConnectionError, MCPResponseError

__all__ = ["MCPClient", "MCPAuth", "MCPError", "MCPConnectionError", "MCPResponseError"]