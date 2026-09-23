"""Planning 模式的验证节点：execute/captcha 完成后验证结果，直接路由。

路由：
- SUCCESS → END
- CONTINUE（步骤未完成）→ route 继续执行下一步
- FAILURE → plan 重新规划
"""

from langgraph.graph import END
from langgraph.types import Command

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from src.utils import log_step, log_info, log_ok, log_error, log_separator
from ...llm import build_structured_llm
from ...prompts import PLAN_VERIFY_PROMPT
from ...schemas import VerifyResult
from ...tools.browser import _run_cli
from .plan_replan_node import PlanState
from .plan_execute_node import MAX_STEPS


def plan_verify_node(state: PlanState) -> Command:
    """验证节点：execute/captcha 执行后验证结果，直接路由。

    每次都获取页面状态，让 LLM 判断：
    - SUCCESS → END
    - CONTINUE → route（继续执行下一步）
    - FAILURE → plan（重新规划）
    """
    log_separator("-")
    log_step("VERIFY", "验证执行结果...")

    # 检查是否达到最大步骤数
    step_index = state.get("step_index", 0)
    if step_index >= MAX_STEPS:
        log_error(f"已达到最大步骤数 {MAX_STEPS}，强制结束")
        return Command(goto=END, update={"done": True, "result": f"FAILURE: 超过最大步骤数 {MAX_STEPS}"})

    # 获取当前页面状态，让 LLM 能看到验证码错误、页面跳转等反馈
    log_info("获取当前页面 URL 和快照...")
    url_output, _ = _run_cli(["eval", "() => window.location.href"])
    snapshot_output, _ = _run_cli(["snapshot"])

    page_state = f"当前 URL:\n{url_output}\n\n页面快照:\n{snapshot_output}"

    # 让 LLM 根据页面状态和消息历史判断结果
    test_case = state["test_case"]
    steps = test_case.get("steps", [])
    steps_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
    expected = test_case.get("expected", "")

    prompt = PLAN_VERIFY_PROMPT.format(
        steps=steps_text,
        expected=expected,
        url=state["url"],
    )

    llm = build_structured_llm(VerifyResult)
    response: VerifyResult = llm.invoke([
        SystemMessage(content="你是测试验证器。必须只输出一个 JSON 对象，不要输出 markdown、解释或其他任何文字。"),
        *state["messages"],
        HumanMessage(content=page_state),
        HumanMessage(content=prompt),
    ])

    status = response.status
    reason = response.reason
    content = f"{status}: {reason}"
    log_info(f"验证结果: {content[:300]}")

    if status == "SUCCESS":
        log_ok("验证通过")
        return Command(goto=END, update={"messages": [AIMessage(content=content)], "done": True, "result": "SUCCESS"})
    elif status == "CONTINUE":
        log_info(f"步骤未完成，继续执行下一步: {reason[:200]}")
        return Command(goto="route", update={"messages": [AIMessage(content=content)], "result": content})
    else:
        log_error(f"验证失败: {reason[:200]}")
        return Command(goto="plan", update={"messages": [AIMessage(content=content)], "result": content})
