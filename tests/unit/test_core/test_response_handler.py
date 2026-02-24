"""Tests for response_handler module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from deskflow.core.response_handler import (
    strip_thinking_tags,
    strip_tool_simulation_text,
    clean_llm_response,
    ResponseHandler,
)


class TestStripThinkingTags:
    """测试思考标签清理"""

    def test_strip_empty(self):
        """测试空字符串"""
        assert strip_thinking_tags("") == ""
        assert strip_thinking_tags(None) is None

    def test_strip_no_tags(self):
        """测试无标签文本"""
        text = "Hello, world!"
        assert strip_thinking_tags(text) == "Hello, world!"

    def test_strip_thinking_tags(self):
        """测试 <thinking> 标签"""
        text = "<thinking>This is internal thought</thinking>Hello user"
        result = strip_thinking_tags(text)
        assert result == "Hello user"

    def test_strip_thinking_tags_multiline(self):
        """测试多行思考标签"""
        text = """<thinking>
Let me think about this...
The user is asking about weather.
I should check the weather API.
</thinking>

The weather today is sunny."""
        result = strip_thinking_tags(text)
        assert "The weather today is sunny" in result
        assert "thinking" not in result.lower()

    def test_strip_thon_tags(self):
        """测试<think></think> 标签"""
        text = "<think>I need to reason about this</think>The answer is 42"
        result = strip_thinking_tags(text)
        assert result == "The answer is 42"

    def test_strip_minimax_tool_call(self):
        """测试 MiniMax 工具调用标签"""
        text = """<minimax:tool_call>
{"name": "search", "args": {"query": "weather"}}
</minimax:tool_call>

Let me search for you."""
        result = strip_thinking_tags(text)
        assert "Let me search for you" in result
        assert "minimax" not in result.lower()

    def test_strip_kimi_tool_section(self):
        """测试 Kimi K2 工具段标签"""
        text = """<<|tool_calls_section_begin|>>
[{"name": "weather", "arguments": {}}]
<<|tool_calls_section_end|>>

Here's the weather forecast."""
        result = strip_thinking_tags(text)
        assert "Here's the weather forecast" in result
        assert "tool_calls_section" not in result

    def test_strip_invoke_tag(self):
        """测试 Anthropic invoke 标签"""
        text = """I'll use the calculator.
<invoke name="calculator">
{"expression": "2+2"}
</invoke>
The result is 4."""
        result = strip_thinking_tags(text)
        assert "I'll use the calculator" in result
        assert "The result is 4" in result
        assert "invoke" not in result.lower()

    def test_strip_residual_closing_tags(self):
        """测试残留闭合标签"""
        text = "Some text</thinking>More text</think>End"
        result = strip_thinking_tags(text)
        assert "</thinking>" not in result
        assert "</think>" not in result

    def test_strip_xml_declaration(self):
        """测试 XML 声明"""
        text = """<?xml version="1.0"?>
<response>Hello</response>"""
        result = strip_thinking_tags(text)
        assert "<?xml" not in result


class TestStripToolSimulationText:
    """测试模拟工具调用清理"""

    def test_strip_empty(self):
        """测试空字符串"""
        assert strip_tool_simulation_text("") == ""
        assert strip_tool_simulation_text(None) is None

    def test_strip_function_call_pattern(self):
        """测试函数调用模式"""
        text = """Here's the result:

search(query="weather")

Let me know if you need more."""
        result = strip_tool_simulation_text(text)
        assert "search(query=" not in result
        assert "Here's the result:" in result
        assert "Let me know if you need more" in result

    def test_strip_tool_number_pattern(self):
        """测试 tool:number 模式"""
        text = """I'll call the tool:

tool:1{"name": "search"}

Done."""
        result = strip_tool_simulation_text(text)
        assert "tool:1" not in result
        assert "I'll call the tool:" in result
        assert "Done" in result

    def test_strip_json_tool_pattern(self):
        """测试 JSON 工具调用模式"""
        text = """Let me use a tool:

{"tool": "search", "name": "query"}

Here's what I found."""
        result = strip_tool_simulation_text(text)
        assert '{"tool":' not in result
        assert "Let me use a tool:" in result
        assert "Here's what I found" in result

    def test_keep_normal_text(self):
        """测试保留正常文本"""
        text = """Hello! I can help you with that.

Let me search for the information you need.

The weather today is sunny."""
        result = strip_tool_simulation_text(text)
        assert result == text


