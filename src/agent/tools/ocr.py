"""验证码 OCR 封装（调用 llama-server 的 OpenAI 兼容接口）。"""

import base64
import re
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from src.utils import log_info
from ..llm import build_llm

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# OCR 服务配置
OCR_BASE_URL = "http://localhost:8080/v1"
OCR_MODEL = "gpt-4o"


def _build_ocr_llm() -> ChatOpenAI:
    """构建 OCR 服务的 LLM 客户端（llama-server，端口 8080）。"""
    return ChatOpenAI(
        base_url=OCR_BASE_URL,
        api_key="not-needed",
        model=OCR_MODEL,
        temperature=0,
    )


def _extract_captcha(raw_text: str, logger=None) -> str:
    """调用 LLM 从 OCR 原始输出中提取纯验证码。

    OCR 服务可能返回包含描述性信息的文本（如"验证码为：AB3D"），
    用 LLM 提取其中的纯验证码字符。
    """
    if logger is None:
        logger = log_info
    logger(f"LLM 提取验证码，原始 OCR 输出: {raw_text}")

    llm = build_llm()
    prompt = (
        "以下是一个 OCR 服务对验证码图片的识别结果，可能包含描述性文字。"
        "请从中提取4位或6位纯验证码字符（仅英文字母和数字），不要输出任何其他内容。\n\n"
        f"OCR 原始输出: {raw_text}\n\n"
        "只输出验证码本身，不要解释、不要标点、不要换行。"
    )

    try:
        resp = llm.invoke(prompt)
        code = resp.content.strip()
        logger(f"LLM 提取结果: {code}")
        return code
    except Exception as e:
        logger(f"LLM 提取失败，使用原始输出: {e}")
        return raw_text.strip()


def _solve_captcha_core(image_path: str, logger=None) -> str:
    """验证码识别核心逻辑，可被 tool 和测试脚本复用。

    logger 为 None 时使用 src.utils 的 logger，否则调用 logger(msg)。
    """
    if logger is None:
        logger = log_info

    # 支持相对路径：转为基于项目根目录的绝对路径
    p = Path(image_path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p

    logger(f"开始识别验证码，图片路径: {p}")
    logger(f"图片文件大小: {p.stat().st_size} 字节")

    if not p.exists():
        logger(f"验证码图片不存在: {p}")
        return f"[OCR 错误] 图片不存在: {p}"

    with open(p, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    logger(f"图片 base64 编码完成，长度: {len(img_b64)} 字符")
    data_url = f"data:image/png;base64,{img_b64}"

    # 使用 langchain ChatOpenAI 调用 OCR 服务
    ocr_llm = _build_ocr_llm()
    logger("调用 OCR 服务 (localhost:8080)...")

    try:
        message = HumanMessage(content=[
            {"type": "text", "text": "解析验证码,验证码为4位英文字母和数字."},
            {"type": "image_url", "image_url": {"url": data_url}},
        ])
        resp = ocr_llm.invoke([message])
        raw_code = resp.content.strip()
        logger(f"OCR 原始返回: {raw_code}")

        # OCR 输出可能包含描述性信息，调用 LLM 提取纯验证码
        code = _extract_captcha(raw_code, logger=logger)

        # 简单校验：如果提取结果明显不是验证码（太长或含中文），回退到原始输出
        if len(code) > 10 or any('\u4e00' <= c <= '\u9fff' for c in code):
            logger(f"LLM 提取结果异常（可能不是验证码）: {code}，回退到原始输出")
            # 尝试从原始输出中提取字母数字
            alphanumeric = re.sub(r'[^a-zA-Z0-9]', '', raw_code)
            if alphanumeric and len(alphanumeric) <= 10:
                code = alphanumeric
                logger(f"正则提取验证码: {code}")
            else:
                code = raw_code
                logger(f"无法提取有效验证码，返回原始输出: {code}")

        logger(f"验证码最终识别结果: {code}")
        return code
    except Exception as e:
        logger(f"OCR 识别失败: {type(e).__name__}: {e}")
        return f"[OCR 错误] {e}"


@tool
def solve_captcha(image_path: str) -> str:
    """识别验证码图片，返回识别结果文本。

    调用本地 OCR 服务（llama-server，端口 8080），
    使用 OpenAI 兼容的 /v1/chat/completions 接口。
    如果 OCR 输出包含描述性信息，会调用 LLM 提取纯验证码。
    """
    return _solve_captcha_core(image_path)
