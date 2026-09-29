"""作业人员业务规则：证照归属、状态流转、权限校验与筛选口径都收在这里。

核心口径：
- 一人可持多份有效证照，按复审日期更晚的一份确定归属单位与在岗状态。
- 证照到期后人员状态自动变为证件过期；复审完成后回到在岗持证。
- 只有本单位管理员能维护本单位人员，跨单位修改会被拦下并提示。
- 历史复审记录的复审单位冻结在复审发生时，不随后续归属变更改变。
- 单位台账与运营概览的持证人数共用 certified_counts() 同一份口径。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "operator"
REQUIRED_FIELDS = ["人员编号", "人员姓名", "所属单位"]
STATUS_ORDER = ["待取证", "在岗持证", "证件过期", "已离岗"]
# 动作 -> 目标状态（复审、登记取证走单独的证照逻辑）
ACTION_RULES = {"登记取证": "在岗持证", "标记过期": "证件过期", "办理离岗": "已离岗"}
# 需要归属权限校验的维护动作
GUARDED_ACTIONS = {"登记取证", "复审", "标记过期", "办理离岗", "归属变更"}
# 平台覆盖的单位（用于单位台账兜底展示）
UNITS = ["运行一班", "运行二班"]


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except (ValueError, TypeError):
        return None


def _today() -> date:
    return date.today()


def _primary_cert(entry: dict[str, Any]) -> dict[str, Any] | None:
    """取复审日期最晚的一份有效证照；没有证照时返回 None。"""
    certs = entry.get("certificates") or []
    if not certs:
        return None
    return max(certs, key=lambda c: _parse_date(c.get("复审日期")) or date.min)


def _has_complete_cert(entry: dict[str, Any]) -> bool:
    """是否持有信息完整（有证件编号、有有效期至）的证照。"""
    primary = _primary_cert(entry)
    if primary is None:
        return False
    return bool(str(primary.get("证件编号") or "").strip() and str(primary.get("有效期至") or "").strip())


def compute_status(entry: dict[str, Any]) -> str:
    """根据证照有效期与离岗状态计算人员状态。

    手动标记（标记过期、办理离岗）通过 statusOverride 粘住，不被自动重算覆盖；
    复审、登记取证会清除手动标记，回到按证照有效期自动判定。
    """
    override = entry.get("statusOverride")
    if override:
        return str(override)
    primary = _primary_cert(entry)
    if primary is None or not _has_complete_cert(entry):
        return "待取证"
    expiry = _parse_date(primary.get("有效期至"))
    if expiry is not None and expiry < _today():
        return "证件过期"
    return "在岗持证"


def recompute_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """根据证照列表重算人员的归属单位、作业项目、证件信息与状态。

    归属单位取复审日期最晚证照的所属单位；状态由有效期自动判定，手动标记优先。
    """
    primary = _primary_cert(entry)
    if primary is not None:
        entry["所属单位"] = str(primary.get("所属单位") or "")
        entry["作业项目"] = str(primary.get("作业项目") or "")
        entry["证件编号"] = str(primary.get("证件编号") or "")
        entry["有效期至"] = str(primary.get("有效期至") or "")
        entry["复审日期"] = str(primary.get("复审日期") or "")
    else:
        # 无有效证照时保留已登记的所属单位（待取证人员可先挂在单位下），不清空
        entry["作业项目"] = ""
        entry["证件编号"] = ""
        entry["有效期至"] = ""
        entry["复审日期"] = ""
    entry["人员状态"] = compute_status(entry)
    entry["status"] = entry["人员状态"]
    entry["missingCert"] = not _has_complete_cert(entry)
    entry["pending"] = entry["人员状态"] != "已离岗"
    entry["abnormal"] = entry["人员状态"] == "证件过期"
    return entry


class OperatorService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        unit: str | None = None,
        missing_only: bool = False,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        for row in rows:
            recompute_entry(row)
        if keyword:
            kw = keyword.strip()
            rows = [row for row in rows if kw in str(row.get("人员编号", "")) or kw in str(row.get("人员姓名", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if unit:
            rows = [row for row in rows if row.get("所属单位") == unit]
        if missing_only:
            rows = [row for row in rows if row.get("missingCert")]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is not None:
            recompute_entry(entry)
        return entry

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["certificates"] = []
        entry["reviewRecords"] = []
        entry["status"] = "待取证"
        entry["pending"] = True
        entry["abnormal"] = False
        # 登记时可一并录入首张证照
        if str(values.get("作业项目") or "").strip() or str(values.get("证件编号") or "").strip():
            entry["certificates"].append({
                "作业项目": str(values.get("作业项目") or "").strip(),
                "证件编号": str(values.get("证件编号") or "").strip(),
                "有效期至": str(values.get("有效期至") or "").strip(),
                "复审日期": str(values.get("复审日期") or "").strip(),
                "所属单位": str(values.get("所属单位") or "").strip(),
            })
        recompute_entry(entry)
        rows.append(entry)
        return entry, []

    def _check_permission(self, entry: dict[str, Any], admin_unit: str | None) -> str | None:
        """跨单位修改拦截：只有本单位管理员能维护本单位人员；未归属人员任意单位可接手。"""
        if not admin_unit:
            return None  # 未携带单位信息时不拦截（骨架环境），前端始终携带
        person_unit = str(entry.get("所属单位") or "")
        if person_unit and person_unit != admin_unit:
            return (
                f"跨单位修改被拦下：该人员归属「{person_unit}」，"
                f"你当前是「{admin_unit}」管理员，无权改动；请联系该单位管理员处理"
            )
        return None

    def run_action(
        self,
        entry_id: int,
        action: str,
        admin_unit: str | None = None,
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"作业人员 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES and action not in ("复审", "归属变更"):
            return None, f"动作「{action}」不属于作业人员可执行范围"
        if action in GUARDED_ACTIONS:
            denied = self._check_permission(entry, admin_unit)
            if denied:
                return None, denied
        values = values or {}
        if action == "登记取证":
            return self._register_cert(entry, values)
        if action == "复审":
            return self._review(entry, values)
        if action == "归属变更":
            return self._transfer(entry, values)
        target = ACTION_RULES[action]
        # 手动标记粘住状态，后续重算不覆盖；复审/登记取证会清除
        entry["statusOverride"] = target
        entry["status"] = target
        entry["人员状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action == "标记过期"
        return entry, f"作业人员已{action}"

    def _register_cert(self, entry: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        cert = {
            "作业项目": str(values.get("作业项目") or "").strip(),
            "证件编号": str(values.get("证件编号") or "").strip(),
            "有效期至": str(values.get("有效期至") or "").strip(),
            "复审日期": str(values.get("复审日期") or "").strip(),
            "所属单位": str(values.get("所属单位") or entry.get("所属单位") or "").strip(),
        }
        if not cert["作业项目"] or not cert["证件编号"]:
            return None, "登记取证需填写作业项目与证件编号"
        certs = entry.setdefault("certificates", [])
        existing = next((c for c in certs if c.get("作业项目") == cert["作业项目"]), None)
        if existing:
            existing.update(cert)
        else:
            certs.append(cert)
        # 登记取证后清除手动标记，状态回到按证照自动判定
        entry["statusOverride"] = None
        recompute_entry(entry)
        return entry, "作业人员已登记取证"

    def _review(self, entry: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        primary = _primary_cert(entry)
        if primary is None:
            return None, "该人员暂无有效证照，无法复审，请先登记取证"
        review_date = str(values.get("复审日期") or "").strip()
        if not review_date:
            return None, "复审需填写复审日期"
        primary["复审日期"] = review_date
        if values.get("有效期至"):
            primary["有效期至"] = str(values.get("有效期至")).strip()
        else:
            # 复审通过后证照延续有效期：默认自复审日期起 4 年（特种设备作业人员证有效期）
            rd = _parse_date(review_date)
            if rd is not None:
                try:
                    expiry = rd.replace(year=rd.year + 4)
                except ValueError:
                    expiry = rd.replace(year=rd.year + 4, day=28)
                primary["有效期至"] = expiry.isoformat()
        if values.get("所属单位"):
            primary["所属单位"] = str(values.get("所属单位")).strip()
        # 历史复审记录：复审单位冻结在复审发生时，不随后续归属变更改变
        entry.setdefault("reviewRecords", []).append({
            "复审日期": review_date,
            "作业项目": str(primary.get("作业项目") or ""),
            "复审单位": str(primary.get("所属单位") or ""),
            "复审结果": "合格",
        })
        # 复审完成后清除手动标记，状态回到按证照自动判定
        entry["statusOverride"] = None
        recompute_entry(entry)
        return entry, "作业人员复审完成，状态已更新为在岗持证"

    def _transfer(self, entry: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        new_unit = str(values.get("所属单位") or "").strip()
        if not new_unit:
            return None, "归属变更需填写转入单位"
        primary = _primary_cert(entry)
        if primary is None:
            return None, "该人员暂无有效证照，无法变更归属"
        old_unit = str(primary.get("所属单位") or "")
        primary["所属单位"] = new_unit
        recompute_entry(entry)
        return entry, f"作业人员归属已由「{old_unit or '未归属'}」变更为「{new_unit}」"

    def certified_counts(self) -> dict[str, Any]:
        """持证人数按单位统计：单位台账与运营概览共用同一份口径。

        只统计非离岗、证照信息完整且在有效期内的人员；证照缺失人员单独计数。
        """
        rows = store.rows(MODULE)
        for row in rows:
            recompute_entry(row)
        by_unit: dict[str, int] = {}
        total_certified = 0
        total_people = 0
        missing = 0
        for row in rows:
            if row.get("status") == "已离岗":
                continue
            total_people += 1
            if row.get("missingCert"):
                missing += 1
            if row.get("人员状态") == "在岗持证":
                total_certified += 1
                unit = str(row.get("所属单位") or "未归属")
                by_unit[unit] = by_unit.get(unit, 0) + 1
        return {
            "total_certified": total_certified,
            "total_people": total_people,
            "missing": missing,
            "by_unit": by_unit,
        }

    def unit_ledger(self) -> dict[str, Any]:
        """单位台账：按单位列出持证人数，与运营概览同口径。"""
        counts = self.certified_counts()
        units = list(UNITS) + [u for u in counts["by_unit"] if u not in UNITS]
        ledger = [{"单位": unit, "持证人数": counts["by_unit"].get(unit, 0)} for unit in units]
        return {
            "total_certified": counts["total_certified"],
            "total_people": counts["total_people"],
            "missing": counts["missing"],
            "ledger": ledger,
        }
