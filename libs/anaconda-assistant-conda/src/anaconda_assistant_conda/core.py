from shutil import copy
from textwrap import dedent
from typing import cast
from typing import Any
from typing import Dict
from typing import Callable
from typing import Generator
from typing import Type
from typing import Optional
from unittest.mock import patch
import os
import subprocess
import time

import tomli
import tomli_w
from anaconda_cli_base.config import anaconda_config_path
from anaconda_cli_base.exceptions import register_error_handler
from anaconda_cli_base.exceptions import ERROR_HANDLERS
from anaconda_assistant import ChatSession
from anaconda_assistant.exceptions import (
    UnspecifiedAcceptedTermsError,
    UnspecifiedDataCollectionChoice,
)
from rich.console import Console, Group
from rich.live import Live
from rich.prompt import Confirm
from .rich_customizations.md import MyMarkdown
from .mcp.models import ActionPlan
from .mcp.executor import MCPExecutor
from .mcp.feedback import MCPFeedback


def set_config(table: str, key: str, value: Any) -> None:
    expanded = table.split(".")

    # save a backup of the config.toml just to be safe
    config_toml = anaconda_config_path()
    if config_toml.exists():
        copy(config_toml, config_toml.with_suffix(".backup.toml"))
        with open(config_toml, "rb") as f:
            config = tomli.load(f)
    else:
        config = {}

    # Add table if it doesn't exist
    config_table = config
    for table_key in expanded:
        if table_key not in config_table:
            config_table[table_key] = {}
        config_table = config_table[table_key]

    # config_table is still referenced in the config dict
    # we can edit the value here and then write the whole dict back
    config_table[key] = value

    config_toml.parent.mkdir(parents=True, exist_ok=True)
    with open(config_toml, "wb") as f:
        tomli_w.dump(config, f)


@register_error_handler(UnspecifiedDataCollectionChoice)
def data_collection_choice(e: Type[UnspecifiedDataCollectionChoice]) -> int:
    import anaconda_auth.cli

    if not anaconda_auth.cli.sys.stdout.isatty():  # type: ignore
        print(e.args[0])
        return 1

    msg = dedent(
        """\
        You have not chosen to opt-in or opt-out of data collection.
        This does not affect the operation of Anaconda Assistant, but your choice is required to proceed.

        If you opt-in you will enjoy personalized recommendations and contribute to smarter features.
        We prioritize your privacy:

          * Your data is never sold
          * Always secured
          * This setting only affects the data Anaconda stores
          * It does not affect the data that is sent to Open AI

        [bold green]Would you like to opt-in to data collection?[/bold green]
        """
    )
    data_collection = Confirm.ask(msg)
    set_config("plugin.assistant", "data_collection", data_collection)

    return -1


@register_error_handler(UnspecifiedAcceptedTermsError)
def accept_terms(e: Type[UnspecifiedAcceptedTermsError]) -> int:
    import anaconda_auth.cli

    if not anaconda_auth.cli.sys.stdout.isatty():  # type: ignore
        print(e.args[0])
        return 1

    msg = dedent(
        """\
        You have not accepted the terms of service.
        You must accept our terms of service and Privacy Policy here

          https://anaconda.com/legal

        [bold green]Are you more than 13 years old and accept the terms?[/bold green]
        """
    )
    accepted_terms = Confirm.ask(msg)
    set_config("plugin.assistant", "accepted_terms", accepted_terms)

    if not accepted_terms:
        return 1
    else:
        return -1


def try_except_repeat(
    func: Callable, max_depth: int = 5, *args: Any, **kwargs: Any
) -> Any:
    if max_depth == 0:
        raise RuntimeError("try/except recursion exceeded")
    try:
        yield from func(*args, **kwargs)
    except Exception as e:
        callback = ERROR_HANDLERS[type(e)]
        exit_code = callback(e)
        if exit_code == -1:
            yield from try_except_repeat(
                func=func,
                max_depth=max_depth - 1,
                *args,
                **kwargs,  # type: ignore
            )
        else:
            return


