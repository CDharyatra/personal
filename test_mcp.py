from mcp.server import FastMCP

app = FastMCP(
    name="test-mcp-server",
    description="Test MCP Server",
    version="0.1.0",
)

@app.tool()
async def echo(message: str) -> str:
    """Echo the message back."""
    return f"Echo: {message}"

if __name__ == "__main__":
    print("Starting test MCP server...")
    app.run(transport="stdio")
