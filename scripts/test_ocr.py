"""测试 OCR 验证码识别效果。

用法: python test_ocr.py [图片路径]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.agent.tools.ocr import _solve_captcha_core


def main():
    image_path = sys.argv[1] if len(sys.argv) > 1 else "imgs/login-form.png"
    print(f"测试图片: {image_path}")
    print("=" * 60)
    result = _solve_captcha_core(image_path, logger=print)
    print("=" * 60)
    print(f"最终结果: {result}")


if __name__ == "__main__":
    main()
