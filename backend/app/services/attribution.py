"""作业人员证照归属口径：归属单位、人员状态、台账持证人数全部从这里的同一份派生数据计算。

路由层与 store.overview 都只能调用这里的函数，避免单位台账与运营概览各算各的、对不上账。

规则：
- 作业项目与归属单位是固定对应关系（PROJECT_UNITS），人员按证照划到单位名下；
- 证照信息完整且「有效期至」晚于当天才算有效；
- 同一个人有多份有效证照时，以复审日期更晚的一份为准（决定归属与展示证件）；
- 没有有效证、但存在信息完整的过期证 → 证件过期，归属仍挂在最后一张证的单位；
- 一张信息完整的证照都没有（无证或关键字段缺失）→ 待取证，列入证照信息缺失清单；
- 已离岗为人工标记，优先级最高。
"""
from __future__ import annotations

from datetime import date
from typing import Any

# 作业项目 → 证照归属单位
PROJECT_UNITS: dict[str, str] = {
    "焊接与热切割作业": "第一分公司",
    "起重机械作业": "第二分公司",
    "厂内机动车辆作业": "第二分公司",
    "压力容器作业": "第三分公司",
    "压力管道作业": "第三分公司",
    "电工作业": "第四分公司",
}

# 证照信息关键字段：缺任意一项都视为证照信息缺失，不能参与有效判定
CERT_REQUIRED_FIELDS = ("证件编号", "有效期至", "复审日期")

STATUS_PENDING = "待取证"
STATUS_CERTIFIED = "在岗持证"
STATUS_EXPIRED = "证件过期"
STATUS_LEFT = "已离岗"


def projects() -> list[dict[str, str]]:
    """作业项目与归属单位对照表，供下拉选项与前端展示使用。"""
    return [{"作业项目": project, "所属单位": unit} for project, unit in PROJECT_UNITS.items()]


def units() -> list[str]:
    return sorted(set(PROJECT_UNITS.values()))


def unit_of_project(project: Any) -> str:
    return PROJECT_UNITS.get(str(project or "").strip(), "")


def parse_date(value: Any) -> date | None:
    """宽容解析 YYYY-MM-DD；解析不了（含占位文字、空值）返回 None。"""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def is_cert_complete(cert: dict[str, Any]) -> bool:
    """证照三个关键字段都有且日期可解析，才算信息完整。"""
    if any(not str(cert.get(field) or "").strip() for field in CERT_REQUIRED_FIELDS):
        return False
    return parse_date(cert.get("有效期至")) is not None and parse_date(cert.get("复审日期")) is not None


def _review_key(cert: dict[str, Any])    -> date:
    return parse_date(cert.get("复审日期")) or date.min


def _sort_key(cert: dict[str, Any]) -> tuple[int, date, int]:
    # 复审日期更晚者优先；日期相同用 id 兜底，保证口径稳定
    return (0, _review_key(cert), int(cert.get("id", 0)))


def build_person_views(
    people: list[dict[str, Any]],
    certs: list[dict[str, Any]],
    *,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """把人员表与证照表合成一份带「归属单位 / 人员状态」的派生视图。

    归属与状态只在本函数里推导，任何写入操作完成后重新调用即可，不落库存储。
    """
    today = today or date.today()
    views: list[dict[str, Any]] = []
    for person in people:
        person_no = str(person.get("人员编号") or "")
        own_certs = [cert for cert in certs if str(cert.get("人员编号") or "") == person_no]
        complete = [cert for cert in own_certs if is_cert_complete(cert)]
        valid = [cert for cert in complete if (parse_date(cert.get("有效期至")) or date.min) >= today]

        # 有效证里复审日期最晚的一份；没有有效证时退而取信息完整证里最晚的一张
        authoritative = max(valid, key=_sort_key) if valid else (
            max(complete, key=_sort_key) if complete else None
        )

        left = bool(person.get("离岗"))
        if left:
            status = STATUS_LEFT
        elif valid:
            status = STATUS_CERTIFIED
        elif complete:
            status = STATUS_EXPIRED
        else:
            status = STATUS_PENDING

        if authoritative is not None:
            unit = unit_of_project(authoritative.get("作业项目")) or str(person.get("所属单位") or "")
            project = authoritative.get("作业项目")
            cert_no = authoritative.get("证件编号")
            expire_at = authoritative.get("有效期至")
            review_at = authoritative.get("复审日期")
            cert_id = authoritative.get("id")
        else:
            # 证照缺失时归属仍挂在人员登记的所属单位，本单位管理员负责补录
            unit = str(person.get("所属单位") or "")
            project = person.get("作业项目")
            cert_no = expire_at = review_at = None
            cert_id = None

        views.append({
            "id": person.get("id"),
            "人员编号": person_no,
            "人员姓名": person.get("人员姓名"),
            "归属单位": unit,
            "作业项目": project,
            "证件编号": cert_no,
            "有效期至": expire_at,
            "复审日期": review_at,
            "人员状态": status,
            "证照信息缺失": not complete and not left,
            "证照份数": len(own_certs),
            # 内部字段：当前权威证照 id，复审时定位要更新的那张证
            "_cert_id": cert_id,
        })
    return views


def build_ledger(views: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按归属单位汇总台账：人员总数、持证人数、证件过期、证照缺失。

    单位台账页面与运营概览共用本函数，所以两处持证人数永远来自同一份数据。
    """
    units: dict[str, dict[str, Any]] = {}
    for view in views:
        unit = view["归属单位"] or "未划单位"
        bucket = units.setdefault(unit, {
            "所属单位": unit, "人员总数": 0, "持证人数": 0,
            "证件过期": 0, "证照缺失": 0,
        })
        bucket["人员总数"] += 1
        if view["人员状态"] == STATUS_CERTIFIED:
            bucket["持证人数"] += 1
        elif view["人员状态"] == STATUS_EXPIRED:
            bucket["证件过期"] += 1
        if view["证照信息缺失"]:
            bucket["证照缺失"] += 1
    return [units[name] for name in sorted(units)]


def certified_count(views: list[dict[str, Any]]) -> int:
    """全平台持证人数：在岗持证才算，过期与缺失都不计入。"""
    return sum(1 for view in views if view["人员状态"] == STATUS_CERTIFIED)
