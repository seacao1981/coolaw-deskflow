"""FastAPI application factory and global state management."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from deskflow.api.middleware.rate_limit import RateLimitMiddleware
from deskflow.api.routes import chat, config, health, identity, llm, memory, metrics, monitor, skills, user_profile, channels, insights, tracing, logs, channels_gateway, sessions, channels_feishu, channels_wecom, channels_dingtalk, channels_telegram, channels_media, orchestration, setup
from deskflow.config import AppConfig, load_config
from deskflow.core.agent import Agent
from deskflow.core.identity import DefaultIdentity
from deskflow.core.task_monitor import TaskMonitor
from deskflow.llm.client import LLMClient, create_adapter
from deskflow.memory.manager import MemoryManager
from deskflow.observability.logging import get_logger, setup_logging
from deskflow.skills.loader import SkillLoader
from deskflow.skills.registry import default_registry as skill_registry
from deskflow.tools.builtin.file import FileTool
from deskflow.tools.builtin.shell import ShellTool
from deskflow.tools.builtin.sticker import StickerTool
from deskflow.tools.builtin.web import WebTool
from deskflow.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = get_logger(__name__)

_app_state: AppState | None = None


@dataclass
class AppState:
    """Global application state holding all initialized components."""

    config: AppConfig
    agent: Agent | None = field(default=None)
    memory: MemoryManager | None = field(default=None)
    tools: ToolRegistry | None = field(default=None)
    llm_client: LLMClient | None = field(default=None)
    monitor: TaskMonitor = field(default_factory=TaskMonitor)
    skill_loader: SkillLoader | None = field(default=None)


def get_app_state() -> AppState:
    """Get the global app state. Raises if not initialized."""
    if _app_state is None:
        raise RuntimeError("Application not initialized")
    return _app_state


async def _initialize_components(app_config: AppConfig) -> AppState:
    """Initialize all application components."""
    global _app_state

    state = AppState(config=app_config)

    # 1. Memory
    memory = MemoryManager(
        db_path=app_config.get_db_path(),
        cache_capacity=app_config.memory.memory_cache_size,
    )
    await memory.initialize()
    state.memory = memory
    logger.info("memory_initialized")

    # 2. Tools
    tools = ToolRegistry(default_timeout=app_config.tools.tool_timeout)
    await tools.register(ShellTool())
    await tools.register(FileTool(allowed_paths=app_config.tools.get_allowed_paths()))
    await tools.register(WebTool())
    await tools.register(StickerTool())
    state.tools = tools
    logger.info("tools_initialized", count=tools.count)

    # 3. LLM
    try:
        primary_adapter = create_adapter(app_config)
        llm_client = LLMClient(primary=primary_adapter)
        state.llm_client = llm_client
        logger.info(
            "llm_initialized",
            provider=primary_adapter.provider_name,
            model=primary_adapter.model_name,
        )
    except ValueError as e:
        logger.warning("llm_init_skipped", reason=str(e))

    # 4. Identity
    identity_dir = app_config.get_project_root() / "identity"
    identity = DefaultIdentity(identity_dir=identity_dir)

    # 5. Skills - Load skills from skills/ directory
    project_root = app_config.get_project_root()
    skills_dir = project_root / "skills"

    if skills_dir.exists():
        skill_loader = SkillLoader(registry=skill_registry)
        skill_loader.load_all_skills(project_root)
        state.skill_loader = skill_loader
        logger.info("skills_initialized", count=skill_loader.registry.count)
    else:
        logger.info("skills_dir_not_found", path=str(skills_dir))

    # 6. Agent
    if state.llm_client and state.memory and state.tools:
        agent = Agent(
            brain=state.llm_client,
            memory=state.memory,
            tools=state.tools,
            identity=identity,
            monitor=state.monitor,
            skill_registry=skill_registry,
        )
        state.agent = agent
        logger.info("agent_initialized")

    _app_state = state
    return state


async def _shutdown_components(state: AppState) -> None:
    """Gracefully shut down all components."""
    if state.memory:
        await state.memory.close()
    logger.info("components_shutdown")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan managing startup and shutdown."""
    app_config = load_config()
    setup_logging(log_level=app_config.server.log_level)

    # Setup tracing
    from deskflow.observability.tracing import setup_tracing
    setup_tracing(
        enabled=True,
        exporter="console",  # Change to "jaeger" or "zipkin" in production
    )

    # Setup enhanced logging with buffer and cleanup
    from deskflow.logging import setup_enhanced_logging
    setup_enhanced_logging(
        log_level=app_config.server.log_level,
        json_output=True,
        enable_buffer=True,
        enable_cleanup=True,
    )

    # Setup message gateway
    from deskflow.channels import start_gateway
    await start_gateway(num_workers=3)

    # Setup session manager
    from deskflow.channels import start_session_manager
    await start_session_manager(
        db_path="data/db/sessions.db",
        default_ttl=3600,
        cleanup_interval=300,
    )

    logger.info("starting_deskflow", version=app_config.version)

    state = await _initialize_components(app_config)

    yield

    # Flush logs before shutdown
    from deskflow.logging import flush_logs
    flush_logs()

    # Stop message gateway
    from deskflow.channels import stop_gateway
    await stop_gateway()

    # Stop session manager
    from deskflow.channels import stop_session_manager
    await stop_session_manager()

    await _shutdown_components(state)
    logger.info("deskflow_stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Coolaw DeskFlow",
        description="Self-evolving AI Agent Framework API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Tauri app connects from localhost
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

    # Routes
    app.include_router(chat.router)
    app.include_router(health.router)
    app.include_router(config.router)
    app.include_router(llm.router)
    app.include_router(monitor.router)
    app.include_router(metrics.router)
    app.include_router(skills.router)
    app.include_router(identity.router)
    app.include_router(memory.router)
    app.include_router(user_profile.router)
    app.include_router(channels.router)
    app.include_router(insights.router)
    app.include_router(tracing.router)
    app.include_router(logs.router)
    app.include_router(channels_gateway.router)
    app.include_router(sessions.router)
    app.include_router(channels_feishu.router)
    app.include_router(channels_wecom.router)
    app.include_router(channels_dingtalk.router)
    app.include_router(channels_telegram.router)
    app.include_router(channels_media.router)
    app.include_router(orchestration.router)
    app.include_router(setup.router)

    return app
