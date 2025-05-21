import sys
import traceback
from typing import Any, Generator, List, cast
import pytest
import typer

from anaconda_assistant.config import AssistantConfig
from conda import CondaError, plugins
from conda.cli.conda_argparse import BUILTIN_COMMANDS
from conda.exception_handler import ExceptionHandler
from conda.exceptions import PackagesNotFoundError
from rich.console import Console
from rich.prompt import Confirm

from .cli import app
from .config import AssistantCondaConfig, DebugErrorMode
from .core import stream_response
from .debug_config import debug_config, config_command_styled
from .get_clean_error_report_command import get_clean_error_report_command
from typing import Dict, List, Optional


ENV_COMMANDS = {
    "env_config",
    "env_create",
    "env_export",
    "env_list",
    "env_remove",
    "env_update",
}

BUILD_COMMANDS = {
    "build",
    "convert",
    "debug",
    "develop",
    "index",
    "inspect",
    "metapackage",
    "render",
    "skeleton",
}

ALL_COMMANDS = BUILTIN_COMMANDS.union(ENV_COMMANDS, BUILD_COMMANDS)

console = Console()

ExceptionHandler._orig_print_conda_exception = (  # type: ignore
    ExceptionHandler._print_conda_exception
)


def create_message(
    debug_mode: DebugErrorMode,
    prompt: str,
    is_a_tty: bool = True,
    error: str = "",
) -> None:
    # If we don't have a config option, we ask the user
    if debug_mode == None:
        debug_mode = debug_config()
    if debug_mode == "automatic":
        stream_response(error, prompt, is_a_tty=is_a_tty)
    elif debug_mode == "ask":
        should_debug = Confirm.ask(
            "[bold]Debug with Anaconda Assistant?[/bold]",
        )
        if should_debug:
            stream_response(error, prompt, is_a_tty=is_a_tty)
        else:
            console.print(
                "\nOK, goodbye! 👋\n"
                f"To change default behavior, run {config_command_styled}\n"
            )


def error_handler(command: str) -> None:
    interrupt_message_styled = (
        "\n\n[bold red]Operation canceled by user (Ctrl-C).[/bold red]\n"
    )

    config = AssistantCondaConfig()
    if config.debug_error_mode == "off":
        return

    assistant_config = AssistantConfig()
    if assistant_config.accepted_terms is False:
        return

    def assistant_exception_handler(
        self: ExceptionHandler,
        exc_val: CondaError,
        exc_tb: traceback.TracebackException,
    ) -> None:

        # If conda is in the middle of executing something, and user types ctrl-c, we don't want to try and "fix"
        # the error since it's not really an error, so we just re-throw.
        # This also prevents stack trace from being printed.
        if str(exc_val) == "KeyboardInterrupt":
            console.print(interrupt_message_styled)
            sys.exit(1)

        try:
            self._orig_print_conda_exception(exc_val, exc_tb)  # type: ignore
            if exc_val.return_code == 0:
                return

            report = self.get_error_report(exc_val, exc_tb)
            command = get_clean_error_report_command(report)
            prompt = f"COMMAND:\n{command}\nMESSAGE:\n{report['error']}"
            is_a_tty = sys.stdout.isatty()
            error = config.system_messages.error

            create_message(config.debug_error_mode, prompt, is_a_tty, error)

        # If we're in the conda debug flow, ctrl-c is caught so we don't show stack trace.
        # This also prevents stack trace from being printed.
        except KeyboardInterrupt:
            console.print(interrupt_message_styled)
            sys.exit(1)

    ExceptionHandler._print_conda_exception = assistant_exception_handler  # type: ignore

def conda_plugin(args: List[str]) -> int:
    """
    Entry point for the conda plugin.
    
    This function is called by conda when the plugin is invoked.
    
    Args:
        args: Command line arguments
        
    Returns:
        int: Exit code
    """
    # Check if the command is 'mcp'
    if len(args) > 1 and args[1] == 'mcp':
        # Import the main CLI app which includes the MCP commands
        from .cli import app
        # Pass the arguments to the CLI app
        # We need to keep 'mcp' in the arguments
        return app(args[1:])
    
    # Keep the rest of your existing code unchanged
    if len(args) > 1 and args[1] == "assist":
        # Remove the first argument (which is 'conda')
        args = args[1:]
        
        # If no query is provided, show help
        if len(args) <= 1:
            return app(["assist", "--help"])  # Use app instead of cli_app
        
        # Join the remaining arguments as the query
        query = " ".join(args[1:])
        
        # Import here to avoid circular imports
        from .core import stream_response
        
        # Use the system message from the original code
        system_message = "You are an assistant that helps with conda-related questions."
        
        # Stream the response
        stream_response(system_message=system_message, prompt=query)
        
        return 0
    
    # If the command is not recognized, show help
    return app(["--help"])  # Use app instead of cli_app
    
    # If the command is not recognized, show help
    return cli_app(["--help"])


@plugins.hookimpl
def conda_subcommands() -> Generator[plugins.CondaSubcommand, None, None]:
    yield plugins.CondaSubcommand(
        name="assist",
        summary="Anaconda Assistant integration",
        action=lambda args: app(args=args),
    )


@plugins.hookimpl
def conda_pre_commands() -> Generator[plugins.CondaPreCommand, None, None]:
    yield plugins.CondaPreCommand(
        name="error-handler", action=error_handler, run_for=ALL_COMMANDS
    )
