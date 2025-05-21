import sys
from typing import List, Optional

import typer
from rich.console import Console
from typing_extensions import Annotated

from .debug_config import debug_config
from .config import AssistantCondaConfig
from .core import stream_response, CondaAssistant
from .mcp.models import ClientType
from .mcp.service import MCPService

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

# Create MCP subcommand group
mcp_app = typer.Typer(
    help="Model Context Protocol (MCP) server management",
    add_help_option=True,
    no_args_is_help=True,
)

# Add MCP subcommand group to main app
app.add_typer(mcp_app, name="mcp")

# Initialize MCP service
mcp_service = MCPService()


@app.callback(invoke_without_command=True, no_args_is_help=True)
def _() -> None:
    pass


@app.command(name="configure")
def configure() -> None:
    debug_config()


@app.command(name="assist")
def assist(
    query: List[str] = typer.Argument(None, help="Natural language query"),
    action_mode: bool = typer.Option(False, "--action", "-a", help="Force action mode"),
    search_mode: bool = typer.Option(False, "--search", "-s", help="Force search mode"),
):
    """
    Process a natural language query with the Anaconda CLI Assistant.
    
    If the query implies an action, it will be routed to the condamcp MCP server.
    Otherwise, it will be processed as a search query.
    """
    # Join the query parts into a single string
    query_str = " ".join(query) if query else ""
    
    if not query_str:
        console.print("[yellow]Please provide a query.[/yellow]")
        return
    
    # Create the assistant
    assistant = CondaAssistant()
    
    # Override the action detection if specified
    if hasattr(assistant, 'action_mode'):
        if action_mode:
            assistant.action_mode = True
        elif search_mode:
            assistant.action_mode = False
    
    # Process the query
    result = assistant.process_query(query_str)
    
    # Print the result
    console.print(result)


# MCP Manager CLI commands
@mcp_app.command("list")
def list_servers():
    """List all available MCP servers."""
    servers = mcp_service.list_available_servers()
    
    if not servers:
        console.print("[yellow]No MCP servers available in the catalog.[/yellow]")
        return
    
    from rich.table import Table
    
    table = Table(title="Available MCP Servers")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Description")
    
    for server in servers:
        table.add_row(server.name, server.version, server.description)
    
    console.print(table)


@mcp_app.command("info")
def server_info(server_name: str):
    """Show details about a specific server."""
    server = mcp_service.get_server_details(server_name)
    
    if not server:
        console.print(f"[red]Server '{server_name}' not found in catalog.[/red]")
        return
    
    console.print(f"[bold cyan]Server:[/bold cyan] {server.name}")
    console.print(f"[bold cyan]Version:[/bold cyan] {server.version}")
    console.print(f"[bold cyan]Description:[/bold cyan] {server.description}")
    
    if server.dependencies:
        console.print("[bold cyan]Dependencies:[/bold cyan]")
        for dep in server.dependencies:
            console.print(f"  - {dep}")
    
    if server.homepage:
        console.print(f"[bold cyan]Homepage:[/bold cyan] {server.homepage}")
    
    if server.repository:
        console.print(f"[bold cyan]Repository:[/bold cyan] {server.repository}")
    
    if server.author:
        console.print(f"[bold cyan]Author:[/bold cyan] {server.author}")
    
    if server.license:
        console.print(f"[bold cyan]License:[/bold cyan] {server.license}")


