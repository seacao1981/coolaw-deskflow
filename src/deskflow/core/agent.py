"""Agent main controller - the central orchestrator of DeskFlow."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from deskflow.core.models import (
    Conversation,
    MemoryEntry,
    Message,
    Role,
    StreamChunk,
    ToolCall,
    ToolCallStatus,
    ToolResult,
)
from deskflow.core.prompt_assembler import PromptAssembler
from deskflow.core.ralph import RalphLoop
from deskflow.core.task_monitor import TaskMonitor
from deskflow.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from deskflow.core.protocols import (
        BrainProtocol,
        IdentityProtocol,
        MemoryProtocol,
        ToolRegistryProtocol,
    )
    from deskflow.skills.registry import SkillRegistry

logger = get_logger(__name__)
MAX_TOOL_ROUNDS = 10


class Agent:
    """Main agent controller that orchestrates all components."""

    def __init__(
        self,
        brain: BrainProtocol,
        memory: MemoryProtocol,
        tools: ToolRegistryProtocol,
        identity: IdentityProtocol,
        monitor: TaskMonitor | None = None,
        skill_registry: SkillRegistry | None = None,
    ) -> None:
        self._brain = brain
        self._memory = memory
        self._tools = tools
        self._identity = identity
        self._monitor = monitor or TaskMonitor()
        self._prompt_assembler = PromptAssembler(
            identity=identity,
            memory=memory,
            brain=brain,
        )
        self._ralph = RalphLoop(max_retries=2)
        self._conversations: dict[str, Conversation] = {}
        self._cancel_requested = False
        self._skill_registry = skill_registry

    @property
    def skill_registry(self) -> SkillRegistry | None:
        """Get the skill registry."""
        return self._skill_registry

    def cancel(self) -> None:
        self._cancel_requested = True
        self._ralph.cancel()

    def _get_or_create_conversation(self, conversation_id: str | None = None) -> Conversation:
        if conversation_id and conversation_id in self._conversations:
            return self._conversations[conversation_id]
        conv = Conversation()
        self._conversations[conv.id] = conv
        return conv

    async def _load_conversation_history(self, conversation_id: str | None = None) -> list[Message]:
        if not conversation_id:
            return []
        try:
            import sqlite3
            from pathlib import Path
            db_path = Path.cwd() / "data" / "conversations.db"
            if not db_path.exists():
                return []
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at ASC", (conversation_id,))
            rows = cursor.fetchall()
            messages = []
            for row in rows:
                msg = Message(id=row["id"], role=Role(row["role"]), content=row["content"], created_at=float(row["created_at"]))
                messages.append(msg)
            conn.close()
            return messages
        except Exception as e:
            logger.warning("conversation_load_failed", error=str(e))
            return []

    async def _save_conversation(self, conversation_id: str, conversation: Conversation) -> None:
        try:
            import sqlite3
            from pathlib import Path
            db_path = Path.cwd() / "data" / "conversations.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            now = time.time()
            cursor.execute("SELECT id FROM conversations WHERE id = ?", (conversation_id,))
            if cursor.fetchone():
                cursor.execute("UPDATE conversations SET updated_at = ?, message_count = ? WHERE id = ?", (now, len(conversation.messages), conversation_id))
                cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            else:
                cursor.execute("INSERT INTO conversations (id, title, created_at, updated_at, message_count) VALUES (?, ?, ?, ?, ?)", (conversation_id, conversation.title or "Untitled", conversation.created_at, now, len(conversation.messages)))
            for msg in conversation.messages:
                cursor.execute("INSERT OR REPLACE INTO messages (id, conversation_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)", (msg.id, conversation_id, msg.role.value, msg.content, msg.timestamp))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("conversation_save_failed", error=str(e))

    async def _store_interaction_memory(self, user_message: str, assistant_response: str, conversation_id: str) -> None:
        try:
            if not self._memory:
                return
            entry = MemoryEntry(
                content=f"User: {user_message}\nAssistant: {assistant_response}",
                memory_type="episodic",
                metadata={"user_message": user_message, "assistant_response": assistant_response, "source_conversation_id": conversation_id}
            )
            await self._memory.store(entry)
        except Exception as e:
            logger.warning("memory_store_failed", error=str(e))

    async def _execute_tool_calls(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        results: list[ToolResult] = []
        for tc in tool_calls:
            start = time.time()
            tc.status = ToolCallStatus.RUNNING
            logger.info("tool_executing", tool_name=tc.name, args=tc.arguments)
            try:
                result = await self._tools.execute(tc.name, tc.arguments)
                result.tool_call_id = tc.id
                tc.status = ToolCallStatus.COMPLETED
            except Exception as e:
                result = ToolResult(tool_call_id=tc.id, tool_name=tc.name, success=False, error=str(e))
                tc.status = ToolCallStatus.FAILED
                logger.warning("tool_execution_failed", tool_name=tc.name, error=str(e))
            duration_ms = (time.time() - start) * 1000
            result.duration_ms = duration_ms
            results.append(result)
            self._monitor.record_tool_call(tool_name=tc.name, duration_ms=duration_ms, success=result.success)
            self._track_tool_execution(tc.name, tc.arguments, result)
        return results

    def _track_tool_execution(self, tool_name: str, arguments: dict, result: ToolResult) -> None:
        if not self._memory:
            return
        if tool_name not in ("shell", "file"):
            return
        try:
            if hasattr(self._memory, "add_recent_entity"):
                cmd = arguments.get("command", "") if tool_name == "shell" else ""
                if "mkdir" in cmd:
                    parts = cmd.split("mkdir -p ")
                    if len(parts) > 1:
                        folder_path = parts[1].strip()
                        self._memory.add_recent_entity(entity_type="folder", name=folder_path.split("/")[-1], location=folder_path, action="created")
                elif "rm -rf" in cmd or "rm -r" in cmd:
                    parts = cmd.split("rm -rf ") if "rm -rf" in cmd else cmd.split("rm -r ")
                    if len(parts) > 1:
                        folder_path = parts[1].strip()
                        self._memory.add_recent_entity(entity_type="folder", name=folder_path.split("/")[-1], location=folder_path, action="deleted")
        except Exception as e:
            logger.warning("track_tool_execution_failed", error=str(e))

    async def chat(self, user_message: str, conversation_id: str | None = None) -> Message:
        self._cancel_requested = False
        self._monitor.set_busy("chatting")
        try:
            await self._load_conversation_history(conversation_id)
            conversation = self._get_or_create_conversation(conversation_id)

            # Record new conversation
            self._monitor.record_conversation()

            tool_definitions = self._tools.list_tools()
            messages = await self._prompt_assembler.assemble(user_message=user_message, tools=tool_definitions if tool_definitions else None, conversation_messages=conversation.messages)
            full_response_text = ""
            all_tool_calls: list[ToolCall] = []
            tool_round = 0
            while tool_round < MAX_TOOL_ROUNDS:
                if self._cancel_requested:
                    return Message(role=Role.ASSISTANT, content="[Cancelled by user]")
                response = await self._brain.chat(messages=messages, tools=tool_definitions if tool_definitions else None)
                if not response.tool_calls:
                    full_response_text += response.content
                    break
                tool_results = await self._execute_tool_calls(response.tool_calls)
                all_tool_calls.extend(response.tool_calls)
                messages.append(response)
                for result in tool_results:
                    tool_msg = Message(role=Role.TOOL, content=result.output if result.success else f"Error: {result.error}", tool_call_id=result.tool_call_id)
                    messages.append(tool_msg)
                tool_round += 1
            user_msg = Message(role=Role.USER, content=user_message)
            response_msg = Message(role=Role.ASSISTANT, content=full_response_text, tool_calls=all_tool_calls)
            conversation.add_message(user_msg)
            conversation.add_message(response_msg)
            if conversation_id:
                await self._save_conversation(conversation_id, conversation)
            await self._store_interaction_memory(user_message, full_response_text, conversation.id)
            return response_msg
        finally:
            self._monitor.set_idle()

    async def stream_chat(self, user_message: str, conversation_id: str | None = None) -> AsyncIterator[StreamChunk]:
        """Stream chat response with tool execution support."""
        self._cancel_requested = False
        self._monitor.set_busy("streaming chat")
        try:
            await self._load_conversation_history(conversation_id)
            conversation = self._get_or_create_conversation(conversation_id)

            # Record new conversation
            self._monitor.record_conversation()

            tool_definitions = self._tools.list_tools()

            yield StreamChunk(type="conversation_id", content=conversation.id)

            messages = await self._prompt_assembler.assemble(
                user_message=user_message,
                tools=tool_definitions if tool_definitions else None,
                conversation_messages=conversation.messages,
            )

            full_response_text = ""
            all_tool_calls: list[ToolCall] = []
            tool_round = 0

            # Track messages for conversation storage
            conversation_messages: list[Message] = []

            while tool_round < MAX_TOOL_ROUNDS:
                if self._cancel_requested:
                    yield StreamChunk(type="text", content="\n[Cancelled by user]")
                    yield StreamChunk(type="done")
                    return

                pending_tool_calls: list[ToolCall] = []
                round_text = ""

                try:
                    async for chunk in self._brain.stream(messages=messages, tools=tool_definitions if tool_definitions else None):
                        if chunk.type == "text":
                            round_text += chunk.content
                            full_response_text += chunk.content
                            yield chunk
                        elif chunk.type == "tool_calls":
                            pending_tool_calls.extend(chunk.tool_calls)
                        elif chunk.type == "done":
                            break

                    if not pending_tool_calls:
                        break

                    # Execute tools
                    tool_results = await self._execute_tool_calls(pending_tool_calls)
                    all_tool_calls.extend(pending_tool_calls)

                    # Add assistant message with tool calls
                    assistant_msg = Message(
                        role=Role.ASSISTANT,
                        content=round_text,
                        tool_calls=pending_tool_calls,
                    )
                    conversation_messages.append(assistant_msg)

                    # Add tool results
                    for result in tool_results:
                        tool_msg = Message(
                            role=Role.TOOL,
                            content=result.output if result.success else f"Error: {result.error}",
                            tool_call_id=result.tool_call_id,
                        )
                        messages.append(tool_msg)

                    tool_round += 1
                    pending_tool_calls = []
                    round_text = ""

                except Exception as e:
                    logger.error("stream_chat_error", error=str(e))
                    yield StreamChunk(type="error", content=str(e))
                    break

            # Add final messages
            if full_response_text or all_tool_calls:
                response_msg = Message(
                    role=Role.ASSISTANT,
                    content=full_response_text,
                    tool_calls=all_tool_calls,
                )
                conversation.add_message(Message(role=Role.USER, content=user_message))
                conversation.add_message(response_msg)

                if conversation_id:
                    await self._save_conversation(conversation_id, conversation)
                await self._store_interaction_memory(user_message, full_response_text, conversation.id)

            yield StreamChunk(type="done")

        finally:
            self._monitor.set_idle()
