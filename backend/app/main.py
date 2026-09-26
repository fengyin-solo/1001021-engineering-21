"""市政道路桥梁养护管理平台 后端服务入口。

启动：uvicorn app.main:app --host 127.0.0.1 --port 8000
健康检查：GET /api/health
占道链路自检：make check（或 backend/scripts/check_occupy.py）
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import ROUTERS
from app.store import store

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="市政道路桥梁养护管理平台", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in ROUTERS:
    app.include_router(module.router)


@app.on_event("startup")
def _on_startup() -> None:
    occupy_rows = len(store.rows("occupy"))
    logger.info(
        "示例数据已灌入：共 %d 个业务模块；占道施工 %d 条（待审批 -> 已批准 -> 施工中 -> 已完工 -> 已恢复）",
        len(store.module_names()),
        occupy_rows,
    )
    logger.info("链路自检入口：make check（或 backend/scripts/check_occupy.py）")


@app.get("/api/health")
def health() -> dict[str, object]:
    """健康检查：确认服务已经监听、示例数据已经就绪。"""
    return {
        "ok": True,
        "app": settings.app_name,
        "env": settings.env,
        "modules": len(store.module_names()),
        "occupy": len(store.rows("occupy")),
    }


@app.get("/api/overview")
def overview() -> dict[str, object]:
    """运营概览：把各业务模块的待处理量汇总成看板卡片。"""
    return store.overview()
