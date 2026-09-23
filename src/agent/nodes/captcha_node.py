"""验证码子图节点：自动完成验证码识别全流程。

当主 ReAct 循环遇到验证码时，通过 Command 跳转到此子图。
子图自动执行：找验证码图片 → 点击刷新 → 截图 → OCR 识别 → 填写 → 返回主循环。
返回普通 dict，由 graph 边 captcha → execute 路由回主循环。
"""

from pathlib import Path

from langchain_core.messages import HumanMessage

from ..tools.browser import _run_cli
from ..tools.ocr import _solve_captcha_core
from src.utils import log_info, log_ok, log_error, log_warn, log_step, log_separator

IMGS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "imgs"

# 用于标记验证码图片的唯一 ID
_CAPTCHA_TAG = "captcha-img-target-tag"


def _captcha_result_message(captcha_input_ref: str, captcha_code: str, success: bool) -> HumanMessage:
    """构造验证码子图结果消息，返回给主循环 LLM。"""
    if success:
        content = (
            f"[验证码子图结果] 验证码已自动识别并填写完成。"
            f"识别结果: {captcha_code}，已填入验证码输入框 {captcha_input_ref}。"
            f"验证码步骤已完成，不要再调用 solve_captcha_subgraph。"
            f"请继续执行下一步操作。"
        )
    else:
        content = (
            f"[验证码子图结果] 验证码自动识别失败: {captcha_code}。"
            f"请尝试手动处理验证码：点击验证码图片刷新，截图后用 solve_captcha 识别，再用 browser_fill 填写。"
        )
    return HumanMessage(content=content)


