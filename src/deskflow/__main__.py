"""DeskFlow CLI entry point.

Usage:
    python -m deskflow [command]
    deskflow [command]
"""

from __future__ import annotations

import typer

from deskflow.cli.chat import chat_command
from deskflow.cli.config_cmd import config_app
from deskflow.cli.init import init_command
from deskflow.cli.serve import serve_command
from deskflow.cli.status import status_command

app = typer.Typer(
    name="deskflow",
    help="Coolaw DeskFlow - Self-evolving AI Agent Framework",
    no_args_is_help=True,
    add_completion=False,
)

app.command("init")(init_command)
app.command("chat")(chat_command)
app.command("serve")(serve_command)
app.command("status")(status_command)
app.add_typer(config_app, name="config")


def main() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
