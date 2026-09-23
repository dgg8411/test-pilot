"""React 模式入口：route → execute → execute → ... → END

用法:
    python main_react.py                                          # 运行默认 JSON 所有用例
    python main_react.py tests/login.test.json                    # 指定 JSON，运行所有用例
    python main_react.py tests/login.test.json tests/prequal.test.json  # 跨文件顺序执行
    python main_react.py tests/login.test.json TC_LOGIN_001       # 指定 JSON + 用例 ID
"""

import json
import sys
from pathlib import Path

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML

from src.agent.graph_react import build_react_graph
from src.utils import log_info, log_ok, log_error, log_warn, log_separator, log_title
from src.utils.logger import get_log_file


def load_test_config(json_path: str) -> dict:
    """加载测试用例 JSON。"""
    path = Path(json_path)
    if not path.exists():
        log_error(f"找不到 {json_path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_config(config: dict) -> bool:
    """校验 JSON 配置完整性。"""
    required_keys = ["url", "testCases"]
    for key in required_keys:
        if key not in config:
            log_error(f"JSON 缺少必需字段: {key}")
            return False

    for i, tc in enumerate(config["testCases"]):
        for key in ["id", "name", "steps", "expected"]:
            if key not in tc:
                log_error(f"测试用例 #{i} 缺少字段: {key}")
                return False

    log_ok("JSON 校验通过")
    return True


def run_test_case(config: dict, test_case: dict) -> dict:
    """运行单个测试用例。"""
    graph = build_react_graph()

    initial_state = {
        "test_case": test_case,
        "url": config["url"],
        "messages": [],
        "plan": "",
        "step_index": 0,
        "result": "",
        "done": False,
        "is_login_case": True,
        "captcha_input_ref": "",
    }

    log_separator()
    log_title(f" {test_case['id']} - {test_case['name']} ")
    log_separator()
    log_info(f"URL:  {config['url']}")
    log_info(f"步骤: {test_case.get('steps', [])}")
    log_info(f"预期: {test_case.get('expected', '')}")

    final_state = graph.invoke(initial_state, {"recursion_limit": 100})

    result = final_state.get("result", "UNKNOWN")
    if "SUCCESS" in result:
        log_ok(f"测试结果: {result}")
    elif "FAILURE" in result:
        log_error(f"测试结果: {result}")
    else:
        log_warn(f"测试结果: {result}")

    return final_state


def main() -> None:
    args = sys.argv[1:]
    if not args:
        args = ["tests/login.test.json"]

    log_info(f"模式: React")
    log_info(f"日志文件: {get_log_file()}")

    # 解析参数：.json 文件为测试文件，非 .json 为用例 ID 过滤
    json_files = [a for a in args if a.endswith(".json")]
    case_filter = next((a for a in args if not a.endswith(".json")), None)

    if not json_files:
        log_error("未指定测试 JSON 文件")
        sys.exit(1)

    results = []
    for json_path in json_files:
        config = load_test_config(json_path)
        if not validate_config(config):
            continue

        test_cases = config.get("testCases", [])
        if case_filter:
            test_cases = [tc for tc in test_cases if tc["id"] == case_filter]

        if not test_cases:
            log_warn(f"{json_path} 中没有找到匹配的测试用例")
            continue

        for tc in test_cases:
            result = run_test_case(config, tc)
            results.append({
                "id": tc["id"],
                "name": tc["name"],
                "actual": result.get("result", "UNKNOWN"),
            })

    if not results:
        log_warn("没有执行任何测试用例")
        sys.exit(1)

    # 汇总
    log_separator()
    log_title(" 测试汇总 ")
    log_separator()
    for r in results:
        if "SUCCESS" in r["actual"]:
            print_formatted_text(HTML(
                f'  <style fg="green">PASS</style> {r["id"]} | {r["name"]} | {r["actual"]}'
            ))
        else:
            print_formatted_text(HTML(
                f'  <style fg="red">FAIL</style> {r["id"]} | {r["name"]} | {r["actual"]}'
            ))


if __name__ == "__main__":
    main()
