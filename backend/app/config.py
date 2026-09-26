"""运行配置：端口、跨域、运行环境。

本地开发（APP_ENV 未设置或为 local）使用内置默认值，clone 下来即可启动；
非 local 环境必须显式提供 APP_SECRET_KEY，由 app.config 加载时校验，
避免「环境变量没配」被拖到请求期才暴露。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


class ConfigError(RuntimeError):
    """配置缺失或非法：启动阶段直接抛出，消息里说明缺的是哪个环境变量。"""


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"环境变量 {name} 必须是整数，当前值：{raw!r}") from exc


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str
    env: str
    port: int
    secret_key: str
    allowed_origins: list[str] = field(
        default_factory=lambda: [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]
    )
    page_size_default: int = 20
    page_size_max: int = 200


def load_settings() -> Settings:
    """从环境变量组装配置；非 local 环境缺少 APP_SECRET_KEY 时直接报错。"""
    env = os.environ.get("APP_ENV", "local").strip() or "local"
    secret_key = os.environ.get("APP_SECRET_KEY", "").strip()
    if env != "local" and not secret_key:
        raise ConfigError(
            "环境变量 APP_SECRET_KEY 未配置：非本地环境（APP_ENV="
            f"{env}）必须提供；本地开发可保持 APP_ENV=local 使用内置默认值。"
        )
    values: dict[str, Any] = {
        "app_name": os.environ.get("APP_NAME", "市政道路桥梁养护管理平台"),
        "env": env,
        "port": _env_int("APP_PORT", 8000),
        "secret_key": secret_key or "local-dev-secret",
        "allowed_origins": _env_list(
            "APP_CORS_ORIGINS",
            ["http://127.0.0.1:5173", "http://localhost:5173"],
        ),
    }
    return Settings(**values)


settings = load_settings()
