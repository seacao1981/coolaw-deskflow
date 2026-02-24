"""DeskFlow orchestration module."""

from deskflow.orchestration.collaboration import (
    MasterAgent,
    Worker,
    WorkerStatus,
    Task,
    TaskResult,
    TaskProgress,
    TaskType,
    TaskPriority,
    TaskStatus,
    MessageBus,
    LoadBalancer,
    WorkerPool,
    PriorityTaskQueue,
)
from deskflow.orchestration.worker_agent import (
    WorkerAgent,
    WorkerAgentStatus,
    WorkerAgentConfig,
    TaskContext,
    create_default_worker,
    handle_shell_task,
    handle_file_task,
    handle_web_search_task,
    handle_code_generation_task,
    handle_text_processing_task,
)
from deskflow.orchestration.zmq_bus import (
    ZMQBus,
    ZMQPublisher,
    ZMQSubscriber,
    ZMQRequester,
    ZMQResponder,
    ZMQMessage,
    MessageType,
)
from deskflow.orchestration.registry import (
    WorkerRegistry,
    WorkerRegistryConfig,
    WorkerInfo,
    WorkerHealthStatus,
    ServiceDiscovery,
)

__all__ = [
    # Core classes
    "MasterAgent",
    "Worker",
    "WorkerStatus",
    "WorkerPool",
    "Task",
    "TaskResult",
    "TaskProgress",
    # Worker Agent classes
    "WorkerAgent",
    "WorkerAgentStatus",
    "WorkerAgentConfig",
    "TaskContext",
    # Registry classes
    "WorkerRegistry",
    "WorkerRegistryConfig",
    "WorkerInfo",
    "WorkerHealthStatus",
    "ServiceDiscovery",
    # Enums
    "TaskType",
    "TaskPriority",
    "TaskStatus",
    # Supporting classes
    "MessageBus",
    "LoadBalancer",
    "PriorityTaskQueue",
    # Built-in handlers
    "create_default_worker",
    "handle_shell_task",
    "handle_file_task",
    "handle_web_search_task",
    "handle_code_generation_task",
    "handle_text_processing_task",
    # ZeroMQ classes
    "ZMQBus",
    "ZMQPublisher",
    "ZMQSubscriber",
    "ZMQRequester",
    "ZMQResponder",
    "ZMQMessage",
    "MessageType",
]