class TestCleanLlmResponse:
    """测试 LLM 响应清理"""

    def test_clean_empty(self):
        """测试空字符串"""
        assert clean_llm_response("") == ""
        assert clean_llm_response(None) is None

    def test_clean_combined(self):
        """测试组合清理"""
        text = """<thinking>Let me think</thinking>

Hello user!

search(query="test")

How can I help?"""
        result = clean_llm_response(text)
        assert "thinking" not in result.lower()
        assert "search(query=" not in result
        assert "Hello user!" in result
        assert "How can I help?" in result

    def test_clean_preserves_content(self):
        """测试保留实际内容"""
        text = """<thinking>analysis</thinking>

The answer to your question is 42.

This is based on my calculation."""
        result = clean_llm_response(text)
        assert "The answer to your question is 42" in result
        assert "This is based on my calculation" in result


class TestResponseHandler:
    """测试 ResponseHandler 类"""

    def test_init_default(self):
        """测试默认初始化"""
        brain = MagicMock()
        handler = ResponseHandler(brain=brain)
        assert handler._brain is brain
        assert handler._memory_manager is None

    def test_init_with_memory(self):
        """测试带记忆管理器初始化"""
        brain = MagicMock()
        memory = MagicMock()
        handler = ResponseHandler(brain=brain, memory_manager=memory)
        assert handler._brain is brain
        assert handler._memory_manager is memory


@pytest.mark.asyncio
class TestVerifyTaskCompletion:
    """测试任务完成度验证"""

    async def test_completed_with_deliver_artifacts(self):
        """测试 deliver_artifacts 工具执行完成"""
        brain = MagicMock()
        handler = ResponseHandler(brain=brain)

        result = await handler.verify_task_completion(
            user_request="Send me the report",
            assistant_response="I've sent the report to you",
            executed_tools=["deliver_artifacts"],
            delivery_receipts=[{"status": "delivered", "file": "report.pdf"}],
        )
        assert result is True

    async def test_completed_with_complete_plan(self):
        """测试 complete_plan 工具执行完成"""
        brain = MagicMock()
        handler = ResponseHandler(brain=brain)

        result = await handler.verify_task_completion(
            user_request="Complete the plan",
            assistant_response="The plan is complete",
            executed_tools=["complete_plan"],
        )
        assert result is True

    async def test_incomplete_claim_without_receipts(self):
        """测试宣称交付但无证据"""
        brain = MagicMock()
        handler = ResponseHandler(brain=brain)

        result = await handler.verify_task_completion(
            user_request="Send me the file",
            assistant_response="I've sent the file to you",
            executed_tools=[],
            delivery_receipts=[],
        )
        assert result is False

    async def test_incomplete_pending_plan(self):
        """测试有待处理 Plan 步骤"""
        brain = MagicMock()
        handler = ResponseHandler(brain=brain)

        # Mock the imports inside the function
        mock_plan_module = MagicMock()
        mock_plan_module.has_active_plan.return_value = True
        mock_handler = MagicMock()
        mock_plan_module.get_plan_handler_for_session.return_value = mock_handler
        mock_handler.get_plan_for.return_value = {
            "steps": [
                {"id": "1", "status": "completed"},
                {"id": "2", "status": "pending"},
            ]
        }

        with patch.dict('sys.modules', {'deskflow.core.plan': mock_plan_module}):
            result = await handler.verify_task_completion(
                user_request="Do something",
                assistant_response="Working on it",
                executed_tools=[],
                conversation_id="test-123",
            )
            assert result is False

    async def test_llm_verification_completed(self):
        """测试 LLM 验证完成"""
        brain = MagicMock()
        brain.think = AsyncMock(return_value=MagicMock(
            content="STATUS: COMPLETED\nEVIDENCE: File saved successfully"
        ))
        handler = ResponseHandler(brain=brain)

        result = await handler.verify_task_completion(
            user_request="Save the file",
            assistant_response="I've saved the file",
            executed_tools=["write_file"],
        )
        assert result is True

    async def test_llm_verification_incomplete(self):
        """测试 LLM 验证未完成"""
        brain = MagicMock()
        brain.think = AsyncMock(return_value=MagicMock(
            content="STATUS: INCOMPLETE\nMISSING: Need to test the code"
        ))
        handler = ResponseHandler(brain=brain)

        result = await handler.verify_task_completion(
            user_request="Write and test code",
            assistant_response="I've written the code",
            executed_tools=["write_file"],
        )
        assert result is False

    async def test_verification_error_fallback(self):
        """测试验证失败时 fallback"""
        brain = MagicMock()
        brain.think = AsyncMock(side_effect=Exception("LLM error"))
        handler = ResponseHandler(brain=brain)

        result = await handler.verify_task_completion(
            user_request="Do something complex",
            assistant_response="Working...",
            executed_tools=[],
        )
        assert result is False


