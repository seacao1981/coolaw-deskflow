"""deskflow config - manage configuration."""

from __future__ import annotations

import asyncio

import httpx
import typer
from rich.console import Console
from rich.table import Table

console = Console()

config_app = typer.Typer(help="Manage DeskFlow configuration")


@config_app.command("show")
def config_show(
    server: str = typer.Option(
        "http://127.0.0.1:8420", "--server", "-s", help="API server URL"
    ),
) -> None:
    """Show current configuration (redacted)."""
    asyncio.run(_show_config(server))


async def _show_config(server_url: str) -> None:
    """Fetch and display config from server."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{server_url}/api/config")
            config = resp.json()
    except httpx.ConnectError:
        console.print("[red]Cannot connect to server. Is it running?[/red]")
        return
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    table = Table(title="DeskFlow Configuration", border_style="dim")
    table.add_column("Key", style="bold")
    table.add_column("Value")

    table.add_row("LLM Provider", config.get("llm_provider", "?"))
    table.add_row("LLM Model", config.get("llm_model", "?"))
    table.add_row("Temperature", str(config.get("llm_temperature", "?")))
    table.add_row("Max Tokens", str(config.get("llm_max_tokens", "?")))
    has_key = config.get("has_api_key", False)
    key_status = "[green]configured[/green]" if has_key else "[red]not set[/red]"
    table.add_row("API Key", key_status)
    table.add_row("Server", f"{config.get('server_host', '?')}:{config.get('server_port', '?')}")
    table.add_row("Cache Size", str(config.get("memory_cache_size", "?")))
    table.add_row("Tool Timeout", f"{config.get('tool_timeout', '?')}s")

    console.print(table)


@config_app.command("list")
def config_list() -> None:
    """List all environment variables for DeskFlow."""
    import os

    table = Table(title="DeskFlow Environment Variables", border_style="dim")
    table.add_column("Variable", style="bold")
    table.add_column("Value")

    prefix = "DESKFLOW_"
    found = False
    for key, value in sorted(os.environ.items()):
        if key.startswith(prefix):
            found = True
            # Redact sensitive values
            if "KEY" in key or "SECRET" in key or "TOKEN" in key:
                display_value = value[:4] + "..." + value[-4:] if len(value) > 8 else "****"
            else:
                display_value = value
            table.add_row(key, display_value)

    if found:
        console.print(table)
    else:
        console.print("[dim]No DESKFLOW_ environment variables found.[/dim]")
        console.print("[dim]Run 'deskflow init' or create a .env file.[/dim]")
