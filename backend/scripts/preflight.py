#!/usr/bin/env python3
"""启动前置诊断：在真正拉起 uvicorn 前把常见启动失败原因讲清楚。

退出码：
  0  环境就绪，可以启动
  2  依赖缺失（Python 版本不够 / 虚拟环境不存在 / 关键包没装）
  3  环境变量配置有误（APP_PORT 不是端口、APP_ENV 非法等）
  4  代码或示例数据本身无法加载

用法：python scripts/preflight.py
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# (导入名, pip 包名, 最低版本要求仅作提示)
REQUIRED_PACKAGES = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn[standard]"),
    ("pydantic", "pydantic"),
    ("dotenv", "python-dotenv"),
]


def fail(code: int, title: str, lines: list[str]) -> int:
    print(f"\n[启动诊断] {title}", file=sys.stderr)
    for line in lines:
        print(f"  - {line}", file=sys.stderr)
    return code


def main() -> int:
    # 1) Python 版本：代码用到了 PEP 604（X | None）等 3.10+ 语法。
    if sys.version_info < (3, 10):
        return fail(
            2,
            "Python 版本过低（依赖/运行环境问题）",
            [
                f"当前 Python：{sys.version.split()[0]}，本项目要求 Python >= 3.10。",
                "请安装 Python 3.10 及以上版本后重建虚拟环境：",
                "  rm -rf backend/.venv && python3 -m venv backend/.venv",
                "  backend/.venv/bin/pip install -r backend/requirements.txt",
            ],
        )

    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    if not in_venv and Path(BACKEND_DIR / ".venv").exists():
        return fail(
            2,
            "检测到 backend/.venv 但当前没有激活它（依赖环境问题）",
            [
                "请用虚拟环境里的解释器启动，而不是系统 Python：",
                "  backend/.venv/bin/python scripts/preflight.py",
                "或先激活：source backend/.venv/bin/activate",
            ],
        )

    # 2) 关键依赖是否可导入。
    missing: list[str] = []
    for import_name, pip_name in REQUIRED_PACKAGES:
        try:
            importlib.import_module(import_name)
        except Exception:  # noqa: BLE001 - 诊断脚本要兜住所有导入异常
            missing.append(pip_name)
    if missing:
        return fail(
            2,
            "依赖缺失（不是环境变量问题）",
            [
                f"无法导入：{', '.join(missing)}",
                "请在 backend/ 下安装已锁定版本的依赖：",
                "  backend/.venv/bin/pip install -r backend/requirements.txt",
                "（若 .venv 是在别的操作系统/机器上拷贝来的，请先 rm -rf backend/.venv 重建）",
            ],
        )

    # 3) 环境变量：交给 config 解析，非法值会在这里显式报出。
    try:
        from app.config import settings  # noqa: E402
    except ValueError as exc:
        return fail(
            3,
            "环境变量配置有误（不是依赖问题）",
            [
                str(exc),
                "可参考根目录 .env.example 修正根目录 .env，或直接 `unset` 对应变量走本地默认值。",
            ],
        )

    # 4) 应用与示例数据能否加载。
    try:
        from app.main import app  # noqa: E402,F401
        from app.store import store  # noqa: E402
    except Exception as exc:  # noqa: BLE001
        return fail(4, "应用代码或示例数据加载失败", [f"{type(exc).__name__}: {exc}"])

    occupy_statuses = [str(row.get("status")) for row in store.rows("occupy")]
    expected = ["待审批", "已批准", "施工中", "已完工", "已恢复"]
    absent = [s for s in expected if s not in occupy_statuses]
    if absent:
        return fail(
            4,
            "示例数据不完整",
            [f"占道施工缺少状态样例：{', '.join(absent)}，请检查 app/seed.py。"],
        )

    print(
        f"[启动诊断] 环境就绪：Python {sys.version.split()[0]}，"
        f"APP_ENV={settings.env}，端口 {settings.port}，"
        f"占道施工示例 {len(occupy_statuses)} 条覆盖完整审批链路。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
