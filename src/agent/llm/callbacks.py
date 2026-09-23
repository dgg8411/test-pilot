"""LangChain CallbackHandler，记录 LLM 调用日志到文件和命令行。"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.outputs import LLMResult

from src.utils import log_info, log_warn, log_error, _log_to_file


def _format_message(msg: Any, max_len: int = 500) -> str:
    """格式化单条消息的摘要。"""
    role = type(msg).__name__
    content = ""

    if isinstance(msg, HumanMessage):
        content = str(msg.content)[:max_len]
    elif isinstance(msg, AIMessage):
        content = str(msg.content)[:max_len]
        if msg.tool_calls:
            calls = []
            for tc in msg.tool_calls:
                args_str = str(tc.get("args", {}))[:100]
                calls.append(f"{tc['name']}({args_str})")
            content += f" [tool_calls: {', '.join(calls)}]"
    elif isinstance(msg, SystemMessage):
        content = str(msg.content)[:max_len]
    elif isinstance(msg, ToolMessage):
        content = str(msg.content)[:max_len]
    else:
        content = str(msg.content)[:max_len]

    return f"[{role}] {content}"


class LLMLoggerHandler(BaseCallbackHandler):
    """记录 LLM 调用的输入、输出、token 使用量到日志。"""

    def __init__(self):
        super().__init__()
        self._call_id_map: Dict[str, dict] = {}

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[Any]],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """ChatModel 调用开始时记录输入消息明细。"""
        model_name = metadata.get("model_name", "unknown") if metadata else "unknown"
        if model_name == "unknown":
            model_name = serialized.get("name", "unknown")

        msg_list = messages[0] if messages else []
        msg_count = len(msg_list)

        self._call_id_map[str(run_id)] = {
            "model": model_name,
            "msg_count": msg_count,
        }

        log_info(f"[LLM] === 请求开始 === 模型: {model_name}, 消息数: {msg_count}")

        # 记录每条输入消息
        for i, msg in enumerate(msg_list):
            summary = _format_message(msg)
            log_info(f"[LLM]   输入消息[{i}]: {summary}")

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """LLM（非 ChatModel）调用开始时记录。"""
        model_name = metadata.get("model_name", "unknown") if metadata else "unknown"
        if model_name == "unknown":
            model_name = serialized.get("name", "unknown")

        self._call_id_map[str(run_id)] = {
            "model": model_name,
            "msg_count": len(prompts),
        }

        log_info(f"[LLM] === 请求开始 === 模型: {model_name}, prompts: {len(prompts)}")
        for i, prompt in enumerate(prompts):
            log_info(f"[LLM]   输入prompt[{i}]: {prompt[:500]}")

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """LLM 调用结束时记录 token 使用量和输出明细。"""
        call_info = self._call_id_map.pop(str(run_id), {})
        model_name = call_info.get("model", "unknown")

        # 提取 token 使用量
        token_usage = {}
        if response.llm_output:
            usage = response.llm_output.get("token_usage") or response.llm_output.get("usage")
            if usage:
                token_usage = {
                    "prompt_tokens": usage.get("prompt_tokens", usage.get("input_tokens", 0)),
                    "completion_tokens": usage.get("completion_tokens", usage.get("output_tokens", 0)),
                    "total_tokens": usage.get("total_tokens", 0),
                }

        # 提取输出内容
        output_text = ""
        tool_calls_info = []
        if response.generations and response.generations[0]:
            gen = response.generations[0][0]
            if hasattr(gen, "message") and gen.message:
                output_text = gen.message.content or ""
                if hasattr(gen.message, "tool_calls") and gen.message.tool_calls:
                    for tc in gen.message.tool_calls:
                        tool_calls_info.append({
                            "name": tc["name"],
                            "args": tc.get("args", {}),
                            "id": tc.get("id", ""),
                        })

        # 命令行输出：token 摘要
        if token_usage:
            log_info(
                f"[LLM] === 响应结束 === {model_name} | "
                f"输入: {token_usage['prompt_tokens']} tokens | "
                f"输出: {token_usage['completion_tokens']} tokens | "
                f"总计: {token_usage['total_tokens']} tokens"
            )
        else:
            log_info(f"[LLM] === 响应结束 === {model_name}")

        # 命令行 + 文件日志：输出明细
        if output_text:
            log_info(f"[LLM] 输出文本: {output_text[:500]}")

        if tool_calls_info:
            for tc in tool_calls_info:
                args_str = str(tc["args"])[:200]
                log_info(f"[LLM] 输出工具调用: {tc['name']}({args_str})")

        # 文件日志：完整响应元数据
        if token_usage:
            _log_to_file("INFO", f"[LLM] Token 明细: {token_usage}")

        # 记录 finish_reason
        if response.generations and response.generations[0]:
            gen = response.generations[0][0]
            if hasattr(gen, "generation_info") and gen.generation_info:
                finish_reason = gen.generation_info.get("finish_reason", "unknown")
                log_info(f"[LLM] finish_reason: {finish_reason}")

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """LLM 调用出错时记录。"""
        call_info = self._call_id_map.pop(str(run_id), {})
        model_name = call_info.get("model", "unknown")
        log_error(f"[LLM] {model_name} 调用失败: {error}")
        _log_to_file("ERROR", f"[LLM] {model_name} 调用失败: {error}")
