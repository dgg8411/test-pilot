"""子图触发工具：LLM 调用这些工具时，execute_node 会拦截并跳转到对应子图。

这些工具不会真正执行，只是让 LLM 有一个明确的工具调用来触发子图跳转。
"""

from langchain_core.tools import tool


@tool
def solve_captcha_subgraph(captcha_input_ref: str) -> str:
    """自动识别并填写验证码。传入验证码输入框的 ref（如 e54），会自动完成：
    1. 获取页面快照并分析登录表单 HTML
    2. 找到验证码图片的 CSS 选择器
    3. 点击验证码图片刷新（防止过期）
    4. 截取验证码图片
    5. OCR 识别验证码
    6. 自动填写到验证码输入框

    调用此工具后无需再手动截图和识别验证码。
    """
    # 此函数不会被真正执行，execute_node 会拦截并跳转到验证码子图
    return f"验证码子图已触发，验证码输入框 ref={captcha_input_ref}"
