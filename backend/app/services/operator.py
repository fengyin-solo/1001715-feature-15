"""作业人员业务规则：证照归属、单位维护权限、状态自动流转与筛选口径都收在这里。

与旧版相比：
- 状态不再由手工动作切换：证照过期自动变「证件过期」，复审提交自动变「在岗持证」；
- 归属单位按作业项目映射、由有效证照中复审日期最晚的一份决定；
- 只有归属单位（证照缺失时为人员登记单位）的管理员能维护，跨单位修改一律拦下；
- 每次写操作后人员归属与状态按 services.attribution 的统一口径重新派生。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.services import attribution
from app.store import store

MODULE = "operator"
CERT_MODULE = "operator_certificate"
REVIEW_MODULE = "operator_review"

REQUIRED_FIELDS = ["人员编号", "人员姓名", "所属单位"]
# 复审 / 补录证照时需要的证照字段
CERT_FIELDS = ["作业项目", "证件编号", "有效期至", "复审日期"]


class OperatorService:
    # ---------- 读 ----------

    def _views(self) -> list[dict[str, Any]]:
        return attribution.build_person_views(
            store.rows(MODULE), store.rows(CERT_MODULE)
        )

    def ledger(self) -> dict[str, Any]:
        """单位台账：持证人数等指标全部走统一口径。"""
        views = self._views()
        return {
            "items": attribution.build_ledger(views),
            "持证人数": attribution.certified_count(views),
        }

    def reviews(self, unit: str | None = None) -> list[dict[str, Any]]:
        """复审历史：按当时的归属单位快照留档，归属变更后仍挂在原单位名下。"""
        rows = list(store.rows(REVIEW_MODULE))
        people = {str(p.get("人员编号")): p.get("人员姓名") for p in store.rows(MODULE)}
        for row in rows:
            row.setdefault("人员姓名", people.get(str(row.get("人员编号")), ""))
        if unit:
            rows = [row for row in rows if row.get("归属单位") == unit]
        return sorted(rows, key=lambda row: str(row.get("复审日期")), reverse=True)

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
        rows = self._views()
        if unit:
            rows = [row for row in rows if row["归属单位"] == unit]
        if keyword:
            rows = [
                row for row in rows
                if keyword in str(row.get("人员编号", "")) or keyword in str(row.get("人员姓名", ""))
            ]
        if status:
            rows = [row for row in rows if row.get("人员状态") == status]
        if missing_only:
            rows = [row for row in rows if row.get("证照信息缺失")]
        total = len(rows)
        start = max(page - 1, 0) * size
        return self._public(rows[start:start + size]), total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        for view in self._views():
            if int(view.get("id", 0)) == entry_id:
                return self._public(view)
        return None

    def missing_entries(self) -> list[dict[str, Any]]:
        return [self._public(row) for row in self._views() if row.get("证照信息缺失")]

    @staticmethod
    def _public(view: dict[str, Any]) -> dict[str, Any]:
        """去掉内部字段再出参。"""
        return {key: value for key, value in view.items() if not key.startswith("_")}

    # ---------- 权限 ----------

    @staticmethod
    def _guard(view: dict[str, Any], admin_unit: str) -> str | None:
        """跨单位修改拦截：返回 None 放行，否则返回可读的拒绝原因。"""
        admin_unit = (admin_unit or "").strip()
        if not admin_unit:
            return "未识别到当前管理员所属单位，无法执行维护操作"
        if view["归属单位"] != admin_unit:
            return (
                f"跨单位修改被拦截：人员「{view.get('人员姓名')}」归属{view['归属单位'] or '未划单位'}，"
                f"当前管理员属于{admin_unit}，仅本单位管理员可维护"
            )
        return None

    def _find_view(self, entry_id: int) -> dict[str, Any] | None:
        for view in self._views():
            if int(view.get("id", 0)) == entry_id:
                return view
        return None

    # ---------- 写 ----------

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        if any(str(row.get("人员编号")) == str(values["人员编号"]).strip() for row in rows):
            return None, ["人员编号"]
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: str(values.get(field)).strip() for field in REQUIRED_FIELDS})
        if str(values.get("作业项目") or "").strip():
            entry["作业项目"] = str(values["作业项目"]).strip()
        entry["离岗"] = False
        rows.append(entry)
        return self.get_entry(entry["id"]), []

    def add_certificate(
        self, entry_id: int, values: dict[str, Any], admin_unit: str
    ) -> tuple[dict[str, Any] | None, str]:
        """补录 / 新增一份证照（用于取证或跨项目调入）。归属随有效证自动重算。"""
        view = self._find_view(entry_id)
        if view is None:
            return None, f"作业人员 {entry_id} 不存在或已归档"
        denied = self._guard(view, admin_unit)
        if denied:
            return None, denied
        project = str(values.get("作业项目") or "").strip()
        cert_unit = attribution.unit_of_project(project)
        if not cert_unit:
            return None, f"作业项目「{project}」未配置归属单位，不能据此划单位"
        missing = [field for field in CERT_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"证照信息不完整，缺少：{'、'.join(missing)}"
        if attribution.parse_date(values.get("有效期至")) is None:
            return None, "有效期至需为 YYYY-MM-DD 日期格式"
        if attribution.parse_date(values.get("复审日期")) is None:
            return None, "复审日期需为 YYYY-MM-DD 日期格式"
        self._insert_certificate(view["人员编号"], values, cert_unit)
        new_view = self._find_view(entry_id)
        message = f"证照已登记，{view['人员姓名']}状态为{new_view['人员状态']}"
        if new_view["归属单位"] != view["归属单位"]:
            message += f"，归属随证照变更为{new_view['归属单位']}"
        return self._public(new_view), message

    def review_certificate(
        self,
        entry_id: int,
        values: dict[str, Any],
        admin_unit: str,
    ) -> tuple[dict[str, Any] | None, str]:
        """复审完成：更新当前权威证照，人员自动回到在岗持证，并留下带单位快照的历史记录。"""
        view = self._find_view(entry_id)
        if view is None:
            return None, f"作业人员 {entry_id} 不存在或已归档"
        if view["人员状态"] == attribution.STATUS_LEFT:
            return None, "该人员已离岗，不再受理复审"
        denied = self._guard(view, admin_unit)
        if denied:
            return None, denied

        review_date = str(values.get("复审日期") or "").strip()
        expire_at = str(values.get("有效期至") or "").strip()
        if not review_date:
            review_date = date.today().isoformat()
        if attribution.parse_date(review_date) is None:
            return None, "复审日期需为 YYYY-MM-DD 日期格式"
        if expire_at and attribution.parse_date(expire_at) is None:
            return None, "有效期至需为 YYYY-MM-DD 日期格式"

        cert_id = values.get("证件id") or view.get("_cert_id")
        cert = store.find(CERT_MODULE, int(cert_id)) if cert_id else None
        if cert is None:
            return None, "该人员名下没有可复审的证照，请先补录证照信息"
        if not expire_at:
            old_expire = attribution.parse_date(cert.get("有效期至"))
            old_review = attribution.parse_date(cert.get("复审日期"))
            if old_expire and old_review and old_expire > old_review:
                span = old_expire - old_review
                expire_at = (attribution.parse_date(review_date) + span).isoformat()
            else:
                expire_at = review_date
        cert["复审日期"] = review_date
        cert["有效期至"] = expire_at

        history = store.rows(REVIEW_MODULE)
        history.append({
            "id": max((int(row.get("id", 0)) for row in history), default=0) + 1,
            "人员编号": view["人员编号"],
            "人员姓名": view["人员姓名"],
            "作业项目": cert.get("作业项目"),
            "证件编号": cert.get("证件编号"),
            # 归属单位取复审发生时的单位快照：以后人员调走，这条记录仍在原单位名下
            "归属单位": view["归属单位"],
            "复审日期": review_date,
            "有效期至": expire_at,
        })
        new_view = self._find_view(entry_id)
        return self._public(new_view), f"复审完成，{view['人员姓名']}已恢复在岗持证"

    def leave(self, entry_id: int, admin_unit: str) -> tuple[dict[str, Any] | None, str]:
        """办理离岗：只有归属单位能办。"""
        view = self._find_view(entry_id)
        if view is None:
            return None, f"作业人员 {entry_id} 不存在或已归档"
        denied = self._guard(view, admin_unit)
        if denied:
            return None, denied
        person = store.find(MODULE, entry_id)
        person["离岗"] = True
        new_view = self._find_view(entry_id)
        return self._public(new_view), f"{view['人员姓名']}已办理离岗"

    def _insert_certificate(
        self, person_no: str, values: dict[str, Any], cert_unit: str
    ) -> dict[str, Any]:
        rows = store.rows(CERT_MODULE)
        cert = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        cert.update({
            "人员编号": person_no,
            "作业项目": str(values["作业项目"]).strip(),
            "证件编号": str(values["证件编号"]).strip(),
            "有效期至": str(values["有效期至"]).strip(),
            "复审日期": str(values["复审日期"]).strip(),
            "归属单位": cert_unit,
        })
        rows.append(cert)
        return cert
