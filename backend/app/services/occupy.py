"""占道施工业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "occupy"
# 登记时必须给到的字段；审批人、占用期限在「审批通过」时才补齐，故不在此列。
REQUIRED_FIELDS = ["施工编号", "施工位置", "占用范围", "申请人"]
# 完整审批链路：从待审批，到批准、施工、完工，最后恢复通行。
STATUS_ORDER = ["待审批", "已批准", "施工中", "已完工", "已恢复"]
# 动作 -> 目标状态。动作只能沿链路逐级前进，不允许跨级或回退。
ACTION_RULES = {"审批通过": "已批准", "开始施工": "施工中", "施工完成": "已完工", "恢复通行": "已恢复"}
# 审批通过时需要在流转数据里一并补齐的信息。
APPROVE_FIELDS = ["审批人", "占用期限"]
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
        duplicate = next((row for row in rows if str(row.get("施工编号")) == str(values["施工编号"]).strip()), None)
        if duplicate is not None:
            return None, [f"施工编号 {values['施工编号']} 已存在"]
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        # 登记阶段只固化申报信息；审批人/占用期限留到审批环节再补。
        entry.update({
            "施工编号": str(values["施工编号"]).strip(),
            "施工位置": str(values["施工位置"]).strip(),
            "占用范围": str(values["占用范围"]).strip(),
            "施工内容": str(values.get("施工内容") or "").strip() or "—",
            "申请人": str(values["申请人"]).strip(),
            "审批人": "",
            "占用期限": "",
            "审批时间": "",
            "施工状态": "待审批",
        })
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        values = values or {}
        if entry is None:
            return None, f"占道施工 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于占道施工可执行范围"
        target = ACTION_RULES[action]
        current = str(entry.get("status") or "")
        current_index = STATUS_ORDER.index(current) if current in STATUS_ORDER else -1
        target_index = STATUS_ORDER.index(target)
        if current_index < 0:
            return None, f"当前状态「{current}」不在允许的状态序列里"
        if target_index != current_index + 1:
            if target_index <= current_index:
                return None, f"{current}的占道施工不能执行「{action}」，状态不可回退"
            return None, f"占道施工需先完成「{STATUS_ORDER[current_index + 1]}」之前的环节，不能从{current}直接{action}"
        # 审批通过时必须明确审批人和占用期限，否则链路信息不完整。
        if action == "审批通过":
            supplied = {
                "审批人": str(values.get("审批人") or entry.get("审批人") or "").strip(),
                "占用期限": str(values.get("占用期限") or entry.get("占用期限") or "").strip(),
            }
            absent = [name for name, value in supplied.items() if not value]
            if absent:
                return None, f"审批通过前请补全：{'、'.join(absent)}"
            entry["审批人"] = supplied["审批人"]
            entry["占用期限"] = supplied["占用期限"]
            # 调用方不传审批时间时，用服务端当前时间留痕，保证链路时间完整。
            entry["审批时间"] = (
                str(values.get("审批时间") or "").strip()
                or datetime.now().strftime("%Y-%m-%d %H:%M")
            )
        entry["status"] = target
        entry["施工状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"占道施工已{action}"
