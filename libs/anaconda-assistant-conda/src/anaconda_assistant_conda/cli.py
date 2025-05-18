import sys

import typer
from rich.console import Console
from typing_extensions import Annotated

from .debug_config import debug_config
from .config import AssistantCondaConfig
from .core import stream_response

console = Console()

helptext = """
The conda assistant, powered by Anaconda Assistant. \n
See https://anaconda.github.io/assistant-sdk/ for more information.
"""

app = typer.Typer(
    help=helptext,
    add_help_option=True,
    no_args_is_help=True,
    add_completion=False,
)


@app.callback(invoke_without_command=True, no_args_is_help=True)
def _() -> None:
    pass


@app.command(name="configure")
def configure() -> None:
    debug_config()

@app.command("start")
def start(
    command: Annotated[str, typer.Argument(..., help="Command to execute, use 'mcp-server' to start the MCP server")],
    host: Annotated[str, typer.Option("--host", "-h")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", "-p")] = 8000,
    debug: Annotated[bool, typer.Option("--debug", "-d")] = False,
    transport: Annotated[str, typer.Option("--transport", "-t", help="Transport protocol (sse or stdio)")] = "sse",
) -> None:
    """Start a service or command, including the MCP server."""
    try:
        print(f"Command received: {command}")  # Debug print
        if command == "mcp-server":
            # Import the MCP application instance
            print("Importing MCP application...")  # Debug print
            from anaconda_assistant_conda.mcp_server.main import mcp_application
            
            print(f"Starting MCP server on {host}:{port} using {transport} transport")
            
            # Configure FastMCP settings
            print("Configuring MCP settings...")  # Debug print
            mcp_application.settings.host = host
            mcp_application.settings.port = port
            mcp_application.settings.debug = debug
            
            if debug:
                mcp_application.settings.log_level = "DEBUG"
                print(f"Debug mode enabled. MCP log level set to {mcp_application.settings.log_level}")
            
            # Start the MCP server
            print(f"About to run MCP server with transport: {transport}")  # Debug print
            mcp_application.run(transport=transport)
            print("MCP server started (this line may not be reached)")  # Debug print
        else:
            print(f"Unknown command: {command}")
            print("Available commands: mcp-server")
    except Exception as e:
        import traceback
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        traceback.print_exc()  # Print full stack trace
        sys.exit(1)
