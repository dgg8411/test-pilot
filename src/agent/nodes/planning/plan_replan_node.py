"""Planning 模式的 plan 节点：根据步骤序列和已执行步骤，规划下一个操作。"""

import json
import operator
from typing import Annotated, TypedDict

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from src.utils import log_step, log_info, log_ok, log_separator
from ...llm import build_structured_llm
from ...prompts import PLAN_PROMPT
from ...schemas import CaseClassification, PlanOutput


class PlanState(TypedDict):
    test_case: dict
    url: str
    messages: Annotated[list, operator.add]
    plan: list  # 工具调用列表，如 ["browser_open(...)", "browser_snapshot()", ...]
    step_index: int
    result: str
    done: bool
    is_login_case: bool
    captcha_input_ref: str


def _classify_case(test_case: dict) -> bool:
    """用 LLM 判断是否为登录用例，返回 True/False（pydantic 结构化输出）。"""
    llm = build_structured_llm(CaseClassification)
    test_case_json = json.dumps(test_case, ensure_ascii=False)
    prompt = (
        "请判断以下测试用例是否为'登录用例'（即测试目标是登录功能本身的用例）。\n"
        "如果用例的步骤中包含填写用户名、密码、验证码、点击登录按钮等操作，则为登录用例。\n"
        "如果用例依赖已登录状态来测试其他功能（如页面操作、数据查看等），则为非登录用例。\n"
        "只输出 JSON 对象，不要输出任何解释文字。\n\n"
        f"测试用例：\n{test_case_json}"
    )
    resp: CaseClassification = llm.invoke([
        SystemMessage(content="你是登录用例分类器。必须只输出一个 JSON 对象，格式为 {\"is_login_case\": true 或 false}，不要输出 markdown、解释或其他文字。"),
        HumanMessage(content=prompt),
    ])
    log_info(f"用例类型判定: {'登录用例' if resp.is_login_case else '非登录用例'}")
    return resp.is_login_case


def _extract_recent_context(messages: list) -> str:
    """从消息历史中提取最近的执行上下文摘要，避免传全部历史导致 LLM 混淆。

    提取策略：
    - 找到最近一次 browser_snapshot 的完整快照（用于拿真实 ref）
    - 找到最后一次 verify 反馈（含 SUCCESS/FAILURE/CONTINUE 的 AIMessage）
    - 找到最近的 ToolMessage（工具执行结果，排除快照类的大段输出）
    - 构造简洁的上下文文本
    """
    if not messages:
        return "（无执行记录，从第1步开始规划）"

    # 收集最近的工具执行结果和验证反馈
    recent_tools = []
    last_verify = None
    last_snapshot = None

    for m in messages:
        content = getattr(m, "content", "")
        if not isinstance(content, str):
            content = str(content) if content else ""
        msg_type = type(m).__name__

        if msg_type == "ToolMessage":
            # 快照类输出保留完整内容（需要 ref 信息用于后续规划）
            if "Snapshot" in content and ("```yaml" in content or "[ref=" in content):
                last_snapshot = content
                continue
            # 其他工具结果截取前 300 字符
            recent_tools.append(content[:300])
        elif msg_type == "AIMessage":
            # 跳过 plan 和 execute 自己的输出消息
            if content.startswith("[PLAN]") or content.startswith("[EXECUTE]"):
                continue
            # 检查是否为 verify 的反馈
            upper = content.upper()
            if any(kw in upper for kw in ["SUCCESS", "FAILURE", "CONTINUE"]):
                last_verify = content[:300]

    parts = []
    if recent_tools:
        # 只取最近 5 个工具结果
        parts.append("最近的工具执行结果：\n" + "\n".join(f"- {t}" for t in recent_tools[-5:]))
    if last_snapshot:
        # 保留完整快照供 LLM 获取真实 ref
        parts.append(f"最近页面快照：\n{last_snapshot}")
    if last_verify:
        parts.append(f"最近验证反馈：{last_verify}")

    if not parts:
        return "（无执行记录，从第1步开始规划）"

    return "\n".join(parts)


def plan_replan_node(state: PlanState) -> dict:
    """规划节点：根据步骤序列和已执行步骤，规划下一个操作。

    首次调用时判定用例类型并生成初始计划。
    后续调用时根据已完成的操作重新规划下一步。
    """
    log_separator("-")
    log_step("PLAN", "规划下一步操作...")

    test_case = state["test_case"]
    steps = test_case.get("steps", [])
    steps_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))

    # 首次调用：判定用例类型
    is_login = state.get("is_login_case")
    if is_login is None:
        is_login = _classify_case(test_case)

    expected = test_case.get("expected", "")

    # 从消息历史中提取简洁上下文，不传全部历史避免 LLM 混淆
    execution_context = _extract_recent_context(state.get("messages", []))

    # 构造上一次规划的操作序列（文本描述）和当前执行进度
    plan_list = state.get("plan", [])
    step_index = state.get("step_index", 0)
    if plan_list:
        # 用文本描述标注每一步及其完成状态，避免只用索引数字
        plan_lines = []
        for i, p in enumerate(plan_list):
            if i < step_index:
                plan_lines.append(f"  已完成 - {p}")
            elif i == step_index:
                plan_lines.append(f"> 当前执行中 - {p}")
            else:
                plan_lines.append(f"  待执行 - {p}")
        previous_plan = "\n".join(plan_lines) if plan_lines else "（无）"
        # 当前步骤用文本描述，而非索引
        if step_index < len(plan_list):
            current_step = f"下一步要执行的操作是：{plan_list[step_index]}（这是第 {step_index + 1} 个操作，前 {step_index} 个操作已完成）"
        else:
            current_step = f"上一次规划的所有操作已全部执行完毕，共 {len(plan_list)} 个操作。请根据验证结果决定是否需要补充新的操作。"
    else:
        previous_plan = "（首次规划，无历史计划）"
        current_step = "（尚未开始执行，请从第1步开始规划）"

    prompt = PLAN_PROMPT.format(
        steps=steps_text,
        expected=expected,
        url=state["url"],
        execution_context=execution_context,
        previous_plan=previous_plan,
        current_step=current_step,
    )

    # plan 节点通过结构化输出生成操作步骤列表
    llm = build_structured_llm(PlanOutput)
    response: PlanOutput = llm.invoke([HumanMessage(content=prompt)])

    plan_steps = [step.tool_call for step in response.steps]
    log_ok(f"规划完成: {len(plan_steps)} 步")
    for i, s in enumerate(plan_steps):
        log_info(f"  步骤 {i+1}: {s}")

    return {
        "plan": plan_steps,
        "step_index": 0,
        "is_login_case": is_login,
        "messages": [AIMessage(content="[PLAN] " + "\n".join(plan_steps))],
    }
