"""deskflow chat - interactive conversation with the agent."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()


def _run_chat(conversation_id: str | None) -> None:
    """Run the interactive chat loop."""
    try:
        asyncio.run(_async_chat(conversation_id))
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye![/dim]")


async def _async_chat(conversation_id: str | None) -> None:
    """Async chat loop."""
    from deskflow.config import load_config
    from deskflow.core.agent import Agent
    from deskflow.core.identity import DefaultIdentity
    from deskflow.core.task_monitor import TaskMonitor
    from deskflow.llm.client import LLMClient, create_adapter
    from deskflow.memory.manager import MemoryManager
    from deskflow.observability.logging import setup_logging
    from deskflow.tools.builtin.file import FileTool
    from deskflow.tools.builtin.shell import ShellTool
    from deskflow.tools.builtin.web import WebTool
    from deskflow.tools.registry import ToolRegistry

    config = load_config()
    setup_logging(log_level="WARNING")  # Quiet logs in chat mode

    console.print(
        Panel.fit(
            "[bold green]DeskFlow Chat[/bold green]\n"
            "[dim]Type your message and press Enter. Ctrl+C to quit.[/dim]",
            border_style="green",
        )
    )

    # Initialize components
    memory = MemoryManager(
        db_path=config.get_db_path(),
        cache_capacity=config.memory.memory_cache_size,
    )
    await memory.initialize()

    tools = ToolRegistry(default_timeout=config.tools.tool_timeout)
    await tools.register(ShellTool())
    await tools.register(FileTool(allowed_paths=config.tools.get_allowed_paths()))
    await tools.register(WebTool())

    try:
        primary = create_adapter(config)
    except ValueError as e:
        console.print(f"[red]LLM Error: {e}[/red]")
        console.print("[dim]Run 'deskflow init' to configure your API key.[/dim]")
        await memory.close()
        return

    llm_client = LLMClient(primary=primary)

    identity = DefaultIdentity(identity_dir=config.get_project_root() / "identity")
    monitor = TaskMonitor()

    agent = Agent(
        brain=llm_client,
        memory=memory,
        tools=tools,
        identity=identity,
        monitor=monitor,
    )

    console.print(f"\n[dim]Provider: {primary.provider_name} | Model: {primary.model_name}[/dim]")
    console.print(f"[dim]{identity.get_greeting()}[/dim]\n")

    conv_id = conversation_id

    try:
        while True:
            try:
                user_input = console.input("[bold green]> [/bold green]")
            except EOFError:
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "/q"):
                break

            if user_input.lower() == "/status":
                mem_count = await memory.count()
                status = monitor.get_status(
                    memory_count=mem_count,
                    available_tools=tools.count,
                    llm_provider=primary.provider_name,
                    llm_model=primary.model_name,
                )
                console.print(Panel(
                    f"Conversations: {status.total_conversations}\n"
                    f"Tool calls: {status.total_tool_calls}\n"
                    f"Tokens used: {status.total_tokens_used}\n"
                    f"Memories: {status.memory_count}\n"
                    f"Uptime: {status.uptime_seconds:.0f}s",
                    title="Status",
                    border_style="blue",
                ))
                continue

            if user_input.lower() == "/help":
                console.print(Panel(
                    "/status  - Show agent status\n"
                    "/help    - Show this help\n"
                    "/q       - Quit",
                    title="Commands",
                    border_style="blue",
                ))
                continue

            # Stream response
            console.print()
            full_text = ""
            try:
                async for chunk in agent.stream_chat(
                    user_message=user_input,
                    conversation_id=conv_id,
                ):
                    if chunk.type == "text":
                        full_text += chunk.content
                        console.print(chunk.content, end="", highlight=False)
                    elif chunk.type == "tool_start" and chunk.tool_call:
                        console.print(
                            f"\n[dim][running: {chunk.tool_call.name}...][/dim]",
                            end="",
                        )
                    elif chunk.type == "tool_end" and chunk.tool_call:
                        console.print(" [green]done[/green]")
                    elif chunk.type == "error":
                        console.print(f"\n[red]Error: {chunk.content}[/red]")
                    elif chunk.type == "done":
                        pass

                console.print("\n")

            except Exception as e:
                console.print(f"\n[red]Error: {e}[/red]\n")

    finally:
        await memory.close()


def chat_command(
    conversation_id: str | None = typer.Option(
        None, "--conversation", "-c", help="Resume a conversation by ID"
    ),
) -> None:
    """Start an interactive chat session with DeskFlow Agent."""
    _run_chat(conversation_id)