@mcp_app.command("install")
def install_server(
    server_name: str,
    client: str = typer.Option(..., "--client", "-c", help="Client type (claude-desktop, cursor, vscode, custom)"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="Workspace path for workspace-specific config"),
    python_version: str = typer.Option("3.10", "--python", "-p", help="Python version to use in the environment"),
):
    """Install a server (globally or in workspace)."""
    try:
        client_type = ClientType(client)
    except ValueError:
        console.print(f"[red]Invalid client type: {client}[/red]")
        console.print("Valid client types: claude-desktop, cursor, vscode, custom")
        return
    
    # Resolve workspace path if provided
    if workspace:
        workspace = os.path.abspath(workspace)
    
    console.print(f"Installing [cyan]{server_name}[/cyan] for [green]{client}[/green]...")
    
    result = mcp_service.install_server(server_name, client_type, workspace, python_version)
    
    if result.success:
        console.print(f"[green]Successfully installed {server_name}![/green]")
        console.print(f"Environment path: {result.environment_path}")
        console.print(f"Configuration updated: {result.config_path}")
    else:
        console.print(f"[red]Installation failed: {result.error_message}[/red]")


@mcp_app.command("update")
def update_server(
    server_name: str,
    client: str = typer.Option(..., "--client", "-c", help="Client type (claude-desktop, cursor, vscode, custom)"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="Workspace path for workspace-specific config"),
):
    """Update an installed server."""
    try:
        client_type = ClientType(client)
    except ValueError:
        console.print(f"[red]Invalid client type: {client}[/red]")
        console.print("Valid client types: claude-desktop, cursor, vscode, custom")
        return
    
    # Resolve workspace path if provided
    if workspace:
        workspace = os.path.abspath(workspace)
    
    console.print(f"Updating [cyan]{server_name}[/cyan] for [green]{client}[/green]...")
    
    result = mcp_service.update_server(server_name, client_type, workspace)
    
    if result.success:
        console.print(f"[green]Successfully updated {server_name}![/green]")
        console.print(f"Environment path: {result.environment_path}")
        console.print(f"Configuration updated: {result.config_path}")
    else:
        console.print(f"[red]Update failed: {result.error_message}[/red]")


@mcp_app.command("uninstall")
def uninstall_server(
    server_name: str,
    client: str = typer.Option(..., "--client", "-c", help="Client type (claude-desktop, cursor, vscode, custom)"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="Workspace path for workspace-specific config"),
):
    """Uninstall a server."""
    try:
        client_type = ClientType(client)
    except ValueError:
        console.print(f"[red]Invalid client type: {client}[/red]")
        console.print("Valid client types: claude-desktop, cursor, vscode, custom")
        return
    
    # Resolve workspace path if provided
    if workspace:
        workspace = os.path.abspath(workspace)
    
    console.print(f"Uninstalling [cyan]{server_name}[/cyan] from [green]{client}[/green]...")
    
    success = mcp_service.uninstall_server(server_name, client_type, workspace)
    
    if success:
        console.print(f"[green]Successfully uninstalled {server_name}![/green]")
    else:
        console.print(f"[red]Uninstallation failed. Server may not be installed or configuration could not be updated.[/red]")


@mcp_app.command("installed")
def list_installed(
    client: Optional[str] = typer.Option(None, "--client", "-c", help="Client type (claude-desktop, cursor, vscode, custom)"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="Workspace path for workspace-specific config"),
):
    """List installed servers."""
    client_type = None
    if client:
        try:
            client_type = ClientType(client)
        except ValueError:
            console.print(f"[red]Invalid client type: {client}[/red]")
            console.print("Valid client types: claude-desktop, cursor, vscode, custom")
            return
    
    # Resolve workspace path if provided
    if workspace:
        workspace = os.path.abspath(workspace)
    
    installed_servers = mcp_service.list_installed_servers(client_type, workspace)
    
    if not installed_servers:
        console.print("[yellow]No installed MCP servers found.[/yellow]")
        return
    
    from rich.table import Table
    
    for client_name, servers in installed_servers.items():
        table = Table(title=f"Installed MCP Servers for {client_name}")
        table.add_column("Name", style="cyan")
        table.add_column("Environment Path", style="green")
        table.add_column("Command")
        table.add_column("Workspace", style="yellow")
        
        for server in servers:
            table.add_row(
                server.name,
                server.environment_path,
                server.command,
                server.workspace_path or "Global"
            )
        
        console.print(table)


if __name__ == "__main__":
    app()
