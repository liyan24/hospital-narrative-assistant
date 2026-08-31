"""论文实验评测管线包。

保证从项目根目录运行脚本/测试时可以 import 现有项目模块
（services / database / config 等）。
"""

import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
