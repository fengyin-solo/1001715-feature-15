"""作业人员接口：证照归属台账、复审流转与按单位隔离的维护权限。

维护类接口都要带 X-Admin-Unit 请求头声明当前管理员所属单位；
跨单位的修改在 services 层被拦下，这里原样把拒绝原因返回给页面提示。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services import attribution
from app.services.operator import OperatorService

router = APIRouter(prefix="/api/operator", tags=["作业人员"])

service = OperatorService()

LIST_COLUMNS = ["人员编号", "人员姓名", "归属单位", "作业项目", "证件编号", "有效期至", "复审日期", "人员状态"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按人员编号或姓名检索"),
    status: str | None = Query(default=None, description="待取证、在岗持证、证件过期、已离岗"),
    unit: str | None = Query(default=None, description="按归属单位过滤"),
    missing: bool = Query(default=False, description="只列证照信息缺失人员"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按归属单位、状态与关键字过滤作业人员；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        keyword=keyword, status=status, unit=unit, missing_only=missing, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/projects")
def list_projects() -> dict[str, Any]:
    """作业项目与归属单位对照表。"""
    return {"items": attribution.projects(), "units": attribution.units()}


@router.get("/ledger")
def unit_ledger() -> dict[str, Any]:
    """单位台账：各单位持证人数与全平台持证合计，口径与运营概览一致。"""
    return service.ledger()


@router.get("/missing")
def list_missing() -> dict[str, Any]:
    """证照信息缺失人员单独列出，便于本单位管理员补录。"""
    return {"items": service.missing_entries()}


@router.get("/reviews")
def list_reviews(unit: str | None = Query(default=None, description="按复审时归属单位过滤")) -> dict[str, Any]:
    """复审历史：按当时的单位快照留档，可按原单位查看。"""
    return {"items": service.reviews(unit)}


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出作业人员清单：返回全量派生数据（含归属单位与自动状态）。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "operator", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条作业人员明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"作业人员 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload, x_admin_unit: str = Header(default="")) -> ActionResult:
    """登记一条作业人员；人员编号重复或字段缺失时说明原因。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        if missing == ["人员编号"]:
            return ActionResult(ok=False, message="人员编号已存在，不能重复登记")
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="作业人员已登记，尚无有效证照，已列入证照信息缺失清单", entry=entry)


@router.post("/{entry_id}/certificates", response_model=ActionResult)
def add_certificate(
    entry_id: int, payload: EntryPayload, x_admin_unit: str = Header(default="")
) -> ActionResult:
    """本单位管理员为人员补录证照；跨单位修改会被拦下并提示。"""
    entry, message = service.add_certificate(entry_id, payload.values, x_admin_unit)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/reviews", response_model=ActionResult)
def review_certificate(
    entry_id: int, payload: EntryPayload, x_admin_unit: str = Header(default="")
) -> ActionResult:
    """复审完成：证照更新后人员自动恢复在岗持证；跨单位复审会被拦下。"""
    entry, message = service.review_certificate(entry_id, payload.values, x_admin_unit)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/leave", response_model=ActionResult)
def leave(entry_id: int, x_admin_unit: str = Header(default="")) -> ActionResult:
    """本单位管理员为人员办理离岗。"""
    entry, message = service.leave(entry_id, x_admin_unit)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
