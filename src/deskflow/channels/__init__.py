"""DeskFlow channels module for IM integration."""

from deskflow.channels.gateway import (
    IMessage,
    BaseMessage,
    OutboundMessage,
    MessageType,
    MessageStatus,
    ChannelAdapter,
    MessageQueue,
    MessageGateway,
    get_gateway,
    start_gateway,
    stop_gateway,
    register_adapter,
)

from deskflow.channels.session import (
    SessionData,
    SessionStore,
    SessionManager,
    get_session_manager,
    start_session_manager,
    stop_session_manager,
    create_session,
    get_session,
    update_session_context,
)

from deskflow.channels.feishu import (
    FeishuAdapter,
    FeishuConfig,
    FeishuMessage,
)

from deskflow.channels.wework import (
    WeComAdapter,
    WeComConfig,
    WeComMessage,
)

from deskflow.channels.dingtalk import (
    DingTalkAdapter,
    DingTalkConfig,
    DingTalkMessage,
)

from deskflow.channels.telegram import (
    TelegramAdapter,
    TelegramConfig,
    TelegramMessage,
)

from deskflow.channels.media import (
    MediaProcessor,
    MediaFile,
    MediaType,
    MediaProcessingStatus,
    TranscriptionResult,
    OcrResult,
    WhisperExtractor,
    BaiduOcrExtractor,
    get_processor,
    process_voice,
    process_image,
    process_video,
)

__all__ = [
    "IMessage",
    "BaseMessage",
    "OutboundMessage",
    "MessageType",
    "MessageStatus",
    "ChannelAdapter",
    "MessageQueue",
    "MessageGateway",
    "get_gateway",
    "start_gateway",
    "stop_gateway",
    "register_adapter",
    "SessionData",
    "SessionStore",
    "SessionManager",
    "get_session_manager",
    "start_session_manager",
    "stop_session_manager",
    "create_session",
    "get_session",
    "update_session_context",
    "FeishuAdapter",
    "FeishuConfig",
    "FeishuMessage",
    "WeComAdapter",
    "WeComConfig",
    "WeComMessage",
    "DingTalkAdapter",
    "DingTalkConfig",
    "DingTalkMessage",
    "TelegramAdapter",
    "TelegramConfig",
    "TelegramMessage",
    "MediaProcessor",
    "MediaFile",
    "MediaType",
    "MediaProcessingStatus",
    "TranscriptionResult",
    "OcrResult",
    "WhisperExtractor",
    "BaiduOcrExtractor",
    "get_processor",
    "process_voice",
    "process_image",
    "process_video",
]
