"""MCP (Model Context Protocol) tool integration module.

This module provides MCP client functionality to discover and invoke
remote MCP servers, enabling access to external tools and resources.

Features:
- MCP server connection (stdio and HTTP transports)
- Tool discovery from MCP servers
- Remote tool invocation with error handling
- Server lifecycle management
- Multiple server support
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from deskflow.observability.logging import get_logger
from deskflow.tools.base import BaseTool
from deskflow.core.models import ToolResult

if TYPE_CHECKING:
    from mcp import ClientSession  # noqa: F401

logger = get_logger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server connection.

    Attributes:
        name: Unique identifier for this server
        transport: Transport type ('stdio' or 'http')
        command: Command to run (for stdio transport)
        args: Command arguments (for stdio transport)
        url: Server URL (for HTTP transport)
        env: Environment variables for the server
        timeout: Connection timeout in seconds
        auto_connect: Whether to auto-connect on registry start
    """

    name: str
    transport: str = "stdio"
    command: str = ""
    args: list[str] = field(default_factory=list)
    url: str = ""
    env: dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    auto_connect: bool = True


@dataclass
class MCPToolDefinition:
    """Definition of an MCP tool.

    Attributes:
        name: Tool name
        description: Tool description
        input_schema: JSON schema for input parameters
        server_name: Name of the server providing this tool
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str


def _get_mcp_stdio_client():
    """Lazy import of MCP stdio client.

    Returns:
        Tuple of (stdio_client, ClientSession, StdioServerParameters, types)
    """
    try:
        from mcp import ClientSession, StdioServerParameters, types
        from mcp.client.stdio import stdio_client
        return stdio_client, ClientSession, StdioServerParameters, types
    except ImportError as e:
        raise ImportError(
            "MCP SDK not installed. Install with: pip install mcp"
        ) from e


def _get_mcp_http_client():
    """Lazy import of MCP HTTP client.

    Returns:
        Tuple of (streamable_http_client, ClientSession, types)
    """
    try:
        from mcp import ClientSession, types
        from mcp.client.streamable_http import streamable_http_client
        return streamable_http_client, ClientSession, types
    except ImportError as e:
        raise ImportError(
            "MCP SDK not installed. Install with: pip install mcp"
        ) from e


class MCPClient:
    """MCP client for a single server connection.

    Wraps the MCP Python SDK client session and provides methods
    for tool discovery and invocation.
    """

    def __init__(self, config: MCPServerConfig) -> None:
        """Initialize MCP client.

        Args:
            config: Server configuration
        """
        self._config = config
        self._session: Any | None = None
        self._connected = False
        self._tools: dict[str, MCPToolDefinition] = {}
        self._streams: tuple[Any, Any] | None = None

    @property
    def name(self) -> str:
        """Get the server name."""
        return self._config.name

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected

    async def connect(self) -> None:
        """Connect to the MCP server.

        Raises:
            ConnectionError: If connection fails
            ValueError: If configuration is invalid
            ImportError: If MCP SDK not installed
        """
        if self._connected:
            logger.warning("mcp_already_connected", server=self._config.name)
            return

        if self._config.transport == "stdio":
            await self._connect_stdio()
        elif self._config.transport == "http":
            await self._connect_http()
        else:
            raise ValueError(f"Unknown transport: {self._config.transport}")

        # Discover tools
        await self._discover_tools()

        logger.info("mcp_connected", server=self._config.name, tool_count=len(self._tools))

    async def _connect_stdio(self) -> None:
        """Connect using stdio transport."""
        if not self._config.command:
            raise ValueError("Command is required for stdio transport")

        stdio_client, ClientSession, StdioServerParameters, types = _get_mcp_stdio_client()

        server_params = StdioServerParameters(
            command=self._config.command,
            args=self._config.args,
            env={**self._config.env} if self._config.env else None,
        )

        try:
            # Create and enter context manager
            self._streams = await stdio_client(server_params).__aenter__()
            read_stream, write_stream = self._streams

            # Create session
            self._session = ClientSession(read_stream, write_stream)
            await self._session.__aenter__()

            # Initialize
            await self._session.initialize()
            self._connected = True

        except ImportError:
            raise
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to MCP server '{self._config.name}': {e}"
            ) from e

    async def _connect_http(self) -> None:
        """Connect using HTTP transport."""
        if not self._config.url:
            raise ValueError("URL is required for HTTP transport")

        streamable_http_client, ClientSession, types = _get_mcp_http_client()

        try:
            # Create HTTP client streams
            streams_ctx = streamable_http_client(self._config.url)
            self._streams = await streams_ctx.__aenter__()
            read_stream, write_stream, _ = self._streams

            # Create session
            self._session = ClientSession(read_stream, write_stream)
            await self._session.__aenter__()

            # Initialize
            await self._session.initialize()
            self._connected = True

        except ImportError:
            raise
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to MCP server '{self._config.name}': {e}"
            ) from e

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if not self._connected:
            return

        try:
            if self._session:
                await self._session.__aexit__(None, None, None)

            if self._streams:
                # streams is a tuple of (read, write) or (read, write, _)
                # We need to exit the context manager
                pass  # Streams are cleaned up with session

        except Exception as e:
            logger.error("mcp_disconnect_error", server=self._config.name, error=str(e))
        finally:
            self._session = None
            self._streams = None
            self._connected = False
            self._tools = {}

        logger.info("mcp_disconnected", server=self._config.name)

    async def _discover_tools(self) -> None:
        """Discover available tools from the server."""
        if not self._connected or not self._session:
            return

        try:
            response = await self._session.list_tools()
            self._tools = {}

            for tool in response.tools:
                self._tools[tool.name] = MCPToolDefinition(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=tool.inputSchema or {},
                    server_name=self._config.name,
                )

            logger.debug(
                "mcp_tools_discovered",
                server=self._config.name,
                tool_count=len(self._tools),
            )

        except Exception as e:
            logger.error(
                "mcp_tool_discovery_error",
                server=self._config.name,
                error=str(e),
            )

    def get_tools(self) -> dict[str, MCPToolDefinition]:
        """Get discovered tools.

        Returns:
            Dictionary of tool definitions
        """
        return self._tools.copy()

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: float | None = None,
    ) -> ToolResult:
        """Call a remote tool.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            timeout: Optional timeout override

        Returns:
            ToolResult with the execution result

        Raises:
            ValueError: If tool not found
            ConnectionError: If not connected
            TimeoutError: If call times out
        """
        if not self._connected:
            raise ConnectionError(f"Not connected to MCP server '{self._config.name}'")

        if not self._session:
            raise ConnectionError("MCP session not initialized")

        if tool_name not in self._tools:
            raise ValueError(f"Tool '{tool_name}' not found on server '{self._config.name}'")

        effective_timeout = timeout or self._config.timeout

        try:
            result = await asyncio.wait_for(
                self._session.call_tool(tool_name, arguments),
                timeout=effective_timeout,
            )

            # Convert MCP result to ToolResult
            content_text = ""
            if result.content:
                # Try to extract text content
                for block in result.content:
                    if hasattr(block, "text"):
                        content_text += block.text
                    elif hasattr(block, "data"):
                        content_text += str(block.data)
                    else:
                        content_text += str(block)

            # Check for errors
            if result.isError:
                return ToolResult(
                    tool_call_id="",
                    tool_name=tool_name,
                    success=False,
                    error=content_text or "Tool execution failed",
                    metadata={"server": self._config.name},
                )

            return ToolResult(
                tool_call_id="",
                tool_name=tool_name,
                success=True,
                output=content_text or (str(result.structuredContent) if result.structuredContent else ""),
                metadata={
                    "server": self._config.name,
                    "structured": result.structuredContent,
                },
            )

        except TimeoutError as e:
            logger.error(
                "mcp_tool_timeout",
                server=self._config.name,
                tool=tool_name,
                timeout=effective_timeout,
            )
            raise
        except Exception as e:
            logger.error(
                "mcp_tool_error",
                server=self._config.name,
                tool=tool_name,
                error=str(e),
            )
            return ToolResult(
                tool_call_id="",
                tool_name=tool_name,
                success=False,
                error=str(e),
                metadata={"server": self._config.name},
            )


class MCPTollWrapper(BaseTool):
    """Wrapper for an MCP tool as a BaseTool.

    Allows MCP tools to be registered in the local ToolRegistry.
    """

    def __init__(
        self,
        client: MCPClient,
        tool_def: MCPToolDefinition,
    ) -> None:
        """Initialize MCP tool wrapper.

        Args:
            client: MCP client connection
            tool_def: Tool definition
        """
        self._client = client
        self._tool_def = tool_def

    @property
    def name(self) -> str:
        """Tool name with server prefix."""
        return f"{self._tool_def.server_name}__{self._tool_def.name}"

    @property
    def description(self) -> str:
        """Tool description."""
        return f"[MCP:{self._tool_def.server_name}] {self._tool_def.description}"

    @property
    def parameters(self) -> dict[str, Any]:
        """Input schema from MCP server."""
        return self._tool_def.input_schema

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the remote tool.

        Args:
            **kwargs: Tool arguments

        Returns:
            ToolResult with execution result
        """
        result = await self._client.call_tool(self._tool_def.name, kwargs)
        # Set tool_call_id for tracking
        result.tool_call_id = self.name
        return result


