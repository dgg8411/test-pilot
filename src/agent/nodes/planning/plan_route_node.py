"""Planning 模式的路由节点：判断当前步骤是否为验证码操作，决定去向。"""

from langgraph.types import Command
from src.utils import log_step, log_info, log_separator
from .plan_replan_node import PlanState


def plan_route_node(state: PlanState) -> Command:
    """路由节点：当前步骤是 solve_captcha_subgraph → captcha，否则 → execute。"""
    log_separator("-")
    log_step("ROUTE", "路由判断...")

    plan = state.get("plan", [])
    step_index = state.get("step_index", 0)

    # 已超出计划范围 → execute（会触发 max steps 或 verify 处理）
    if step_index >= len(plan):
        log_info("步骤已超出计划范围，路由到 execute")
        return Command(goto="execute")

    current_step = plan[step_index].strip()

    if current_step.startswith("solve_captcha_subgraph"):
        log_info(f"路由到 captcha (步骤 {step_index + 1}/{len(plan)})")
        return Command(goto="captcha", update={"step_index": step_index + 1})

    log_info(f"路由到 execute (步骤 {step_index + 1}/{len(plan)})")
    return Command(goto="execute")
