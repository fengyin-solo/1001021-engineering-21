"""占道施工业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "occupy"
REQUIRED_FIELDS = ["施工编号", "施工位置", "占用范围"]
OPTIONAL_FIELDS = ["施工内容", "申请人", "审批人", "占用期限", "施工状态"]
STATUS_ORDER = ["待审批", "已批准", "施工中", "已完工", "已恢复"]
ACTION_RULES = {
    "审批通过": "已批准",
    "开始施工": "施工中",
    "完工确认": "已完工",
    "恢复通行": "已恢复",
}
NEGATIVE_ACTIONS = []


class OccupyService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("施工编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in REQUIRED_FIELDS + OPTIONAL_FIELDS:
            if field in values and str(values.get(field) or "").strip():
                entry[field] = values[field]
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"占道施工 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于占道施工可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        # 审批通过时允许前端把审批人一并提交，写回记录便于追溯
        approver = str((values or {}).get("审批人") or "").strip()
        if action == "审批通过" and approver:
            entry["审批人"] = approver
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"占道施工已{action}"
