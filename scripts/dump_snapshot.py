"""用 playwright-cli 打开测试页面并保存快照到文本文件。

用法: d:\miniconda3\envs\agent-test\python.exe -m scripts.dump_snapshot
"""

import json
import subprocess
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def find_cli() -> str:
    if shutil.which("playwright-cli"):
        return "playwright-cli"
    return "npx --no-install playwright cli"


def run_cli(args: list[str]) -> tuple[str, int]:
    cmd = f'{find_cli()} {" ".join(args)}'
    print(f"[CMD] {cmd}")
    result = subprocess.run(
        cmd, shell=True, capture_output=True,
        timeout=60, encoding="utf-8", errors="replace",
    )
    output = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if result.returncode != 0 and stderr:
        output += f"\n[stderr] {stderr}"
    return output, result.returncode


def main():
    # 从 JSON 读取 URL
    config_path = PROJECT_ROOT / "tests" / "login.test.json"
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    url = config["url"]
    print(f"[INFO] 页面 URL: {url}")

    # 打开浏览器
    print("[INFO] 打开浏览器...")
    out, rc = run_cli(["open", url])
    if rc != 0:
        print(f"[ERROR] 打开失败: {out}")
        sys.exit(1)
    print(f"[OK] 浏览器已打开")

    # 获取快照
    print("[INFO] 获取页面快照...")
    out, rc = run_cli(["snapshot"])
    if rc != 0:
        print(f"[ERROR] 快照获取失败: {out}")
        sys.exit(1)
    print(f"[OK] 快照长度: {len(out)} 字符")

    # 保存到文件
    snapshot_file = PROJECT_ROOT / "imgs" / "snapshot.txt"
    snapshot_file.parent.mkdir(exist_ok=True)
    with open(snapshot_file, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"[OK] 快照已保存: {snapshot_file}")

    # 关闭浏览器
    print("[INFO] 关闭浏览器...")
    run_cli(["close"])
    print("[OK] 完成")


if __name__ == "__main__":
    main()
