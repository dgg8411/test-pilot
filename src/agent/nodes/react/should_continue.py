"""React 模式路由节点：判断下一步走向。"""

from typing import Literal
from langgraph.graph import END

from .route_node import LoginState
from .execute_node import MAX_STEPS


def should_continue(state: LoginState) -> Literal["execute", "__end__"]:
    """execute_node 直接执行工具后，只需判断是否继续或结束。"""
    if state.get("done"):
        return END

    if state.get("step_index", 0) >= MAX_STEPS:
        return END

    return "execute"
