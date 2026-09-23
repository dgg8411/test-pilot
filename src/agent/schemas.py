"""LLM 结构化输出模型（pydantic）。

用于约束 LLM 返回固定结构，替代脆弱的字符串解析（如 "SUCCESS" in content、正则匹配）。
"""

from typing import Literal

from pydantic import BaseModel, Field


class CaseClassification(BaseModel):
    """用例类型判定结果。"""

    is_login_case: bool = Field(
        description="是否为登录用例（测试目标是登录功能本身）。True 表示登录用例，False 表示非登录用例。"
    )


class PlanStep(BaseModel):
    """规划中的单个操作步骤。"""

    tool_call: str = Field(
        description="单条工具调用文本，格式为 工具名(参数1=值1, 参数2=值2)，例如 browser_open(url=https://example.com/login)。"
    )


class PlanOutput(BaseModel):
    """规划节点输出的操作步骤列表。"""

    steps: list[PlanStep] = Field(
        description="按执行顺序排列的操作步骤列表。只包含尚未完成的步骤，不要重复规划已完成的步骤。"
    )


class VerifyResult(BaseModel):
    """验证节点输出。"""

    status: Literal["SUCCESS", "CONTINUE", "FAILURE"] = Field(
        description="执行状态：SUCCESS=全部步骤完成且符合预期；CONTINUE=步骤未全部完成，继续执行下一步；FAILURE=执行出错或结果不符合预期。"
    )
    reason: str = Field(
        description="状态的原因说明。若页面有错误提示（如验证码错误），必须原样引用该错误文字。"
    )


class ExecuteResult(BaseModel):
    """React 模式执行节点输出（无工具调用时的收尾判定）。"""

    status: Literal["SUCCESS", "FAILURE", "CONTINUE"] = Field(
        description="执行状态。"
    )
    reason: str = Field(description="状态的原因说明。")