def captcha_subgraph_node(state: dict) -> dict:
    """验证码子图节点：自动完成验证码识别全流程。

    从 plan[step_index - 1] 中提取 captcha_input_ref（route 已推进 step_index），
    自动完成：标记验证码图片 → 点击刷新 → 截图 → OCR → 填写。
    """
    import re

    log_separator("-")
    log_step("CAPTCHA", "进入验证码子图，自动识别验证码")

    # 从 plan 列表中取当前步骤（route 已推进 step_index，所以是 step_index - 1）
    plan = state.get("plan", [])
    step_index = state.get("step_index", 0)
    current_step = plan[step_index - 1] if step_index > 0 and step_index <= len(plan) else ""
    # 提取 captcha_input_ref：支持普通 ref（e54）或 locator（getByRole(...)）
    ref_match = re.search(r'captcha_input_ref=(.+)', current_step)
    captcha_input_ref = ""
    if ref_match:
        # 去掉末尾的 ')'（solve_captcha_subgraph 的闭合括号）及空白
        captcha_input_ref = ref_match.group(1).strip()
        if captcha_input_ref.endswith(')'):
            captcha_input_ref = captcha_input_ref[:-1].rstrip()
    log_info(f"验证码输入框 ref: {captcha_input_ref}")

    # Step 1: 获取页面快照（刷新 ref 映射）
    log_info("[CAPTCHA] Step 1: 获取页面快照")
    snapshot_output, snapshot_rc = _run_cli(["snapshot"])
    if snapshot_rc != 0:
        log_error(f"[CAPTCHA] 获取快照失败: {snapshot_output}")
        msg = _captcha_result_message(captcha_input_ref, "获取快照失败", success=False)
        return {"messages": [msg]}

    # Step 2: 通过 eval 在验证码输入框的父容器中找到验证码图片并标记
    # 向上遍历父元素，找到含 data:image/png 的 img，给它加唯一 id
    log_info(f"[CAPTCHA] Step 2: 标记验证码图片 (ref={captcha_input_ref})")
    # 不用 f-string，避免 {{ }} 转义问题，用字符串拼接插入 TAG
    js_code = (
        "el => {"
        "  const old = document.getElementById('" + _CAPTCHA_TAG + "');"
        "  if (old) old.removeAttribute('id');"
        "  let node = el;"
        "  for (let i = 0; i < 10; i++) {"
        "    node = node.parentElement;"
        "    if (!node) break;"
        "    const imgs = node.querySelectorAll('img');"
        "    for (const img of imgs) {"
        "      if (img.src && img.src.startsWith('data:image/png')) {"
        "        img.id = '" + _CAPTCHA_TAG + "';"
        "        return 'OK:png:' + img.src.substring(0, 60);"
        "      }"
        "    }"
        "  }"
        "  node = el;"
        "  for (let i = 0; i < 10; i++) {"
        "    node = node.parentElement;"
        "    if (!node) break;"
        "    const imgs = node.querySelectorAll('img');"
        "    for (const img of imgs) {"
        "      if (img.src && !img.src.startsWith('data:image/svg')) {"
        "        const lower = img.src.toLowerCase();"
        "        if (lower.includes('captcha') || lower.includes('verify') || lower.includes('code') || lower.includes('kaptcha')) {"
        "          img.id = '" + _CAPTCHA_TAG + "';"
        "          return 'OK:url:' + img.src.substring(0, 60);"
        "        }"
        "      }"
        "    }"
        "  }"
        "  node = el;"
        "  for (let i = 0; i < 10; i++) {"
        "    node = node.parentElement;"
        "    if (!node) break;"
        "    const imgs = node.querySelectorAll('img');"
        "    for (let j = imgs.length - 1; j >= 0; j--) {"
        "      if (!imgs[j].src || !imgs[j].src.startsWith('data:image/svg')) {"
        "        imgs[j].id = '" + _CAPTCHA_TAG + "';"
        "        return 'OK:fallback:' + (imgs[j].src || '').substring(0, 60);"
        "      }"
        "    }"
        "  }"
        "  return 'NOT_FOUND';"
        "}"
    )
    tag_output, tag_rc = _run_cli(["eval", js_code, captcha_input_ref])
    log_info(f"[CAPTCHA] 标记结果: {tag_output}")

    # 检查是否标记成功：eval 返回 "OK:..." 表示成功
    # 注意 output 包含 "### Ran Playwright code" 部分，其中 JS 源码含 'NOT_FOUND' 字符串
    # 所以只检查 ### Result 行是否含 OK
    result_line = ""
    for line in tag_output.split("\n"):
        if "OK:" in line:
            result_line = line.strip()
            break

    if tag_rc != 0 or not result_line or "NOT_FOUND" in result_line:
        log_error(f"[CAPTCHA] 无法找到验证码图片: {tag_output[:300]}")
        msg = _captcha_result_message(captcha_input_ref, "无法找到验证码图片", success=False)
        return {"messages": [msg]}

    selector = f"#{_CAPTCHA_TAG}"
    log_ok(f"[CAPTCHA] 验证码图片已标记，选择器: {selector}")

    # Step 3: 点击验证码图片刷新
    log_info(f"[CAPTCHA] Step 3: 点击验证码图片刷新: {selector}")
    click_output, click_rc = _run_cli(["click", selector])
    if click_rc != 0:
        log_warn(f"[CAPTCHA] 点击刷新失败（可能不影响）: {click_output}")
    else:
        log_ok("[CAPTCHA] 验证码已刷新")

    # 刷新后重新标记（DOM 可能变了）
    if click_rc == 0:
        log_info("[CAPTCHA] 重新标记验证码图片（刷新后）")
        retag_output, retag_rc = _run_cli(["eval", js_code, captcha_input_ref])
        log_info(f"[CAPTCHA] 重新标记结果: {retag_output}")

    # Step 4: 截图
    log_info("[CAPTCHA] Step 4: 截取验证码图片")
    captcha_path = IMGS_DIR / "captcha.png"
    screenshot_output, screenshot_rc = _run_cli([
        "screenshot", selector, f"--filename={str(captcha_path)}"
    ])
    if screenshot_rc != 0 or not captcha_path.exists():
        log_error(f"[CAPTCHA] 截图失败: {screenshot_output}")
        msg = _captcha_result_message(captcha_input_ref, "截图失败", success=False)
        return {"messages": [msg]}
    log_ok(f"[CAPTCHA] 截图已保存: {captcha_path} ({captcha_path.stat().st_size} 字节)")

    # Step 5: OCR 识别
    log_info("[CAPTCHA] Step 5: OCR 识别验证码")
    captcha_code = _solve_captcha_core(str(captcha_path))
    log_ok(f"[CAPTCHA] 验证码识别结果: {captcha_code}")

    # Step 6: 自动填写验证码
    fill_success = False
    if captcha_input_ref and not captcha_code.startswith("[OCR"):
        log_info(f"[CAPTCHA] Step 6: 自动填写验证码到 {captcha_input_ref}")
        # 先清空再填入，确保旧内容被清除
        _run_cli(["fill", captcha_input_ref, ""])
        fill_output, fill_rc = _run_cli(["fill", captcha_input_ref, captcha_code])
        if fill_rc != 0:
            log_error(f"[CAPTCHA] 填写验证码失败: {fill_output}")
        else:
            log_ok(f"[CAPTCHA] 验证码已填写: {captcha_code}")
            fill_success = True

    log_separator("-")
    log_step("CAPTCHA", f"验证码子图完成，识别结果: {captcha_code}")

    # 返回主循环：用 HumanMessage 明确告知 LLM 验证码已完成
    # HumanMessage 不会触发 should_continue 路由到 tools，LLM 直接看到结果并继续下一步
    # 不使用 Command(goto=...)，依赖 graph 中 captcha → execute 的边
    msg = _captcha_result_message(captcha_input_ref, captcha_code, success=fill_success)
    return {"messages": [msg]}