class MCPRegistry:
    """Registry for managing multiple MCP server connections.

    Provides centralized management of MCP servers with:
    - Server registration and configuration
    - Connection lifecycle management
    - Tool discovery and access
    - Health monitoring
    """

    def __init__(self) -> None:
        """Initialize MCP registry."""
        self._servers: dict[str, MCPServerConfig] = {}
        self._clients: dict[str, MCPClient] = {}
        self._running = False

    async def register_server(self, config: MCPServerConfig) -> None:
        """Register an MCP server configuration.

        Args:
            config: Server configuration

        Raises:
            ValueError: If server with same name exists
        """
        if config.name in self._servers:
            raise ValueError(f"MCP server '{config.name}' already registered")

        self._servers[config.name] = config
        logger.info("mcp_server_registered", server=config.name)

    async def unregister_server(self, name: str) -> bool:
        """Unregister an MCP server.

        Args:
            name: Server name to unregister

        Returns:
            True if unregistered, False if not found
        """
        if name not in self._servers:
            logger.warning("mcp_server_not_found", server=name)
            return False

        # Disconnect if connected
        if name in self._clients:
            await self._clients[name].disconnect()
            del self._clients[name]

        del self._servers[name]
        logger.info("mcp_server_unregistered", server=name)
        return True

    async def start(self, auto_connect: bool = True) -> None:
        """Start the MCP registry.

        Args:
            auto_connect: Whether to auto-connect to servers
        """
        if self._running:
            logger.warning("mcp_registry_already_running")
            return

        self._running = True

        if auto_connect:
            # Connect to all auto-connect servers
            connect_tasks = []
            for name, config in self._servers.items():
                if config.auto_connect:
                    connect_tasks.append(self._connect_server(name))

            if connect_tasks:
                await asyncio.gather(*connect_tasks, return_exceptions=True)

        logger.info("mcp_registry_started")

    async def _connect_server(self, name: str) -> None:
        """Connect to a specific server.

        Args:
            name: Server name to connect to
        """
        if name not in self._servers:
            logger.error("mcp_server_not_found_for_connect", server=name)
            return

        config = self._servers[name]
        client = MCPClient(config)

        try:
            await client.connect()
            self._clients[name] = client
        except Exception as e:
            logger.error("mcp_connect_error", server=name, error=str(e))

    async def stop(self) -> None:
        """Stop the MCP registry and disconnect all servers."""
        self._running = False

        # Disconnect all clients
        disconnect_tasks = []
        for client in self._clients.values():
            disconnect_tasks.append(client.disconnect())

        if disconnect_tasks:
            await asyncio.gather(*disconnect_tasks, return_exceptions=True)

        self._clients.clear()
        logger.info("mcp_registry_stopped")

    def get_client(self, server_name: str) -> MCPClient | None:
        """Get a client by server name.

        Args:
            server_name: Server name

        Returns:
            MCPClient if connected, None otherwise
        """
        return self._clients.get(server_name)

    def list_servers(self) -> list[dict[str, Any]]:
        """List all registered servers with status.

        Returns:
            List of server info dictionaries
        """
        result = []
        for name, config in self._servers.items():
            client = self._clients.get(name)
            result.append({
                "name": name,
                "transport": config.transport,
                "url": config.url or f"{config.command} {' '.join(config.args)}",
                "connected": client.is_connected if client else False,
                "tool_count": len(client.get_tools()) if client else 0,
                "auto_connect": config.auto_connect,
            })
        return result

    def list_all_tools(self) -> list[MCPToolDefinition]:
        """List all tools from all connected servers.

        Returns:
            List of tool definitions
        """
        tools = []
        for client in self._clients.values():
            tools.extend(client.get_tools().values())
        return list(tools)

    def get_tool(self, server_name: str, tool_name: str) -> MCPToolDefinition | None:
        """Get a specific tool definition.

        Args:
            server_name: Server name
            tool_name: Tool name

        Returns:
            Tool definition if found, None otherwise
        """
        client = self._clients.get(server_name)
        if not client:
            return None
        return client.get_tools().get(tool_name)

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: float | None = None,
    ) -> ToolResult:
        """Call a tool on a specific server.

        Args:
            server_name: Server name
            tool_name: Tool name
            arguments: Tool arguments
            timeout: Optional timeout

        Returns:
            ToolResult with execution result
        """
        client = self._clients.get(server_name)
        if not client:
            return ToolResult(
                tool_call_id="",
                tool_name=tool_name,
                success=False,
                error=f"Server '{server_name}' not connected",
            )

        return await client.call_tool(tool_name, arguments, timeout)

    def get_statistics(self) -> dict[str, Any]:
        """Get registry statistics.

        Returns:
            Dictionary with statistics
        """
        total_tools = sum(
            len(client.get_tools()) for client in self._clients.values()
        )
        connected = sum(1 for c in self._clients.values() if c.is_connected)

        return {
            "total_servers": len(self._servers),
            "connected_servers": connected,
            "total_tools": total_tools,
            "running": self._running,
        }


# Convenience functions
def stdio_server(
    name: str,
    command: str,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    timeout: float = 30.0,
    auto_connect: bool = True,
) -> MCPServerConfig:
    """Create a stdio server configuration.

    Args:
        name: Server name
        command: Command to run
        args: Command arguments
        env: Environment variables
        timeout: Connection timeout
        auto_connect: Whether to auto-connect

    Returns:
        MCPServerConfig for stdio transport
    """
    return MCPServerConfig(
        name=name,
        transport="stdio",
        command=command,
        args=args or [],
        env=env or {},
        timeout=timeout,
        auto_connect=auto_connect,
    )


def http_server(
    name: str,
    url: str,
    timeout: float = 30.0,
    auto_connect: bool = True,
) -> MCPServerConfig:
    """Create an HTTP server configuration.

    Args:
        name: Server name
        url: Server URL
        timeout: Connection timeout
        auto_connect: Whether to auto-connect

    Returns:
        MCPServerConfig for HTTP transport
    """
    return MCPServerConfig(
        name=name,
        transport="http",
        url=url,
        timeout=timeout,
        auto_connect=auto_connect,
    )
