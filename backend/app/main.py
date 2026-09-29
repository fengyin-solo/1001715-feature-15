"""特种设备点检运维平台 后端服务入口。

启动：uvicorn app.main:app --host 127.0.0.1 --port 8000
健康检查：GET /api/health
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import ROUTERS
from app.services.operator import OperatorService
from app.store import store

app = FastAPI(title="特种设备点检运维平台", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in ROUTERS:
    app.include_router(module.router)


@app.get("/api/health")
def health() -> dict[str, object]:
    """健康检查：确认服务已经监听、示例数据已经就绪。"""
    return {"ok": True, "app": settings.app_name, "modules": len(store.module_names())}


@app.get("/api/overview")
def overview() -> dict[str, object]:
    """运营概览：把各业务模块的待处理量汇总成看板卡片；持证人数与单位台账同口径。"""
    counts = OperatorService().certified_counts()  # 先重算，确保证照状态与 pending/abnormal 口径一致
    data = store.overview()
    cards = list(data.get("cards") or [])
    found = False
    for card in cards:
        if card.get("label") == "持证人数":
            card["value"] = counts["total_certified"]
            found = True
    if not found:
        cards.append({"label": "持证人数", "value": counts["total_certified"]})
    data["cards"] = cards
    data["certifiedByUnit"] = counts["by_unit"]
    data["certifiedMissing"] = counts["missing"]
    return data
