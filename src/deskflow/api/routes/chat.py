"""Chat API routes - REST and WebSocket."""

from __future__ import annotations

import contextlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException

from deskflow.api.schemas.models import ChatRequest, ChatResponse, ToolCallInfo
from deskflow.config import AppConfig
from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

# Database path for conversation history
DB_PATH = Path.cwd() / "data" / "conversations.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _get_agent() -> Any:
    """Get the agent instance from app state.

    This is resolved at runtime to avoid circular imports.
    """
    from deskflow.app import get_app_state

    return get_app_state().agent


def _get_config() -> AppConfig:
    """Get app config at runtime."""
    from deskflow.app import get_app_state

    return get_app_state().config


def init_conversation_db() -> None:
    """Initialize conversation database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            message_count INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
    """)
    conn.commit()
    conn.close()


def _get_db_connection() -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a message and get a complete response."""
    agent = _get_agent()

    if not agent:
        return ChatResponse(
            message="[LLM 未配置] 请在 .env 文件中设置 DESKFLOW_ANTHROPIC_API_KEY",
            conversation_id=request.conversation_id or "",
            tool_calls=[],
            metadata={"warning": "LLM not configured"},
        )

    response = await agent.chat(
        user_message=request.message,
        conversation_id=request.conversation_id,
    )

    tool_calls_info = [
        ToolCallInfo(
            name=tc.name,
            arguments=tc.arguments,
            success=tc.status.value == "completed",
        )
        for tc in response.tool_calls
    ]

    # Learn from conversation asynchronously (non-blocking)
    try:
        from deskflow.core.user_profile import get_profile_manager

        async def learn_conversation():
            manager = get_profile_manager()
            await manager.learn_from_conversation([
                {"role": "user", "content": request.message},
                {"role": "assistant", "content": response.content},
            ])

        # Schedule learning in background (don't block response)
        import asyncio
        asyncio.create_task(learn_conversation())
    except Exception as e:
        logger.warning("user_profile_learn_failed", error=str(e))

    return ChatResponse(
        message=response.content,
        conversation_id=request.conversation_id or "",
        tool_calls=tool_calls_info,
        metadata=response.metadata,
    )


@router.websocket("/chat/stream")
async def chat_stream(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming chat responses.

    Client sends: {"message": "...", "conversation_id": "..."}
    Server sends: StreamChunk objects as JSON lines.
    """
    await websocket.accept()
    logger.info("websocket_connected", remote=websocket.client)

    agent = _get_agent()

    if not agent:
        await websocket.send_json({
            "type": "error",
            "content": "LLM 未配置，请在 .env 文件中设置 DESKFLOW_ANTHROPIC_API_KEY",
        })
        await websocket.close()
        return

    try:
        while True:
            data = await websocket.receive_text()
            logger.debug("websocket_message_received", size=len(data))

            try:
                request = json.loads(data)
            except json.JSONDecodeError:
                logger.warning("websocket_invalid_json")
                await websocket.send_json({"type": "error", "content": "Invalid JSON"})
                continue

            message = request.get("message", "")
            conversation_id = request.get("conversation_id")

            if not message:
                await websocket.send_json({"type": "error", "content": "Empty message"})
                continue

            logger.info(
                "chat_request_received",
                message_length=len(message),
                conversation_id=conversation_id,
            )

            async for chunk in agent.stream_chat(
                user_message=message,
                conversation_id=conversation_id,
            ):
                chunk_data = chunk.model_dump()
                # Handle non-serializable fields
                if chunk.tool_call:
                    chunk_data["tool_call"] = chunk.tool_call.model_dump()
                if chunk.tool_result:
                    chunk_data["tool_result"] = chunk.tool_result.model_dump()
                await websocket.send_json(chunk_data)

            logger.info("chat_response_complete")

    except WebSocketDisconnect:
        logger.info("websocket_disconnected")
    except Exception as e:
        logger.error("websocket_error", error=str(e), exc_info=True)
        with contextlib.suppress(Exception):
            await websocket.send_json({"type": "error", "content": str(e)})


# Initialize database on module load
init_conversation_db()


@router.get("/chat/history")
async def get_conversation_history(limit: int = 50):
    """Get conversation history list.

    Args:
        limit: Maximum number of conversations to return.

    Returns:
        List of conversations with metadata.
    """
    conn = _get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, created_at, updated_at, message_count
        FROM conversations
        ORDER BY updated_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()

    conversations = [
        {
            "id": row["id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "message_count": row["message_count"],
        }
        for row in rows
    ]

    return {"conversations": conversations, "total": len(conversations)}


@router.get("/chat/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all messages.

    Args:
        conversation_id: The conversation ID.

    Returns:
        Conversation details with messages.
    """
    conn = _get_db_connection()
    cursor = conn.cursor()

    # Get conversation metadata
    cursor.execute("""
        SELECT id, title, created_at, updated_at, message_count
        FROM conversations
        WHERE id = ?
    """, (conversation_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation = {
        "id": row["id"],
        "title": row["title"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "message_count": row["message_count"],
        "messages": [],
    }

    # Get messages
    cursor.execute("""
        SELECT id, role, content, created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY created_at ASC
    """, (conversation_id,))

    for msg_row in cursor.fetchall():
        conversation["messages"].append({
            "id": msg_row["id"],
            "role": msg_row["role"],
            "content": msg_row["content"],
            "created_at": msg_row["created_at"],
        })

    conn.close()
    return conversation


@router.delete("/chat/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation.

    Args:
        conversation_id: The conversation ID.

    Returns:
        Deletion status.
    """
    conn = _get_db_connection()
    cursor = conn.cursor()

    # Check if conversation exists
    cursor.execute("""
        SELECT id FROM conversations WHERE id = ?
    """, (conversation_id,))

    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Delete messages first
    cursor.execute("""
        DELETE FROM messages WHERE conversation_id = ?
    """, (conversation_id,))

    # Delete conversation
    cursor.execute("""
        DELETE FROM conversations WHERE id = ?
    """, (conversation_id,))

    conn.commit()
    conn.close()

    return {"success": True, "message": "Conversation deleted"}


@router.post("/chat/history/save")
async def save_conversation(request: dict):
    """Save or update a conversation.

    Args:
        request: Contains conversation_id, title, and messages.

    Returns:
        Save status.
    """
    conn = _get_db_connection()
    cursor = conn.cursor()

    conversation_id = request.get("conversation_id") or str(uuid4())
    title = request.get("title", "New Conversation")
    messages = request.get("messages", [])

    now = datetime.now().isoformat()

    # Check if conversation exists
    cursor.execute("""
        SELECT id FROM conversations WHERE id = ?
    """, (conversation_id,))

    if cursor.fetchone():
        # Update existing conversation
        cursor.execute("""
            UPDATE conversations
            SET title = ?, updated_at = ?, message_count = ?
            WHERE id = ?
        """, (title, now, len(messages), conversation_id))

        # Clear existing messages
        cursor.execute("""
            DELETE FROM messages WHERE conversation_id = ?
        """, (conversation_id,))
    else:
        # Create new conversation
        cursor.execute("""
            INSERT INTO conversations (id, title, created_at, updated_at, message_count)
            VALUES (?, ?, ?, ?, ?)
        """, (conversation_id, title, now, now, len(messages)))

    # Insert messages
    for msg in messages:
        msg_id = msg.get("id") or str(uuid4())
        cursor.execute("""
            INSERT INTO messages (id, conversation_id, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (msg_id, conversation_id, msg.get("role", "user"), msg.get("content", ""), now))

    conn.commit()
    conn.close()

    return {"success": True, "conversation_id": conversation_id}
