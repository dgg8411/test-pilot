"""执行节点：执行计划中的下一步操作，直接执行工具调用。"""

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.types import Command

from ...tools import ALL_TOOLS
from src.utils import log_step, log_info, log_ok, log_error, log_separator, log_warn
from ...prompts import LOGIN_EXECUTE_PROMPT, APP_EXECUTE_PROMPT
from .route_node import LoginState
from ...llm import build_llm, build_structured_llm
from ...schemas import ExecuteResult

MAX_STEPS = 25  # 最大执行步骤数，防止无限循环

# 构建 工具名 → 工具函数 的映射
_TOOL_MAP = {t.name: t for t in ALL_TOOLS}


def _check_captcha_redirect(response, step: int, state: LoginState) -> Command | None:
    """检查 LLM 是否请求跳转验证码子图。

    LLM 通过调用 solve_captcha_subgraph(captcha_input_ref) 工具触发跳转。
    如果检测到该工具调用，返回 Command(goto="captcha")，否则返回 None。

    防护：检查消息历史中是否已有验证码子图结果（含 [验证码子图结果]），
    如有则拦截重复调用，从 tool_calls 中移除 solve_captcha_subgraph。
    """
    if not hasattr(response, "tool_calls") or not response.tool_calls:
        return None

    for tc in response.tool_calls:
        if tc["name"] == "solve_captcha_subgraph":
            # 防护：检查消息历史中是否已有验证码子图结果
            already_solved = False
            for i, m in enumerate(state["messages"]):
                content = getattr(m, "content", "")
                if not isinstance(content, str):
                    content = str(content) if content else ""
                if "[验证码子图结果]" in content and "已自动识别并填写完成" in content:
                    already_solved = True
                    log_info(f"[CAPTCHA] 防护命中: messages[{i}] 含验证码子图结果")
                    break
            log_info(f"[CAPTCHA] 防护检查: messages={len(state['messages'])}, already_solved={already_solved}")
            if already_solved:
                log_warn("[CAPTCHA] 验证码子图已执行过（消息历史中有结果），忽略重复调用")
                response.tool_calls = [
                    t for t in response.tool_calls if t["name"] != "solve_captcha_subgraph"
                ]
                if not response.tool_calls:
                    response.content = response.content or "验证码已自动填写完成，继续执行下一步操作。"
                return None

            captcha_ref = tc.get("args", {}).get("captcha_input_ref", "")
            log_info(f"[CAPTCHA] LLM 请求跳转验证码子图, ref={captcha_ref}")
            return Command(
                goto="captcha",
                update={
                    "captcha_input_ref": captcha_ref,
                    "messages": [AIMessage(content=f"跳转验证码子图，验证码输入框 ref={captcha_ref}")],
                    "step_index": step + 1,
                },
            )
    return None


def _execute_tool_calls(response) -> list[ToolMessage]:
    """直接执行 LLM 返回的工具调用，返回 ToolMessage 列表。"""
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


def execute_node(state: LoginState) -> dict | Command:
    """执行计划中的下一步操作。根据用例类型选择不同的 prompt。

    LLM 返回工具调用后，直接在 execute_node 中执行工具，
    不再经过 ToolNode，简化 graph 结构。
    """
    step = state["step_index"]

    if step >= MAX_STEPS:
        log_error(f"已达到最大步骤数 {MAX_STEPS}，强制结束")
        return {"done": True, "result": f"FAILURE: 超过最大步骤数 {MAX_STEPS}"}

    log_separator("-")
    log_step("EXECUTE", f"执行第 {step + 1} 步 (上限 {MAX_STEPS})")
    log_info(f"captcha_input_ref={state.get('captcha_input_ref', '')}")

    llm = build_llm()
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    expected = state["test_case"].get("expected", "")
    steps = state["test_case"].get("steps", [])
    steps_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
    is_login = state.get("is_login_case", True)

    # 根据用例类型选择 prompt
    prompt_template = LOGIN_EXECUTE_PROMPT if is_login else APP_EXECUTE_PROMPT

    prompt = prompt_template.format(
        steps=steps_text,
        expected=expected,
        url=state["url"],
        current_step=steps[step] if step < len(steps) else "（已完成所有步骤）",
    )

    response = llm_with_tools.invoke(
        state["messages"] + [HumanMessage(content=prompt)]
    )

    # 检查是否请求跳转验证码子图
    redirect = _check_captcha_redirect(response, step, state)
    if redirect:
        return redirect

    # 防护可能已从 tool_calls 中移除 solve_captcha_subgraph
    # 如果移除后 tool_calls 为空，构造不含 tool_calls 的 AIMessage
    if hasattr(response, "tool_calls") and not response.tool_calls and response.content:
        return {
            "messages": [AIMessage(content=response.content)],
            "step_index": step + 1,
        }

    # 直接执行工具调用
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_messages = _execute_tool_calls(response)
        return {
            "messages": [response] + tool_messages,
            "step_index": step + 1,
        }

    # 没有工具调用，检查是否成功/失败（用结构化输出判定收尾状态）
    content = response.content.strip()
    log_info(f"LLM 回复: {content[:300]}")

    status_llm = build_structured_llm(ExecuteResult)
    status_result: ExecuteResult = status_llm.invoke([
        SystemMessage(content="你是执行状态判定器。必须只输出一个 JSON 对象，格式为 {\"status\": \"SUCCESS\" 或 \"FAILURE\" 或 \"CONTINUE\", \"reason\": \"原因说明\"}，不要输出 markdown、解释或其他文字。"),
        HumanMessage(content=(
            "根据以下执行内容，判断测试状态是 SUCCESS（成功）、FAILURE（失败）还是 CONTINUE（继续）。\n\n"
            f"执行内容：\n{content}"
        ))
    ])

    if status_result.status == "SUCCESS":
        log_ok(f"执行成功: {status_result.reason[:200]}")
        return {"messages": [response], "step_index": step + 1, "done": True, "result": "SUCCESS"}
    elif status_result.status == "FAILURE":
        log_error(f"执行失败: {status_result.reason[:200]}")
        return {"messages": [response], "step_index": step + 1, "done": True, "result": f"FAILURE: {status_result.reason}"}

    return {
        "messages": [response],
        "step_index": step + 1,
    }
