from .browser import (
    browser_open, browser_goto, browser_snapshot, browser_find,
    browser_click, browser_fill, browser_screenshot,
    browser_screenshot_element, browser_get_html, browser_get_url,
    browser_save_state, browser_load_state, browser_close,
)
from .subgraph_tools import solve_captcha_subgraph

# solve_captcha 工具不暴露给 LLM，验证码识别由 captcha_node 子图自动完成
# _solve_captcha_core 仍被子图内部调用（从 ocr 模块直接导入）

ALL_TOOLS = [
    browser_open,
    browser_goto,
    browser_snapshot,
    browser_find,
    browser_click,
    browser_fill,
    browser_screenshot,
    browser_screenshot_element,
    browser_get_html,
    browser_get_url,
    browser_save_state,
    browser_load_state,
    browser_close,
    solve_captcha_subgraph,
]
