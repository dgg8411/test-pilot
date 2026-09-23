"""React 模式 graph：route → execute → execute → ... → END

route 节点只判定用例类型，execute 节点直接执行工具调用。
验证码子图：execute → captcha → execute（通过 Command 跳转）。
"""

from langgraph.graph import StateGraph, END

from .nodes.react import (
    LoginState, route_node, execute_node, should_continue, captcha_subgraph_node,
)


def build_react_graph():
    """构建 React 模式 graph。

    route → execute → execute → ... → END
                  ↕
              captcha（验证码子图，通过 Command 跳转）
    """
    graph = StateGraph(LoginState)

    graph.add_node("route", route_node)
    graph.add_node("execute", execute_node)
    graph.add_node("captcha", captcha_subgraph_node)

    graph.set_entry_point("route")
    graph.add_edge("route", "execute")
    graph.add_edge("captcha", "execute")
    graph.add_conditional_edges("execute", should_continue, {
        "execute": "execute",
        END: END,
    })

    return graph.compile()
