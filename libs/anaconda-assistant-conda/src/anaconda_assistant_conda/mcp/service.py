"""
MCP (Model Context Protocol) - Service Module

This module provides a unified API for the CLI layer by coordinating operations across modules.
"""
from typing import Dict, List, Optional

from .catalog import MCPCatalog
from .config import MCPConfigurator
from .environment import MCPEnvironmentManager
from .models import ConfiguredServerInfo, InstallationResult, ServerInfo


class MCPService:
    """
    Core service layer for MCP functionality.
    
    This class coordinates operations across modules and provides a unified API
    for the CLI layer.
    """
    
    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize the service with all required modules.
        
        Args:
            base_path: Base path for MCP environments. If None, defaults to ~/.anaconda/mcp
        """
        self.catalog = MCPCatalog()
        self.env_manager = MCPEnvironmentManager(base_path)
        self.configurator = MCPConfigurator()
    
    def list_available_servers(self) -> List[ServerInfo]:
        """
        List all available MCP servers.
        
        Returns:
            List[ServerInfo]: List of available servers
        """
        return self.catalog.list_available_servers()
    
    def get_server_details(self, server_name: str) -> Optional[ServerInfo]:
        """
        Get detailed information about a specific server.
        
        Args:
            server_name: Name of the server to get details for
            
        Returns:
            Optional[ServerInfo]: Server details if found, None otherwise
        """
        return self.catalog.get_server_details(server_name)
    
    def search_servers(self, query: str) -> List[ServerInfo]:
        """
        Search for servers matching the query.
        
        Args:
            query: Search query string
            
        Returns:
            List[ServerInfo]: List of servers matching the query
        """
        return self.catalog.search_servers(query)
    
    def install_server(
        self, 
        server_name: str, 
        client_name: str, 
        workspace_path: Optional[str] = None,
        python_version: str = "3.10"
    ) -> InstallationResult:
        """
        Install and configure an MCP server.
        
        Args:
            server_name: Name of the MCP server
            client_name: Name of the client
            workspace_path: Path to workspace for workspace-specific config
            python_version: Python version to use in the environment
            
        Returns:
            InstallationResult: Result of the installation
        """
        # Check if the server exists in the catalog
        server_info = self.catalog.get_server_details(server_name)
        if not server_info:
            return InstallationResult(
                success=False,
                server_name=server_name,
                error_message=f"Server '{server_name}' not found in catalog"
            )
        
        try:
            # Create a conda environment for the server
            env_path = self.env_manager.create_environment(server_name, python_version)
            
            # In a real implementation, this would install the server and its dependencies
            # using the conda API or subprocess calls to conda
            # For now, we'll just simulate it
            
            # Generate the command to start the server
            command = self._generate_server_command(server_name, env_path)
            
            # Add the server to the client's configuration
            config_success = self.configurator.add_server_to_config(
                server_name=server_name,
                client_type=client_name,
                env_path=env_path,
                command=command,
                workspace_path=workspace_path
            )
            
            if not config_success:
                # Clean up the environment if configuration failed
                self.env_manager.remove_environment(server_name)
                return InstallationResult(
                    success=False,
                    server_name=server_name,
                    error_message="Failed to update client configuration"
                )
            
            # Get the config path for reporting
            config_path = self.configurator._get_config_path(client_name, workspace_path)
            
            return InstallationResult(
                success=True,
                server_name=server_name,
                environment_path=env_path,
                config_path=config_path
            )
            
        except Exception as e:
            # Clean up any partial installation
            self.env_manager.remove_environment(server_name)
            return InstallationResult(
                success=False,
                server_name=server_name,
                error_message=f"Installation failed: {str(e)}"
            )
    
    def update_server(
        self, 
        server_name: str, 
        client_name: str, 
        workspace_path: Optional[str] = None
    ) -> InstallationResult:
        """
        Update an installed MCP server.
        
        Args:
            server_name: Name of the MCP server
            client_name: Name of the client
            workspace_path: Path to workspace for workspace-specific config
            
        Returns:
            InstallationResult: Result of the update
        """
        # Check if the server exists in the catalog
        server_info = self.catalog.get_server_details(server_name)
        if not server_info:
            return InstallationResult(
                success=False,
                server_name=server_name,
                error_message=f"Server '{server_name}' not found in catalog"
            )
        
        # Check if the server is installed
        env_path = self.env_manager.get_environment_path(server_name)
        if not env_path:
            return InstallationResult(
                success=False,
                server_name=server_name,
                error_message=f"Server '{server_name}' is not installed"
            )
        
        try:
            # In a real implementation, this would update the server and its dependencies
            # using the conda API or subprocess calls to conda
            # For now, we'll just simulate it
            
            # Update the environment timestamp
            self.env_manager.update_environment(server_name)
            
            # Generate the command to start the server
            command = self._generate_server_command(server_name, env_path)
            
            # Update the server in the client's configuration
            config_success = self.configurator.add_server_to_config(
                server_name=server_name,
                client_type=client_name,
                env_path=env_path,
                command=command,
                workspace_path=workspace_path
            )
            
            if not config_success:
                return InstallationResult(
                    success=False,
                    server_name=server_name,
                    error_message="Failed to update client configuration"
                )
            
            # Get the config path for reporting
            config_path = self.configurator._get_config_path(client_name, workspace_path)
            
            return InstallationResult(
                success=True,
                server_name=server_name,
                environment_path=env_path,
                config_path=config_path
            )
            
        except Exception as e:
            return InstallationResult(
                success=False,
                server_name=server_name,
                error_message=f"Update failed: {str(e)}"
            )
    
    def uninstall_server(
        self, 
        server_name: str, 
        client_name: str, 
        workspace_path: Optional[str] = None
    ) -> bool:
        """
        Uninstall and remove an MCP server.
        
        Args:
            server_name: Name of the MCP server
            client_name: Name of the client
            workspace_path: Path to workspace for workspace-specific config
            
        Returns:
            bool: True if the server was uninstalled, False otherwise
        """
        # First remove from client config
        config_removed = self.configurator.remove_server_from_config(
            server_name, client_name, workspace_path
        )
        
        # Then remove the environment
        env_removed = self.env_manager.remove_environment(server_name)
        
        return config_removed and env_removed
    
    def list_installed_servers(
        self, 
        client_name: Optional[str] = None, 
        workspace_path: Optional[str] = None
    ) -> Dict[str, List[ConfiguredServerInfo]]:
        """
        List installed servers, optionally filtered by client and workspace.
        
        Args:
            client_name: Name of the client to filter by
            workspace_path: Path to workspace to filter by
            
        Returns:
            Dict[str, List[ConfiguredServerInfo]]: Dictionary mapping client names to lists of configured servers
        """
        result = {}
        
        # If client is specified, only check that client
        if client_name:
            clients = [client_name]
        else:
            # Otherwise check all clients
            clients = [c.value for c in self.configurator.client_config_paths.keys()]
        
        for client in clients:
            servers = self.configurator.list_configured_servers(client, workspace_path)
            if servers:
                result[client] = servers
        
        return result
    
    def verify_installation(self, server_name: str) -> bool:
        """
        Verify that a server is correctly installed and operational.
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            bool: True if the server is correctly installed, False otherwise
        """
        # Check if the server is installed
        env_path = self.env_manager.get_environment_path(server_name)
        if not env_path:
            return False
        
        # In a real implementation, this would check if the server is operational
        # by running a health check or similar
        # For now, we'll just check if the environment exists
        return os.path.exists(env_path)
    
    def _generate_server_command(self, server_name: str, env_path: str) -> str:
        """
        Generate the command to start the server.
        
        Args:
            server_name: Name of the MCP server
            env_path: Path to the conda environment
            
        Returns:
            str: Command to start the server
        """
        # This is a simplified version; in a real implementation, this would
        # generate the appropriate command based on the server type
        if server_name == "condamcp":
            return f"conda run -p {env_path} condamcp"
        else:
            return f"conda run -p {env_path} python -m {server_name.replace('-', '_')}"
