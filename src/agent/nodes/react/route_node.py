"""路由节点：判定用例类型，不做规划。

React 模式下取代 plan_node，只判定登录/非登录用例，直接进入 execute 循环。
"""

import json
import operator
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage

from ...tools import ALL_TOOLS
from src.utils import log_step, log_info, log_ok, log_separator
from ...llm import build_structured_llm
from ...schemas import CaseClassification


class LoginState(TypedDict):
    test_case: dict
    url: str
    messages: Annotated[list, operator.add]
    plan: str
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


def route_node(state: LoginState) -> dict:
    """路由节点：判定用例类型，直接进入 execute 循环。"""
    log_separator("-")
    log_step("ROUTE", "判定用例类型...")

    test_case = state["test_case"]
    test_case_json = json.dumps(test_case, ensure_ascii=False, indent=2)
    log_info(f"测试用例:\n{test_case_json}")
    log_info(f"页面 URL: {state['url']}")

    is_login = _classify_case(test_case)

    log_ok(f"用例类型: {'登录用例' if is_login else '非登录用例'}")

    return {
        "is_login_case": is_login,
        "step_index": 0,
    }
