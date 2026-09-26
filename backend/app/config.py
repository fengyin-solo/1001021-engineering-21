"""运行配置：从环境变量（含项目根目录 .env）读取端口、跨域、运行环境等。

本地开发可以一个环境变量都不配：下面的默认值足够把前后端跑起来。
显式设置时以环境变量为准，方便区分 local / staging / production。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# 后端目录的上一级即仓库根目录；根目录放 .env，本地开发不用到处 export。
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_DIR.parent
load_dotenv(_REPO_ROOT / ".env")


def _parse_origins(raw: str | None) -> list[str]:
    if not raw:
        return ["http://127.0.0.1:5173", "http://localhost:5173"]
    origins = [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]
    return origins or ["http://127.0.0.1:5173", "http://localhost:5173"]


def _parse_port(raw: str | None) -> int:
    if not raw:
        return 8000
    try:
        port = int(raw)
    except ValueError:
        raise ValueError(f"APP_PORT 必须是 1024-65535 之间的整数，当前值：{raw!r}") from None
    if not 1024 <= port <= 65535:
        raise ValueError(f"APP_PORT 超出 1024-65535 范围：{port}")
    return port


_VALID_ENVS = {"local", "dev", "staging", "production", "prod", "test"}


def _build_settings() -> "Settings":
    env = (os.getenv("APP_ENV") or "local").strip()
    if env not in _VALID_ENVS:
        raise ValueError(
            f"APP_ENV={env!r} 不被识别，可选值：{', '.join(sorted(_VALID_ENVS))}"
        )
    return Settings(
        app_name=(os.getenv("APP_NAME") or "市政道路桥梁养护管理平台").strip(),
        env=env,
        port=_parse_port(os.getenv("APP_PORT")),
        host=(os.getenv("APP_HOST") or "127.0.0.1").strip(),
        allowed_origins=_parse_origins(os.getenv("CORS_ORIGINS")),
        page_size_default=int(os.getenv("PAGE_SIZE_DEFAULT") or "20"),
        page_size_max=int(os.getenv("PAGE_SIZE_MAX") or "200"),
    )


@dataclass(frozen=True)
class Settings:
    app_name: str
    env: str
    port: int
    host: str
    allowed_origins: list[str] = field(default_factory=list)
    page_size_default: int = 20
    page_size_max: int = 200


settings = _build_settings()
