"""统一的命令行日志输出，基于 prompt_toolkit，同时写入日志文件。"""

import re
import logging
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML

# 匹配 XML 1.0 不允许的控制字符（保留 \t \n \r）
_INVALID_XML_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# ---------------------------------------------------------------------------
# 文件日志（标准库 logging）
# ---------------------------------------------------------------------------
_LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
_LOGS_DIR.mkdir(exist_ok=True)
_LOG_FILE = _LOGS_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

_file_logger = logging.getLogger("test_pilot")
_file_logger.setLevel(logging.DEBUG)
_file_handler = logging.FileHandler(str(_LOG_FILE), encoding="utf-8")
_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
_file_logger.addHandler(_file_handler)
_file_logger.propagate = False


def _log_to_file(level: str, msg: str) -> None:
    """将日志写入文件。"""
    _file_logger.log(
        getattr(logging, level, logging.INFO),
        str(msg),
    )


def get_log_file() -> Path:
    """返回当前日志文件路径。"""
    return _LOG_FILE


# ---------------------------------------------------------------------------
# 命令行输出 + 文件日志
# ---------------------------------------------------------------------------

def _safe(msg: str) -> str:
    """转义 XML 特殊字符并移除非法控制字符，防止 HTML 解析报错。"""
    s = str(msg)
    s = _INVALID_XML_CHARS.sub("?", s)
    return escape(s)


def log_info(msg: str) -> None:
    print_formatted_text(HTML(f'<style fg="cyan">[INFO]</style> {_safe(msg)}'))
    _log_to_file("INFO", msg)


def log_ok(msg: str) -> None:
    print_formatted_text(HTML(f'<style fg="green">[OK]</style>   {_safe(msg)}'))
    _log_to_file("INFO", msg)


def log_warn(msg: str) -> None:
    print_formatted_text(HTML(f'<style fg="yellow">[WARN]</style> {_safe(msg)}'))
    _log_to_file("WARNING", msg)


def log_error(msg: str) -> None:
    print_formatted_text(HTML(f'<style fg="red">[ERROR]</style> {_safe(msg)}'))
    _log_to_file("ERROR", msg)


def log_step(node: str, msg: str) -> None:
    print_formatted_text(HTML(
        f'<style fg="ansiblue">[{_safe(node)}]</style> {_safe(msg)}'
    ))
    _log_to_file("INFO", f"[{node}] {msg}")


def log_separator(char: str = "=", length: int = 60) -> None:
    line = char * length
    print_formatted_text(line)
    _log_to_file("INFO", line)


def log_title(title: str) -> None:
    print_formatted_text(HTML(
        f'<style fg="white" bg="ansiblue"> {_safe(title)} </style>'
    ))
    _log_to_file("INFO", f"=== {title} ===")
