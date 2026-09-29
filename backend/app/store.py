"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
"""
from __future__ import annotations

from typing import Any

from app.seed import SEED_ROWS


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {
            name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()
        }

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def overview(self) -> dict[str, object]:
        from app.services import attribution

        # 作业人员持证口径唯一来源：单位台账与这里的概览数字都从这份派生视图计算
        person_views = attribution.build_person_views(
            self.rows("operator"), self.rows("operator_certificate")
        )
        certified = attribution.certified_count(person_views)
        operator_ledger = attribution.build_ledger(person_views)

        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            item = {
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            }
            if name == "operator":
                # 与 /api/operator/ledger 完全一致的口径，避免两处对不上账
                item["持证人数"] = certified
                item["证照缺失"] = sum(1 for view in person_views if view["证照信息缺失"])
                item["证件过期"] = sum(1 for view in person_views if view["人员状态"] == "证件过期")
            modules.append(item)
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
            {"label": "持证作业人员", "value": certified},
        ]
        return {"cards": cards, "modules": modules, "operator_ledger": operator_ledger}


store = Store()
