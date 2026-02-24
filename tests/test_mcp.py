"""Tests for MCP tool integration."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from deskflow.tools.mcp import (
    MCPServerConfig,
    MCPToolDefinition,
    MCPClient,
    MCPTollWrapper,
    MCPRegistry,
    stdio_server,
    http_server,
    _get_mcp_stdio_client,
    _get_mcp_http_client,
)


class TestMCPServerConfig:
    """Test MCPServerConfig dataclass."""

    def test_stdio_config_creation(self):
        """Test creating stdio server config."""
        config = MCPServerConfig(
            name="test-server",
            transport="stdio",
            command="python",
            args=["server.py"],
            timeout=60.0,
        )

        assert config.name == "test-server"
        assert config.transport == "stdio"
        assert config.command == "python"
        assert config.args == ["server.py"]
        assert config.timeout == 60.0
        assert config.auto_connect is True
        assert config.env == {}

    def test_http_config_creation(self):
        """Test creating HTTP server config."""
        config = MCPServerConfig(
            name="remote-server",
            transport="http",
            url="http://localhost:8000/mcp",
            timeout=45.0,
            auto_connect=False,
        )

        assert config.name == "remote-server"
        assert config.transport == "http"
        assert config.url == "http://localhost:8000/mcp"
        assert config.timeout == 45.0
        assert config.auto_connect is False

    def test_config_with_env(self):
        """Test config with environment variables."""
        config = MCPServerConfig(
            name="test-server",
            transport="stdio",
            command="uv",
            args=["run", "mcp-server"],
            env={"API_KEY": "secret", "DEBUG": "true"},
        )

        assert config.env["API_KEY"] == "secret"
        assert config.env["DEBUG"] == "true"


class TestMCPToolDefinition:
    """Test MCPToolDefinition dataclass."""

    def test_tool_definition_creation(self):
        """Test creating tool definition."""
        tool_def = MCPToolDefinition(
            name="fetch",
            description="Fetch content from a URL",
            input_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"}
                },
                "required": ["url"],
            },
            server_name="web-server",
        )

        assert tool_def.name == "fetch"
        assert tool_def.description == "Fetch content from a URL"
        assert tool_def.server_name == "web-server"
        assert "url" in tool_def.input_schema["properties"]


class TestMCPClient:
    """Test MCPClient class."""

    @pytest.fixture
    def stdio_config(self):
        """Create a stdio config for testing."""
        return MCPServerConfig(
            name="test-server",
            transport="stdio",
            command="python",
            args=["server.py"],
            timeout=10.0,
        )

    @pytest.fixture
    def http_config(self):
        """Create an HTTP config for testing."""
        return MCPServerConfig(
            name="http-server",
            transport="http",
            url="http://localhost:8000/mcp",
            timeout=10.0,
        )

    def test_client_initialization(self, stdio_config):
        """Test client initialization."""
        client = MCPClient(stdio_config)

        assert client.name == "test-server"
        assert client.is_connected is False
        assert client.get_tools() == {}

    @pytest.mark.asyncio
    async def test_connect_stdio_no_command(self, stdio_config):
        """Test stdio connection fails without command."""
        stdio_config.command = ""
        client = MCPClient(stdio_config)

        with pytest.raises(ValueError, match="Command is required"):
            await client.connect()

    @pytest.mark.asyncio
    async def test_connect_http_no_url(self, http_config):
        """Test HTTP connection fails without URL."""
        http_config.url = ""
        client = MCPClient(http_config)

        with pytest.raises(ValueError, match="URL is required"):
            await client.connect()

    @pytest.mark.asyncio
    async def test_connect_unknown_transport(self):
        """Test connection fails with unknown transport."""
        config = MCPServerConfig(
            name="test",
            transport="unknown",
            command="python",
        )
        client = MCPClient(config)

        with pytest.raises(ValueError, match="Unknown transport"):
            await client.connect()

    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self, stdio_config):
        """Test disconnect when not connected."""
        client = MCPClient(stdio_config)
        # Should not raise
        await client.disconnect()

    @pytest.mark.asyncio
    async def test_call_tool_not_connected(self, stdio_config):
        """Test calling tool when not connected."""
        client = MCPClient(stdio_config)

        with pytest.raises(ConnectionError, match="Not connected"):
            await client.call_tool("tool", {})

    @pytest.mark.asyncio
    async def test_connect_stdio_import_error(self, stdio_config):
        """Test stdio connection handles import error."""
        client = MCPClient(stdio_config)

        # When mcp module is not installed, the lazy import will fail
        with patch("deskflow.tools.mcp._get_mcp_stdio_client", side_effect=ImportError("MCP SDK not installed. Install with: pip install mcp")):
            with pytest.raises(ImportError, match="MCP SDK not installed"):
                await client.connect()

    @pytest.mark.asyncio
    async def test_connect_http_import_error(self, http_config):
        """Test HTTP connection handles import error."""
        client = MCPClient(http_config)

        with patch("deskflow.tools.mcp._get_mcp_http_client", side_effect=ImportError("MCP SDK not installed. Install with: pip install mcp")):
            with pytest.raises(ImportError, match="MCP SDK not installed"):
                await client.connect()

    @pytest.mark.asyncio
    async def test_connect_stdio_success(self, stdio_config):
        """Test stdio connection success."""
        # Setup session mock
        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # ClientSession class mock that returns mock_session
        mock_session_cls = MagicMock(return_value=mock_session)

        # Setup context manager that returns streams - use MagicMock for sync context manager
        mock_read = MagicMock()
        mock_write = MagicMock()
        mock_ctx_manager = MagicMock()
        mock_ctx_manager.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
        mock_ctx_manager.__aexit__ = AsyncMock(return_value=None)

        def make_ctx_manager(params):
            return mock_ctx_manager

        with patch("deskflow.tools.mcp._get_mcp_stdio_client", return_value=(make_ctx_manager, mock_session_cls, MagicMock, MagicMock)):
            client = MCPClient(stdio_config)
            await client.connect()

            assert client.is_connected is True
            assert client.get_tools() == {}

            await client.disconnect()

    @pytest.mark.asyncio
    async def test_connect_http_success(self, http_config):
        """Test HTTP connection success."""
        # Setup session mock
        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # ClientSession class mock that returns mock_session
        mock_session_cls = MagicMock(return_value=mock_session)

        # Setup context manager
        mock_read = MagicMock()
        mock_write = MagicMock()
        mock_ctx_manager = MagicMock()
        mock_ctx_manager.__aenter__ = AsyncMock(return_value=(mock_read, mock_write, None))
        mock_ctx_manager.__aexit__ = AsyncMock(return_value=None)

        def make_ctx_manager(url):
            return mock_ctx_manager

        with patch("deskflow.tools.mcp._get_mcp_http_client", return_value=(make_ctx_manager, mock_session_cls, MagicMock)):
            client = MCPClient(http_config)
            await client.connect()

            assert client.is_connected is True

            await client.disconnect()

    @pytest.mark.asyncio
    async def test_discover_tools(self, stdio_config):
        """Test tool discovery."""
        # Setup session with tools
        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()

        # Create mock tool objects with proper string name attributes
        from collections import namedtuple
        MockTool = namedtuple('MockTool', ['name', 'description', 'inputSchema'])
        mock_tools_response = MagicMock()
        mock_tools_response.tools = [
            MockTool(name="tool1", description="First tool", inputSchema={"type": "object"}),
            MockTool(name="tool2", description="Second tool", inputSchema={"type": "object"}),
        ]
        mock_session.list_tools = AsyncMock(return_value=mock_tools_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # ClientSession class mock
        mock_session_cls = MagicMock(return_value=mock_session)

        # Setup context manager
        mock_read = MagicMock()
        mock_write = MagicMock()
        mock_ctx_manager = MagicMock()
        mock_ctx_manager.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
        mock_ctx_manager.__aexit__ = AsyncMock(return_value=None)

        def make_ctx_manager(params):
            return mock_ctx_manager

        with patch("deskflow.tools.mcp._get_mcp_stdio_client", return_value=(make_ctx_manager, mock_session_cls, MagicMock, MagicMock)):
            client = MCPClient(stdio_config)
            await client.connect()

            tools = client.get_tools()
            assert len(tools) == 2
            assert "tool1" in tools
            assert "tool2" in tools

            await client.disconnect()

    @pytest.mark.asyncio
    async def test_call_tool_success(self, stdio_config):
        """Test calling a tool successfully."""
        # Setup session with tool
        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()

        # Create mock tool with proper string name attribute
        from collections import namedtuple
        MockTool = namedtuple('MockTool', ['name', 'description', 'inputSchema'])
        mock_tool = MockTool(name="test_tool", description="Test tool", inputSchema={"type": "object"})
        mock_tools_response = MagicMock(tools=[mock_tool])
        mock_session.list_tools = AsyncMock(return_value=mock_tools_response)

        # Mock tool call result using MagicMock like the error test
        mock_result = MagicMock()
        mock_result.content = [MagicMock(text="Result from tool")]
        mock_result.isError = False
        mock_result.structuredContent = None
        mock_session.call_tool = AsyncMock(return_value=mock_result)

        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # ClientSession class mock
        mock_session_cls = MagicMock(return_value=mock_session)

        # Setup context manager
        mock_read = MagicMock()
        mock_write = MagicMock()
        mock_ctx_manager = MagicMock()
        mock_ctx_manager.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
        mock_ctx_manager.__aexit__ = AsyncMock(return_value=None)

        def make_ctx_manager(params):
            return mock_ctx_manager

        with patch("deskflow.tools.mcp._get_mcp_stdio_client", return_value=(make_ctx_manager, mock_session_cls, MagicMock, MagicMock)):
            client = MCPClient(stdio_config)
            await client.connect()

            result = await client.call_tool("test_tool", {"arg": "value"})

            assert result.success is True
            assert result.output == "Result from tool"
            assert result.tool_name == "test_tool"

            await client.disconnect()

    @pytest.mark.asyncio
    async def test_call_tool_error(self, stdio_config):
        """Test calling tool that returns error."""
        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()

        # Create mock tool with proper string name attribute
        from collections import namedtuple
        MockTool = namedtuple('MockTool', ['name', 'description', 'inputSchema'])
        mock_tool = MockTool(name="error_tool", description="Error tool", inputSchema={})
        mock_tools_response = MagicMock(tools=[mock_tool])
        mock_session.list_tools = AsyncMock(return_value=mock_tools_response)

        # Mock error result
        mock_result = MagicMock()
        mock_result.content = [MagicMock(text="Error message")]
        mock_result.isError = True
        mock_result.structuredContent = None
        mock_session.call_tool = AsyncMock(return_value=mock_result)

        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # ClientSession class mock
        mock_session_cls = MagicMock(return_value=mock_session)

        # Setup context manager
        mock_read = MagicMock()
        mock_write = MagicMock()
        mock_ctx_manager = MagicMock()
        mock_ctx_manager.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
        mock_ctx_manager.__aexit__ = AsyncMock(return_value=None)

        def make_ctx_manager(params):
            return mock_ctx_manager

        with patch("deskflow.tools.mcp._get_mcp_stdio_client", return_value=(make_ctx_manager, mock_session_cls, MagicMock, MagicMock)):
            client = MCPClient(stdio_config)
            await client.connect()

            result = await client.call_tool("error_tool", {})

            assert result.success is False
            assert result.error == "Error message"

            await client.disconnect()

    @pytest.mark.asyncio
    async def test_call_tool_timeout(self, stdio_config):
        """Test calling tool with timeout."""
        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()

        # Create mock tool with proper string name attribute
        from collections import namedtuple
        MockTool = namedtuple('MockTool', ['name', 'description', 'inputSchema'])
        mock_tool = MockTool(name="slow_tool", description="Slow tool", inputSchema={})
        mock_tools_response = MagicMock(tools=[mock_tool])
        mock_session.list_tools = AsyncMock(return_value=mock_tools_response)
        mock_session.call_tool = AsyncMock(side_effect=asyncio.TimeoutError())

        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # ClientSession class mock
        mock_session_cls = MagicMock(return_value=mock_session)

        # Setup context manager
        mock_read = MagicMock()
        mock_write = MagicMock()
        mock_ctx_manager = MagicMock()
        mock_ctx_manager.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
        mock_ctx_manager.__aexit__ = AsyncMock(return_value=None)

        def make_ctx_manager(params):
            return mock_ctx_manager

        with patch("deskflow.tools.mcp._get_mcp_stdio_client", return_value=(make_ctx_manager, mock_session_cls, MagicMock, MagicMock)):
            client = MCPClient(stdio_config)
            await client.connect()

            with pytest.raises(asyncio.TimeoutError):
                await client.call_tool("slow_tool", {}, timeout=0.1)

            await client.disconnect()

    @pytest.mark.asyncio
    async def test_call_tool_not_found(self, stdio_config):
        """Test calling non-existent tool."""
        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # ClientSession class mock
        mock_session_cls = MagicMock(return_value=mock_session)

        # Setup context manager
        mock_read = MagicMock()
        mock_write = MagicMock()
        mock_ctx_manager = MagicMock()
        mock_ctx_manager.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
        mock_ctx_manager.__aexit__ = AsyncMock(return_value=None)

        def make_ctx_manager(params):
            return mock_ctx_manager

        with patch("deskflow.tools.mcp._get_mcp_stdio_client", return_value=(make_ctx_manager, mock_session_cls, MagicMock, MagicMock)):
            client = MCPClient(stdio_config)
            await client.connect()

            with pytest.raises(ValueError, match="not found"):
                await client.call_tool("nonexistent", {})

            await client.disconnect()


class TestMCPTollWrapper:
    """Test MCPToolWrapper class."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock MCP client."""
        client = MagicMock(spec=MCPClient)
        client.name = "test-server"
        return client

    @pytest.fixture
    def tool_def(self):
        """Create a tool definition."""
        return MCPToolDefinition(
            name="test_tool",
            description="Test tool description",
            input_schema={
                "type": "object",
                "properties": {"input": {"type": "string"}},
            },
            server_name="test-server",
        )

    def test_wrapper_initialization(self, mock_client, tool_def):
        """Test wrapper initialization."""
        wrapper = MCPTollWrapper(mock_client, tool_def)

        assert wrapper.name == "test-server__test_tool"
        assert "test-server" in wrapper.description
        assert wrapper.parameters == tool_def.input_schema

    @pytest.mark.asyncio
    async def test_wrapper_execute(self, mock_client, tool_def):
        """Test wrapper execute."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "Result"
        mock_result.tool_call_id = ""
        mock_client.call_tool = AsyncMock(return_value=mock_result)

        wrapper = MCPTollWrapper(mock_client, tool_def)
        result = await wrapper.execute(input="test")

        assert result.tool_call_id == wrapper.name
        mock_client.call_tool.assert_called_once_with("test_tool", {"input": "test"})

    @pytest.mark.asyncio
    async def test_wrapper_execute_error(self, mock_client, tool_def):
        """Test wrapper execute with error."""
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "Failed"
        mock_result.tool_call_id = ""
        mock_client.call_tool = AsyncMock(return_value=mock_result)

        wrapper = MCPTollWrapper(mock_client, tool_def)
        result = await wrapper.execute(input="test")

        assert result.success is False
        assert result.error == "Failed"


class TestMCPRegistry:
    """Test MCPRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create a registry for testing."""
        return MCPRegistry()

    @pytest.fixture
    def server_config(self):
        """Create a server config for testing."""
        return MCPServerConfig(
            name="test-server",
            transport="stdio",
            command="python",
            args=["server.py"],
            auto_connect=False,
        )

    @pytest.mark.asyncio
    async def test_register_server(self, registry, server_config):
        """Test server registration."""
        await registry.register_server(server_config)

        assert "test-server" in registry._servers
        servers = registry.list_servers()
        assert len(servers) == 1
        assert servers[0]["name"] == "test-server"

    @pytest.mark.asyncio
    async def test_register_duplicate_server(self, registry, server_config):
        """Test registering duplicate server."""
        await registry.register_server(server_config)

        with pytest.raises(ValueError, match="already registered"):
            await registry.register_server(server_config)

    @pytest.mark.asyncio
    async def test_unregister_server(self, registry, server_config):
        """Test server unregistration."""
        await registry.register_server(server_config)
        result = await registry.unregister_server("test-server")

        assert result is True
        assert "test-server" not in registry._servers

    @pytest.mark.asyncio
    async def test_unregister_not_found(self, registry):
        """Test unregistering non-existent server."""
        result = await registry.unregister_server("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_start_auto_connect(self, registry, server_config):
        """Test registry start with auto-connect."""
        server_config.auto_connect = True
        await registry.register_server(server_config)

        with patch.object(registry, "_connect_server", new_callable=AsyncMock):
            await registry.start(auto_connect=True)

            assert registry._running is True
            registry._connect_server.assert_called_once_with("test-server")

    @pytest.mark.asyncio
    async def test_start_no_auto_connect(self, registry, server_config):
        """Test registry start without auto-connect."""
        await registry.register_server(server_config)

        with patch.object(registry, "_connect_server", new_callable=AsyncMock) as mock_connect:
            await registry.start(auto_connect=False)

            assert registry._running is True
            mock_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_already_running(self, registry):
        """Test starting already running registry."""
        registry._running = True

        # Should not raise, just log warning
        await registry.start()

    @pytest.mark.asyncio
    async def test_stop(self, registry, server_config):
        """Test registry stop."""
        await registry.register_server(server_config)
        registry._running = True

        # Mock client
        mock_client = MagicMock()
        mock_client.disconnect = AsyncMock()
        mock_client.is_connected = True
        registry._clients["test-server"] = mock_client

        await registry.stop()

        assert registry._running is False
        mock_client.disconnect.assert_called_once()
        assert len(registry._clients) == 0

    @pytest.mark.asyncio
    async def test_get_client(self, registry, server_config):
        """Test getting client by server name."""
        await registry.register_server(server_config)

        # Not connected yet
        assert registry.get_client("test-server") is None

        # Mock connected client
        mock_client = MagicMock()
        mock_client.is_connected = True
        registry._clients["test-server"] = mock_client

        assert registry.get_client("test-server") is mock_client

    @pytest.mark.asyncio
    async def test_list_servers(self, registry, server_config):
        """Test listing servers."""
        await registry.register_server(server_config)

        servers = registry.list_servers()

        assert len(servers) == 1
        assert servers[0]["name"] == "test-server"
        assert servers[0]["transport"] == "stdio"
        assert servers[0]["connected"] is False

    @pytest.mark.asyncio
    async def test_list_all_tools(self, registry, server_config):
        """Test listing all tools from all servers."""
        await registry.register_server(server_config)

        # Mock client with tools
        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.get_tools.return_value = {
            "tool1": MCPToolDefinition("tool1", "Tool 1", {}, "test-server"),
            "tool2": MCPToolDefinition("tool2", "Tool 2", {}, "test-server"),
        }
        registry._clients["test-server"] = mock_client

        tools = registry.list_all_tools()

        assert len(tools) == 2
        assert tools[0].name == "tool1"
        assert tools[1].name == "tool2"

    @pytest.mark.asyncio
    async def test_get_tool(self, registry, server_config):
        """Test getting specific tool."""
        await registry.register_server(server_config)

        # Mock client
        mock_client = MagicMock()
        mock_tool = MCPToolDefinition("test_tool", "Test", {}, "test-server")
        mock_client.get_tools.return_value = {"test_tool": mock_tool}
        mock_client.is_connected = True
        registry._clients["test-server"] = mock_client

        tool = registry.get_tool("test-server", "test_tool")

        assert tool is not None
        assert tool.name == "test_tool"

    @pytest.mark.asyncio
    async def test_call_tool(self, registry, server_config):
        """Test calling tool through registry."""
        await registry.register_server(server_config)

        # Mock client
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "Result"
        mock_client.call_tool = AsyncMock(return_value=mock_result)
        mock_client.is_connected = True
        registry._clients["test-server"] = mock_client

        result = await registry.call_tool(
            "test-server", "test_tool", {"arg": "value"}
        )

        assert result.success is True
        # Check call was made with correct arguments (timeout may be passed as None)
        call_args = mock_client.call_tool.call_args
        assert call_args[0][0] == "test_tool"
        assert call_args[0][1] == {"arg": "value"}

    @pytest.mark.asyncio
    async def test_call_tool_server_not_connected(self, registry, server_config):
        """Test calling tool on disconnected server."""
        await registry.register_server(server_config)

        result = await registry.call_tool("test-server", "test_tool", {})

        assert result.success is False
        assert "not connected" in result.error

    @pytest.mark.asyncio
    async def test_get_statistics(self, registry, server_config):
        """Test getting registry statistics."""
        await registry.register_server(server_config)

        # Mock connected client with tools
        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.get_tools.return_value = {
            "tool1": MCPToolDefinition("tool1", "Tool 1", {}, "test-server"),
        }
        registry._clients["test-server"] = mock_client

        stats = registry.get_statistics()

        assert stats["total_servers"] == 1
        assert stats["connected_servers"] == 1
        assert stats["total_tools"] == 1
        assert stats["running"] is False  # Not started


class TestConvenienceFunctions:
    """Test stdio_server and http_server convenience functions."""

    def test_stdio_server_function(self):
        """Test stdio_server convenience function."""
        config = stdio_server(
            name="my-server",
            command="uv",
            args=["run", "mcp-server"],
            env={"KEY": "value"},
            timeout=60.0,
            auto_connect=False,
        )

        assert config.name == "my-server"
        assert config.transport == "stdio"
        assert config.command == "uv"
        assert config.args == ["run", "mcp-server"]
        assert config.env == {"KEY": "value"}
        assert config.timeout == 60.0
        assert config.auto_connect is False

    def test_http_server_function(self):
        """Test http_server convenience function."""
        config = http_server(
            name="remote-server",
            url="http://example.com/mcp",
            timeout=45.0,
            auto_connect=True,
        )

        assert config.name == "remote-server"
        assert config.transport == "http"
        assert config.url == "http://example.com/mcp"
        assert config.timeout == 45.0
        assert config.auto_connect is True


class TestLazyImports:
    """Test lazy import functions."""

    def test_get_mcp_stdio_client_import_error(self):
        """Test stdio client import error."""
        with patch.dict("sys.modules", {"mcp": None}):
            with pytest.raises(ImportError, match="MCP SDK not installed"):
                _get_mcp_stdio_client()

    def test_get_mcp_http_client_import_error(self):
        """Test HTTP client import error."""
        with patch.dict("sys.modules", {"mcp": None}):
            with pytest.raises(ImportError, match="MCP SDK not installed"):
                _get_mcp_http_client()
