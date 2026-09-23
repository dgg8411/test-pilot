"""Playwright CLI 封装工具。"""

import subprocess
import shutil
from pathlib import Path

from langchain_core.tools import tool

from src.utils import log_info, log_ok, log_warn, log_error

# 项目根目录下的 imgs/，确保截图路径始终正确
IMGS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "imgs"
IMGS_DIR.mkdir(exist_ok=True)


def _find_cli() -> str:
    """返回 playwright-cli 可执行命令，优先全局，其次 npx。"""
    if shutil.which("playwright-cli"):
        return "playwright-cli"
    return "npx --no-install playwright cli"


def _quote_arg(arg: str) -> str:
    """对 shell 参数加双引号，内部双引号转义。"""
    return '"' + arg.replace('"', '\\"') + '"'


def _run_cli(args: list[str]) -> tuple[str, int]:
    """执行 playwright-cli 命令，返回 (stdout, returncode)。"""
    cli = _find_cli()
    quoted_args = " ".join(_quote_arg(a) for a in args)
    cmd = f"{cli} {quoted_args}"
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        timeout=60,
        encoding="utf-8",
        errors="replace",
    )
    output = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if result.returncode != 0 and stderr:
        output += f"\n[stderr] {stderr}"
    return output, result.returncode


_browser_opened = False


@tool
def browser_open(url: str) -> str:
    """打开浏览器（非无头模式，可见浏览器窗口）并导航到指定 URL。返回页面快照（无障碍树）。每个会话只能调用一次。"""
    global _browser_opened
    if _browser_opened:
        log_warn(f"浏览器已打开，跳过重复打开。如需导航到其他页面，请使用 browser_goto。")
        return "[提示] 浏览器已经打开，不要重复调用 browser_open。如需导航到其他页面，请使用 browser_goto(url)。"
    log_info(f"打开浏览器: {url}")
    output, rc = _run_cli(["open", url, "--headed"])
    if rc != 0:
        log_error(f"打开浏览器失败: {output}")
        return f"[错误] 打开浏览器失败: {output}"
    _browser_opened = True
    log_ok(f"浏览器已打开, 快照长度: {len(output)} 字符")
    return output


@tool
def browser_goto(url: str) -> str:
    """导航到指定 URL。返回页面快照。"""
    log_info(f"导航到: {url}")
    output, rc = _run_cli(["goto", url])
    if rc != 0:
        log_error(f"导航失败: {output}")
        return f"[错误] 导航失败: {output}"
    log_ok("导航完成")
    return output


@tool
def browser_snapshot() -> str:
    """获取当前页面的无障碍树快照，用于了解页面结构和元素 ref。"""
    log_info("获取页面快照")
    output, rc = _run_cli(["snapshot"])
    if rc != 0:
        log_error(f"获取快照失败: {output}")
        return f"[错误] 获取快照失败: {output}"
    log_ok(f"快照已获取, 长度: {len(output)} 字符")
    return output


@tool
def browser_find(text: str) -> str:
    """在无障碍树中搜索文本，返回匹配的节点及其 ref。"""
    log_info(f"搜索页面文本: {text}")
    output, rc = _run_cli(["find", text])
    if rc != 0:
        log_warn(f"搜索失败: {output}")
        return f"[错误] 搜索失败: {output}"
    if output:
        log_ok(f"找到匹配: {output[:200]}")
    else:
        log_warn("未找到匹配")
    return output


@tool
def browser_click(ref_or_locator: str) -> str:
    """点击元素。可传入 ref（如 e5）或 Playwright locator（如 getByRole('button', { name: '登录' })）。"""
    log_info(f"点击元素: {ref_or_locator}")
    output, rc = _run_cli(["click", ref_or_locator])
    if rc != 0:
        log_error(f"点击失败: {output}")
        return f"[错误] 点击失败: {output}"
    log_ok("点击完成")
    return output


@tool
def browser_fill(ref_or_locator: str, value: str) -> str:
    """在输入框中填入文本（会自动清空原有内容）。可传入 ref 或 Playwright locator。"""
    display = value[:2] + "***" if len(value) > 2 else value
    log_info(f"填写 {ref_or_locator}: {display}")
    # fill 命令本身会先清空再填入，无需手动传空值清空
    output, rc = _run_cli(["fill", ref_or_locator, value])
    if rc != 0:
        log_error(f"填写失败: {output}")
        return f"[错误] 填写失败: {output}"
    log_ok("填写完成")
    return output