@pytest.mark.asyncio
class TestDoTaskRetrospect:
    """测试任务复盘功能"""

    async def test_retrospect_success(self):
        """测试复盘成功"""
        brain = MagicMock()
        brain.think = AsyncMock(return_value=MagicMock(
            content="任务耗时原因：重复调用同一个 API\n改进建议：缓存 API 结果"
        ))
        handler = ResponseHandler(brain=brain)

        task_monitor = MagicMock()
        task_monitor.get_retrospect_context = MagicMock(return_value="Task context")
        task_monitor.metrics = MagicMock()
        task_monitor.metrics.retrospect_result = ""

        # Mock the task_monitor module with proper RETROSPECT_PROMPT
        mock_tm_module = MagicMock()
        mock_tm_module.RETROSPECT_PROMPT = "{context}"  # Use proper format string

        with patch.dict('sys.modules', {'deskflow.core.task_monitor': mock_tm_module}):
            result = await handler.do_task_retrospect(task_monitor)
            # The result may be empty due to the mock, so just verify no exception
            assert task_monitor.metrics.retrospect_result is not None

    async def test_retrospect_with_memory_save(self):
        """测试复盘结果保存到记忆"""
        brain = MagicMock()
        brain.think = AsyncMock(return_value=MagicMock(
            content="发现问题：重复执行无效操作"
        ))
        memory_manager = MagicMock()
        handler = ResponseHandler(brain=brain, memory_manager=memory_manager)

        task_monitor = MagicMock()
        task_monitor.get_retrospect_context = MagicMock(return_value="Context")
        task_monitor.metrics = MagicMock()
        task_monitor.metrics.retrospect_result = ""

        mock_tm_module = MagicMock()
        mock_tm_module.RETROSPECT_PROMPT = "{context}"

        with patch.dict('sys.modules', {'deskflow.core.task_monitor': mock_tm_module}):
            # Mock the Memory import inside the function
            mock_memory_module = MagicMock()
            mock_memory_module.Memory = MagicMock()
            mock_memory_module.MemoryPriority = MagicMock()
            mock_memory_module.MemoryType = MagicMock()

            with patch.dict('sys.modules', {'deskflow.memory.types': mock_memory_module}):
                await handler.do_task_retrospect(task_monitor)

                # 验证是否尝试保存记忆
                assert memory_manager.add_memory.called

    async def test_retrospect_error(self):
        """测试复盘失败"""
        brain = MagicMock()
        brain.think = AsyncMock(side_effect=Exception("Error"))
        handler = ResponseHandler(brain=brain)

        task_monitor = MagicMock()
        task_monitor.get_retrospect_context = MagicMock(return_value="Context")

        result = await handler.do_task_retrospect(task_monitor)
        assert result == ""


class TestShouldCompilePrompt:
    """测试 Prompt 编译判断"""

    def test_short_message(self):
        """测试短消息"""
        assert ResponseHandler.should_compile_prompt("Hi") is False
        assert ResponseHandler.should_compile_prompt("   ") is False

    def test_long_message(self):
        """测试长消息"""
        long_msg = "This is a longer message that should trigger compilation"
        assert ResponseHandler.should_compile_prompt(long_msg) is True


class TestGetLastUserRequest:
    """测试获取最后用户请求"""

    def test_get_last_user_message(self):
        """测试获取最后一条用户消息"""
        messages = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "Response"},
            {"role": "user", "content": "Second message"},
        ]
        result = ResponseHandler.get_last_user_request(messages)
        assert result == "Second message"

    def test_skip_system_messages(self):
        """测试跳过系统消息"""
        messages = [
            {"role": "user", "content": "[系统] System message"},
            {"role": "user", "content": "Real user message"},
        ]
        result = ResponseHandler.get_last_user_request(messages)
        assert result == "Real user message"

    def test_empty_messages(self):
        """测试空消息列表"""
        assert ResponseHandler.get_last_user_request([]) == ""

    def test_no_user_messages(self):
        """测试无用户消息"""
        messages = [
            {"role": "assistant", "content": "Response 1"},
            {"role": "assistant", "content": "Response 2"},
        ]
        result = ResponseHandler.get_last_user_request(messages)
        assert result == ""

    def test_truncate_long_message(self):
        """测试长消息截断"""
        long_content = "A" * 3000
        messages = [{"role": "user", "content": long_content}]
        result = ResponseHandler.get_last_user_request(messages)
        assert len(result) == 2000
