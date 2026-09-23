"""Prompt 模板包。"""

from .plan import PLAN_PROMPT
from .login_execute import LOGIN_EXECUTE_PROMPT
from .app_execute import APP_EXECUTE_PROMPT
from .plan_execute import PLAN_EXECUTE_PROMPT
from .plan_verify import PLAN_VERIFY_PROMPT

__all__ = [
    "PLAN_PROMPT",
    "LOGIN_EXECUTE_PROMPT",
    "APP_EXECUTE_PROMPT",
    "PLAN_EXECUTE_PROMPT",
    "PLAN_VERIFY_PROMPT",
]
