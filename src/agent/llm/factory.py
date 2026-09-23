"""LLM 工厂：从环境变量构建 LLM 实例。"""

import os
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from .callbacks import LLMLoggerHandler


def build_llm() -> ChatOpenAI:
    """从环境变量构建 LLM（使用 .env-baidu 里的千帆接口）。"""
    if os.path.exists(".env-baidu"):
        load_dotenv(".env-baidu")
    return ChatOpenAI(
        base_url=os.getenv("OPENAI_BASE_URL"),
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("OPENAI_MODEL", "deepseek-v4-flash-0731"),
        temperature=0,
        callbacks=[LLMLoggerHandler()],
    )


def build_structured_llm(schema: type[BaseModel]) -> Any:
    """构建结构化输出 LLM。

    使用 with_structured_output 默认行为（json_schema 模式），
    配合 prompt 中的 JSON 输出要求和示例。"""
    return build_llm().with_structured_output(schema)