def stream_response(
    system_message: str,
    prompt: str,
    is_a_tty: bool = True,
    console: Optional[Console] = None,
) -> None:
    if console is None:
        console = Console()

    full_text = ""
    with Live(
        MyMarkdown(full_text),
        vertical_overflow="visible",
        console=console,
        auto_refresh=False,
    ) as live:
        with patch("anaconda_auth.cli.sys") as mocked:
            mocked.stdout.isatty.return_value = is_a_tty

            def chat() -> Generator[str, None, None]:
                session = ChatSession(system_message=system_message)
                response = session.chat(message=prompt, stream=True)
                yield from response

            response = cast(
                Generator[str, None, None], try_except_repeat(chat, max_depth=5)
            )

            for chunk in response:
                full_text += chunk
                try:
                    md = MyMarkdown(full_text, hyperlinks=False)
                except Exception:
                    continue
                live.update(md, refresh=True)


class CondaAssistant:
    """
    Enhanced Conda Assistant with MCP integration.
    
    This class extends the base assistant functionality to detect when a user's query
    implies an action rather than just a search, and routes those queries to
    the condamcp MCP server.
    """
    
    def __init__(self):
        """Initialize the MCP-aware assistant."""
        self.condamcp_env_name = "condamcp"
        self.condamcp_process = None
        self.action_mode = False
        self.executor = MCPExecutor()
        self.feedback = MCPFeedback()
    
    def process_query(self, query: str) -> str:
        """
        Process a user query, detecting if it implies an action.
        
        Args:
            query: User's natural language query
            
        Returns:
            str: Response to the user
        """
        # Detect if the query implies an action
        if self._is_action_query(query):
            self.action_mode = True
            return self._handle_action_query(query)
        else:
            self.action_mode = False
            # Use the standard search-based assistant for informational queries
            return self._handle_search_query(query)
    
    def _is_action_query(self, query: str) -> bool:
        """
        Determine if a query implies an action rather than just a search.
        
        Args:
            query: User's natural language query
            
        Returns:
            bool: True if the query implies an action, False otherwise
        """
        # Simple keyword-based detection for now
        action_keywords = [
            "create", "make", "build", "setup", "install", "update", 
            "remove", "delete", "clean", "activate", "deactivate",
            "can you", "please", "help me", "I need", "I want"
        ]
        
        # Check for action keywords
        query_lower = query.lower()
        for keyword in action_keywords:
            if keyword in query_lower:
                return True
        
        return False
    
    def _handle_action_query(self, query: str) -> str:
        """
        Handle an action query by routing it to the condamcp MCP server.
        
        Args:
            query: User's natural language query
            
        Returns:
            str: Response to the user
        """
        # Ensure the condamcp server is running
        if not self._ensure_condamcp_server():
            return "I couldn't start the condamcp server. Please make sure it's installed."
        
        # Send the query to the condamcp server and get the proposed action
        action_plan = self._get_action_plan(query)
        
        # Present the action plan to the user for confirmation
        confirmation = self.feedback.present_action_plan(action_plan)
        
        if confirmation:
            # Execute the action
            result = self.executor.execute_action(action_plan)
            self.feedback.display_result(result)
            return self._format_result(result)
        else:
            return "Action cancelled. Is there something else I can help you with?"
    
    def _handle_search_query(self, query: str) -> str:
        """
        Handle a search query using the standard assistant.
        
        Args:
            query: User's natural language query
            
        Returns:
            str: Response to the user
        """
        # This is a simplified version; in a real implementation, this would
        # use the existing search functionality
        system_message = "You are an assistant that helps with conda-related questions."
        console = Console(width=80)
        
        # Capture the output in a string
        from io import StringIO
        import sys
        
        original_stdout = sys.stdout
        string_io = StringIO()
        sys.stdout = string_io
        
        try:
            stream_response(system_message, query, console=console)
            return string_io.getvalue()
        finally:
            sys.stdout = original_stdout
    
    def _ensure_condamcp_server(self) -> bool:
        """
        Ensure the condamcp server is running.
        
        Returns:
            bool: True if the server is running, False otherwise
        """
        # Check if the condamcp environment exists
        if not self._check_condamcp_env():
            # Create the environment if it doesn't exist
            if not self._create_condamcp_env():
                return False
        
        # Start the server if it's not already running
        if not self.condamcp_process or self.condamcp_process.poll() is not None:
            return self._start_condamcp_server()
        
        return True
    
    def _check_condamcp_env(self) -> bool:
        """
        Check if the condamcp environment exists.
        
        Returns:
            bool: True if the environment exists, False otherwise
        """
        # In a real implementation, this would use the conda API to check
        # if the environment exists. For now, we'll simulate it.
        return os.path.exists(os.path.expanduser(f"~/.conda/envs/{self.condamcp_env_name}"))
    
    def _create_condamcp_env(self) -> bool:
        """
        Create the condamcp environment.
        
        Returns:
            bool: True if the environment was created, False otherwise
        """
        # In a real implementation, this would use the conda API to create
        # the environment and install condamcp. For now, we'll simulate it.
        try:
            # Create the environment directory
            os.makedirs(os.path.expanduser(f"~/.conda/envs/{self.condamcp_env_name}/conda-meta"), exist_ok=True)
            return True
        except Exception as e:
            print(f"Error creating condamcp environment: {e}")
            return False
    
    def _start_condamcp_server(self) -> bool:
        """
        Start the condamcp server.
        
        Returns:
            bool: True if the server was started, False otherwise
        """
        # In a real implementation, this would use subprocess to start the
        # condamcp server in the condamcp environment. For now, we'll simulate it.
        try:
            # Simulate starting the server
            self.condamcp_process = subprocess.Popen(
                ["echo", "Simulated condamcp server"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return True
        except Exception as e:
            print(f"Error starting condamcp server: {e}")
            return False
    
    def _get_action_plan(self, query: str) -> ActionPlan:
        """
        Get the proposed action plan from the condamcp server.
        
        Args:
            query: User's natural language query
            
        Returns:
            ActionPlan: Action plan with details about the proposed action
        """
        # In a real implementation, this would send the query to the condamcp
        # server and parse the response. For now, we'll simulate it.
        
        # Simulate different action plans based on the query
        if "create" in query.lower() or "new" in query.lower():
            return ActionPlan(
                action="create_environment",
                name="py310_data",
                python_version="3.10",
                packages=["numpy", "pandas"],
                description="Create a new environment named 'py310_data' with Python 3.10, numpy, and pandas"
            )
        elif "install" in query.lower():
            return ActionPlan(
                action="install_packages",
                environment="base",
                packages=["matplotlib", "seaborn"],
                description="Install matplotlib and seaborn packages in the base environment"
            )
        elif "update" in query.lower():
            return ActionPlan(
                action="update_packages",
                environment="base",
                exclude=["cuda-toolkit", "cudnn"],
                description="Update all packages in the base environment, excluding CUDA-related packages"
            )
        elif "remove" in query.lower() or "delete" in query.lower():
            return ActionPlan(
                action="remove_environment",
                name="experiment",
                description="Remove the 'experiment' environment"
            )
        else:
            return ActionPlan(
                action="unknown",
                description="I'm not sure what action you want to perform. Could you please be more specific?"
            )
    
    def _format_result(self, result: Dict) -> str:
        """
        Format the action execution result for presentation to the user.
        
        Args:
            result: Result of the action execution
            
        Returns:
            str: Formatted result message
        """
        if result["success"]:
            return f"✅ {result['message']}"
        else:
            return f"❌ {result['message']}"
