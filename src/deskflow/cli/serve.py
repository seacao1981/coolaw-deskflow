"""deskflow serve - start the API server."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def serve_command(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind host"),
    port: int = typer.Option(8420, "--port", "-p", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload (dev)"),
    log_level: str = typer.Option("info", "--log-level", "-l", help="Log level"),
) -> None:
    """Start the DeskFlow API server."""
    import uvicorn

    console.print(
        f"[bold green]Starting DeskFlow API server[/bold green]\n"
        f"  Host: [cyan]{host}[/cyan]\n"
        f"  Port: [cyan]{port}[/cyan]\n"
        f"  Reload: [cyan]{reload}[/cyan]\n"
        f"  Log level: [cyan]{log_level}[/cyan]\n"
    )
    console.print(f"  API docs: [link]http://{host}:{port}/docs[/link]")
    console.print(f"  Health:   [link]http://{host}:{port}/api/health[/link]")
    console.print()

    uvicorn.run(
        "deskflow.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        log_level=log_level.lower(),
    )
