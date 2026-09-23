"""Planning 模式 graph：plan → route → execute/captcha → verify → route/END/plan

plan 生成步骤列表，route 按 step_index 分流，execute 执行，verify 验证结果并路由。
verify CONTINUE 回 route 继续下一步，SUCCESS 结束，FAILURE 回 plan 重新规划。
"""

from langgraph.graph import StateGraph, END

from .nodes.planning import (
    PlanState, plan_replan_node, plan_execute_node, captcha_subgraph_node,
    plan_route_node,
)
from .nodes.planning.plan_verify_node import plan_verify_node


def build_planning_graph():
    """构建 Planning 模式 graph。

    plan → route → execute → verify → route (CONTINUE)
              ↘ captcha ↗        ├── END (SUCCESS)
                                  └── plan (FAILURE)

    plan 生成完整步骤列表，route 按 step_index 取当前步骤分流：
    - solve_captcha_subgraph → captcha
    - 其他 → execute
    """
    graph = StateGraph(PlanState)

    graph.add_node("plan", plan_replan_node)
    graph.add_node("route", plan_route_node)
    graph.add_node("execute", plan_execute_node)
    graph.add_node("captcha", captcha_subgraph_node)
    graph.add_node("verify", plan_verify_node)

    graph.set_entry_point("plan")
    graph.add_edge("plan", "route")
    # route 通过 Command 路由到 captcha 或 execute
    # captcha 和 execute 完成后都进入 verify
    graph.add_edge("captcha", "verify")
    graph.add_edge("execute", "verify")
    # verify 通过 Command 路由到 route / END / plan

    return graph.compile()
