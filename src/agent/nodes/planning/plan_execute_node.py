"""Planning 模式的 execute 节点：用 LLM 绑定工具，执行 plan 中当前步骤的操作。

每次只执行当前 1 步（plan[step_index]），执行完 step_index + 1 推进一步，
由 route / verify 节点决定下一步去向。

LLM 通过 bind_tools 直接产生工具调用，不再解析纯文本格式。
"""

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from ...tools import ALL_TOOLS
from ...prompts import PLAN_EXECUTE_PROMPT
from ...llm import build_llm
from src.utils import log_step, log_info, log_ok, log_error, log_separator
from .plan_replan_node import PlanState

MAX_STEPS = 25

# 工具名 → 工具函数（排除验证码子图工具，由 route 节点处理）
_TOOL_MAP = {t.name: t for t in ALL_TOOLS if t.name != "solve_captcha_subgraph"}


def _execute_tool_calls(response) -> list[ToolMessage]:
    """执行 LLM 返回的工具调用，返回 ToolMessage 列表。"""
    tool_messages = []
    for tc in response.tool_calls:
        tool_name = tc["name"]
        tool_args = tc["args"]
        log_info(f"调用工具: {tool_name}({tool_args})")

        if tool_name not in _TOOL_MAP:
            tool_messages.append(ToolMessage(
                content=f"错误: 未知工具 {tool_name}",
                tool_call_id=tc["id"],
            ))
            continue

        try:
            result = _TOOL_MAP[tool_name].invoke(tool_args)
            log_ok(f"工具执行完成: {str(result)[:200]}")
            tool_messages.append(ToolMessage(
                content=str(result),
                tool_call_id=tc["id"],
            ))
        except Exception as e:
            log_error(f"工具 {tool_name} 执行失败: {e}")
            tool_messages.append(ToolMessage(
                content=f"工具执行失败: {e}",
                tool_call_id=tc["id"],
            ))
    return tool_messages


def plan_execute_node(state: PlanState) -> dict:
    """执行 plan 中当前 1 步的操作，通过 LLM 绑定工具直接调用工具。

    完成后 step_index + 1，由后续 route/verify 节点决定去向。
    """
    step = state["step_index"]

    if step >= MAX_STEPS:
        log_error(f"已达到最大步骤数 {MAX_STEPS}，强制结束")
        return {"result": f"FAILURE: 超过最大步骤数 {MAX_STEPS}"}

    log_separator("-")
    log_step("EXECUTE", f"执行第 {step + 1} 步 (上限 {MAX_STEPS})")

    plan = state.get("plan", [])
    if step >= len(plan):
        log_error(f"步骤 {step + 1} 超出计划范围 ({len(plan)} 步)")
        return {
            "messages": [AIMessage(content=f"[EXECUTE] 步骤超出计划范围")],
            "step_index": step + 1,
        }

    current_step = plan[step].strip()
    log_info(f"当前步骤: {current_step}")

    llm = build_llm()
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    prompt = PLAN_EXECUTE_PROMPT.format(
        plan=current_step,
        url=state["url"],
    )

    response = llm_with_tools.invoke(
        state["messages"] + [HumanMessage(content=prompt)]
    )

    # LLM 未产生工具调用，仅记录回复
    if not hasattr(response, "tool_calls") or not response.tool_calls:
        log_info(f"LLM 回复（无工具调用）: {str(response.content)[:300]}")
        return {
            "messages": [response],
            "step_index": step + 1,
        }

    # 执行工具调用
    tool_messages = _execute_tool_calls(response)
    return {
        "messages": [response] + tool_messages,
        "step_index": step + 1,
    }
