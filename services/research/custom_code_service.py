"""
自定义代码执行服务（实验性）。

在受限命名空间中执行用户 pandas 代码：
- 执行前 AST 检查，禁止 import / 文件与系统相关内建函数；
- 命名空间只暴露 pd、np 和白名单 DataFrame；
- 捕获 stdout，超时 30 秒（线程实现，Windows 兼容）；
- 约定用户把最终结果放进变量 `result`（dict / DataFrame / 字符串）。

注意：本功能为实验性，受限 exec 不构成安全沙箱，请勿在生产环境开放给不可信用户。
"""
import ast
import contextlib
import io
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

import numpy as np
import pandas as pd

from services.research.dataset_service import dataset_service
from services.research.skills.base import convert, make_result

TIMEOUT_SECONDS = 30

# 允许使用的安全内建函数子集（禁止 open/eval/exec/compile/input/__import__）
SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
    "enumerate": enumerate, "filter": filter, "float": float, "format": format,
    "int": int, "isinstance": isinstance, "len": len, "list": list, "map": map,
    "max": max, "min": min, "print": print, "range": range, "repr": repr,
    "round": round, "set": set, "sorted": sorted, "str": str, "sum": sum,
    "tuple": tuple, "type": type, "zip": zip,
}

# AST 层面禁止的节点与名称
FORBIDDEN_NAMES = {"open", "eval", "exec", "compile", "input", "__import__",
                   "globals", "locals", "getattr", "setattr", "delattr", "vars",
                   "breakpoint", "exit", "quit", "help", "memoryview", "object",
                   "super", "iter", "next"}


class CustomCodeService:
    """实验性受限代码执行"""

    def _check_ast(self, code: str) -> str | None:
        """AST 静态检查，返回拒绝原因（None 表示通过）"""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return f"代码存在语法错误：{e}"

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                return "自定义代码中禁止 import（实验性限制）：命名空间已内置 pd、np 和常用 DataFrame"
            if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
                return f"自定义代码中禁止使用内建函数 `{node.id}`（实验性限制）"
            if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                return "自定义代码中禁止访问双下划线属性（实验性限制）"
        return None

    def _build_namespace(self) -> dict:
        """构建受限命名空间：pd、np、白名单 DataFrame（副本）"""
        namespace = {
            "__builtins__": SAFE_BUILTINS,
            "pd": pd,
            "np": np,
            "result": None,
        }
        # 白名单 DataFrame（提供副本，避免污染缓存）
        try:
            namespace["visits"] = dataset_service.build_visit_matrix().copy()
        except Exception:
            pass
        for var, table in [("admission", "admission"), ("discharge", "discharge"),
                           ("labs", "lab"), ("orders", "orders"),
                           ("exam", "exam"), ("surgery", "surgery")]:
            try:
                namespace[var] = dataset_service.load_table(table).copy()
            except Exception:
                pass
        return namespace

    def _execute(self, code: str) -> tuple[dict, str]:
        """在线程中执行，返回 (命名空间, stdout)"""
        namespace = self._build_namespace()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exec(code, namespace)  # noqa: S102 - 实验性受限执行
        return namespace, stdout.getvalue()

    def run(self, code: str) -> dict:
        """
        执行自定义代码（实验性），返回与算子统一的结构。
        约定：代码把最终结果赋值给变量 `result`（dict / DataFrame / 字符串）。
        """
        reject = self._check_ast(code)
        if reject:
            return make_result(f"代码被拒绝：{reject}")

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._execute, code)
            try:
                namespace, stdout = future.result(timeout=TIMEOUT_SECONDS)
            except FuturesTimeout:
                return make_result(
                    f"代码执行超过 {TIMEOUT_SECONDS} 秒被终止（实验性限制）。"
                    "请减小数据规模或简化计算后重试。"
                )
            except Exception as e:
                return make_result(f"代码执行出错：{type(e).__name__}: {e}")

        result = namespace.get("result")
        if result is None:
            return make_result(
                "代码执行完成，但未检测到 `result` 变量。"
                "请把最终结果赋值给变量 result（dict / DataFrame / 字符串）。"
                + (f"\n\n标准输出：\n{stdout}" if stdout.strip() else "")
            )

        # 结果转统一结构
        if isinstance(result, pd.DataFrame):
            df = result.head(100)
            out = make_result(
                f"代码执行成功，返回 DataFrame（{len(result)} 行 × {len(result.columns)} 列，展示前 100 行）。",
                tables=[{
                    "title": "自定义代码结果",
                    "columns": [str(c) for c in df.columns],
                    "rows": df.astype(object).where(df.notna(), None).values.tolist(),
                }],
                facts={"row_count": len(result)},
            )
        elif isinstance(result, dict):
            if any(k in result for k in ("summary", "tables", "charts", "facts")):
                out = make_result(
                    result.get("summary", "代码执行成功。"),
                    result.get("tables"), result.get("charts"), result.get("facts"),
                )
            else:
                out = make_result(
                    "代码执行成功，返回字典结果。",
                    tables=[{"title": "自定义代码结果", "columns": ["键", "值"],
                             "rows": [[str(k), str(v)] for k, v in result.items()]}],
                    facts=result if all(isinstance(v, (int, float, str, bool, type(None))) for v in result.values()) else {},
                )
        else:
            out = make_result(str(result))

        if stdout.strip():
            out["summary"] += f"\n\n标准输出：\n{stdout}"
        return convert(out)


# 全局单例
custom_code_service = CustomCodeService()