@tool
def browser_screenshot(filename: str = "captcha.png") -> str:
    """截取当前页面截图，保存到 imgs/ 目录。返回绝对文件路径。"""
    filepath = IMGS_DIR / filename
    log_info(f"截取页面截图: {filepath}")
    output, rc = _run_cli(["screenshot", f"--filename={str(filepath)}"])
    if rc != 0:
        log_error(f"截图失败: {output}")
        return f"[错误] 截图失败: {output}"
    if not filepath.exists():
        log_error(f"截图文件未生成: {filepath}")
        return f"[错误] 截图文件未生成: {filepath}"
    log_ok(f"截图已保存: {filepath}")
    return str(filepath)


@tool
def browser_screenshot_element(ref_or_locator: str, filename: str = "captcha.png") -> str:
    """对指定元素截图，保存到 imgs/ 目录。用于截取验证码图片。返回绝对文件路径。

    注意：优先使用 ref（如 e5）定位元素，也可使用 CSS/role 选择器。
    """
    filepath = IMGS_DIR / filename
    log_info(f"截取元素截图: {ref_or_locator} → {filepath}")
    output, rc = _run_cli(["screenshot", ref_or_locator, f"--filename={str(filepath)}"])
    if rc != 0:
        log_error(f"元素截图失败: {output}")
        return f"[错误] 元素截图失败: {output}"
    if not filepath.exists():
        log_error(f"截图文件未生成: {filepath}")
        return f"[错误] 截图文件未生成: {filepath}"
    log_ok(f"元素截图已保存: {filepath}")
    return str(filepath)


@tool
def browser_get_html(ref: str) -> str:
    """获取指定 ref 元素的 outerHTML，用于分析 DOM 结构。

    传入 ref（如 e5），返回该元素的完整 HTML（包含子元素）。
    可用于分析验证码图片在 DOM 中的位置和选择器。
    """
    log_info(f"获取元素 HTML: {ref}")
    js_code = "el => el.outerHTML"
    output, rc = _run_cli(["eval", js_code, ref])
    if rc != 0:
        log_error(f"获取 HTML 失败: {output}")
        return f"[错误] 获取 HTML 失败: {output}"
    log_ok(f"HTML 已获取, 长度: {len(output)} 字符")
    return output


@tool
def browser_get_url() -> str:
    """获取当前页面的 URL。用于登录后判断是否跳转成功。"""
    log_info("获取当前 URL")
    output, rc = _run_cli(["eval", "() => window.location.href"])
    if rc != 0:
        log_error(f"获取 URL 失败: {output}")
        return f"[错误] 获取 URL 失败: {output}"
    log_ok(f"当前 URL: {output}")
    return output


@tool
def browser_save_state(filename: str = "auth.json") -> str:
    """保存浏览器登录状态（cookies、localStorage 等）到文件。登录成功后调用以持久化登录态。

    文件保存在项目根目录下，非登录用例可通过 browser_load_state 加载。
    """
    log_info(f"保存登录状态: {filename}")
    output, rc = _run_cli(["state-save", filename])
    if rc != 0:
        log_error(f"保存状态失败: {output}")
        return f"[错误] 保存状态失败: {output}"
    log_ok(f"登录状态已保存: {filename}")
    return f"登录状态已保存: {filename}。状态文件已写入，后续非登录用例可通过 browser_load_state 加载。"


@tool
def browser_load_state(filename: str = "auth.json") -> str:
    """加载之前保存的浏览器登录状态。非登录用例在打开浏览器后、操作前调用。

    需要先调用 browser_open 打开浏览器，再调用本工具加载状态。
    """
    log_info(f"加载登录状态: {filename}")
    output, rc = _run_cli(["state-load", filename])
    if rc != 0:
        log_error(f"加载状态失败: {output}")
        return f"[错误] 加载状态失败: {output}"
    log_ok(f"登录状态已加载: {filename}")
    return f"登录状态已加载: {filename}。登录状态已生效，不要再重复调用 browser_load_state。接下来应调用 browser_snapshot() 获取页面快照并继续执行计划中的操作。"


@tool
def browser_close() -> str:
    """关闭浏览器。"""
    global _browser_opened
    log_info("关闭浏览器")
    output, rc = _run_cli(["close"])
    if rc != 0:
        log_warn(f"关闭浏览器异常: {output}")
    else:
        log_ok("浏览器已关闭")
    _browser_opened = False
    return output
