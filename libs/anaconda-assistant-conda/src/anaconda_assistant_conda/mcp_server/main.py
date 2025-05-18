from mcp.server.fastmcp import FastMCP

# Create the FastMCP application instance
# This instance will be imported by the CLI extension to run the server.
mcp_application = FastMCP(
    name="my-custom-mcp-server",
    description="A custom MCP server integrated into the project.",
    version="0.1.0",
)

@mcp_application.tool()
async def echo_tool(message: str) -> str:
    """A simple tool that echoes back the received message."""
    return f"MCP Server echoes: {message}"

# Add more tools here as needed by the project
# For example:
# @mcp_application.tool()
# async def get_project_data(item_id: str) -> dict:
#     """Fetches some data relevant to the project."""
#     # Your logic here
#     return {"id": item_id, "data": "some project specific data"}

# If you wanted to run this server directly using `python -m anaconda_assistant_conda.mcp_server.main`
# you could add:
# if __name__ == "__main__":
#     from mcp.server import run_server
#     print("Starting MCP server directly via main.py...")
#     run_server(mcp_application, host="127.0.0.1", port=8000) # Default host/port for direct run

