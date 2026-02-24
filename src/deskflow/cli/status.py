"""deskflow status - check system status."""

from __future__ import annotations

import asyncio

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def status_command(
    server: str = typer.Option(
        "http://127.0.0.1:8420", "--server", "-s", help="API server URL"
    ),
) -> None:
    """Check the status of the DeskFlow server and agent."""
    asyncio.run(_check_status(server))


async def _check_status(server_url: str) -> None:
    """Query the server for status information."""
    console.print(f"[dim]Checking {server_url}...[/dim]\n")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Health check
            health_resp = await client.get(f"{server_url}/api/health")
            health = health_resp.json()

            # Status
            status_resp = await client.get(f"{server_url}/api/status")
            status = status_resp.json()

    except httpx.ConnectError:
        console.print(
            Panel(
                "[red]Cannot connect to DeskFlow server.[/red]\n\n"
                f"Server URL: {server_url}\n\n"
                "Make sure the server is running:\n"
                "  [green]deskflow serve[/green]",
                title="Connection Failed",
                border_style="red",
            )
        )
        return
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    # Display health
    health_status = health.get("status", "unknown")
    color = "green" if health_status == "ok" else "yellow" if health_status == "degraded" else "red"

    table = Table(title="Component Health", border_style="dim")
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Details", style="dim")

    for name, comp in health.get("components", {}).items():
        comp_status = comp.get("status", "unknown")
        comp_color = "green" if comp_status == "ok" else "red"
        details = ", ".join(f"{k}={v}" for k, v in comp.get("details", {}).items())
        table.add_row(name, f"[{comp_color}]{comp_status}[/{comp_color}]", details)

    console.print(
        Panel(
            f"[{color}]Overall: {health_status.upper()}[/{color}]  |  "
            f"Version: {health.get('version', '?')}",
            title="DeskFlow Health",
            border_style=color,
        )
    )
    console.print(table)

    # Display agent status
    console.print()

    agent_table = Table(title="Agent Status", border_style="dim")
    agent_table.add_column("Metric", style="bold")
    agent_table.add_column("Value")

    online = status.get("is_online", False)
    busy = status.get("is_busy", False)
    state_str = "[green]Online[/green]" if online else "[red]Offline[/red]"
    if busy:
        state_str += f" [yellow](Busy: {status.get('current_task', '?')})[/yellow]"

    agent_table.add_row("State", state_str)
    agent_table.add_row("LLM", f"{status.get('llm_provider', '?')} / {status.get('llm_model', '?')}")
    agent_table.add_row("Uptime", f"{status.get('uptime_seconds', 0):.0f}s")
    agent_table.add_row("Conversations", str(status.get("total_conversations", 0)))
    agent_table.add_row("Tool Calls", str(status.get("total_tool_calls", 0)))
    agent_table.add_row("Tokens Used", f"{status.get('total_tokens_used', 0):,}")
    agent_table.add_row("Memories", f"{status.get('memory_count', 0):,}")
    agent_table.add_row("Tools", f"{status.get('active_tools', 0)} / {status.get('available_tools', 0)}")

    console.print(agent_table)
