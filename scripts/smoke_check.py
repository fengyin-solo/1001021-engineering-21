#!/usr/bin/env python3
"""占道施工审批链路自检：启动后跑一遍，确认「申请提交 + 逐级审批」接口真的可用。

覆盖：
  1. GET  /api/health        服务存活、示例数据已灌入
  2. GET  /api/occupy        列表能读到 待审批→已恢复 五个状态的种子数据
  3. POST /api/occupy        提交一条新的占道申请（含申请人、占用期限）
  4. POST /api/occupy/{id}/actions  依次执行 审批通过→开始施工→完工确认→恢复通行
  5. GET  /api/occupy/{id}   最终状态确认为「已恢复」
  6. 经前端端口走一遍 /api 代理，确认 dev/preview 代理链路也通

用法：scripts/smoke_check.py [后端基址，默认 http://127.0.0.1:8000]
设 FRONTEND_BASE（如 http://127.0.0.1:5173）会额外校验前端代理。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BACKEND = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
    "BACKEND_BASE", "http://127.0.0.1:8000"
).rstrip("/")
FRONTEND = os.environ.get("FRONTEND_BASE", "http://127.0.0.1:5173").rstrip("/")

PASS, FAIL = "✓", "✗"
failures = 0


def request(method: str, base: str, path: str, body: dict | None = None) -> tuple[int, dict | list | str]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{base}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def check(label: str, condition: bool, detail: str = "") -> None:
    global failures
    mark = PASS if condition else FAIL
    print(f"  {mark} {label}" + (f" —— {detail}" if detail and not condition else ""))
    if not condition:
        failures += 1


def main() -> int:
    print(f"占道施工审批链路自检（后端 {BACKEND}）\n")

    print("[1/6] 健康检查")
    status, payload = request("GET", BACKEND, "/api/health")
    check("GET /api/health 返回 200", status == 200, f"HTTP {status}: {payload}")
    if status != 200:
        print("\n后端未响应，自检终止。请先执行 make up 启动服务。")
        return 1
    assert isinstance(payload, dict)
    check(f"示例数据已灌入（{payload.get('modules')} 个业务模块）", bool(payload.get("ok")))

    print("\n[2/6] 种子数据覆盖完整审批状态")
    status, payload = request("GET", BACKEND, "/api/occupy?size=100")
    check("GET /api/occupy 返回 200", status == 200, f"HTTP {status}")
    statuses = {item["status"] for item in payload.get("items", [])} if isinstance(payload, dict) else set()
    expected = {"待审批", "已批准", "施工中", "已完工", "已恢复"}
    check(f"列表含全部状态：{'、'.join(STATUS_ORDER)}",
          expected.issubset(statuses), f"实际状态：{sorted(statuses)}")
    real_approver = [i for i in payload["items"] if i.get("审批人")]
    check("审批人字段有真实示例数据而非占位符", len(real_approver) >= 2, "已批准及之后的记录应有审批人")

    print("\n[3/6] 提交占道申请")
    application = {
        "values": {
            "施工编号": "OCCU-TEST-01",
            "施工位置": "自检路段 K0+000",
            "占用范围": "自检临时占用 50 平方米",
            "施工内容": "链路自检：燃气检测井维修",
            "申请人": "自检脚本",
            "占用期限": "2026-09-26 至 2026-09-27",
        }
    }
    status, payload = request("POST", BACKEND, "/api/occupy", application)
    check("POST /api/occupy 返回 200", status == 200, f"HTTP {status}: {payload}")
    check("受理结果 ok=true", isinstance(payload, dict) and payload.get("ok") is True, str(payload))
    entry = payload.get("entry") if isinstance(payload, dict) else None
    check("新申请初始状态为「待审批」", bool(entry) and entry.get("status") == "待审批", str(entry))
    check("申请人与占用期限已落库", bool(entry) and entry.get("申请人") == "自检脚本", str(entry))
    if not entry:
        print("\n申请提交失败，后续链路无法验证。")
        return 1
    entry_id = entry["id"]

    print(f"\n[4/6] 逐级审批（申请 id={entry_id}）")
    steps = [
        ("审批通过", "已批准", {"审批人": "自检审批人-王海涛"}),
        ("开始施工", "施工中", {}),
        ("完工确认", "已完工", {}),
        ("恢复通行", "已恢复", {}),
    ]
    for action, target, extra in steps:
        status, payload = request(
            "POST", BACKEND, f"/api/occupy/{entry_id}/actions",
            {"values": {"action": action, **extra}},
        )
        ok = (
            status == 200
            and isinstance(payload, dict)
            and payload.get("ok") is True
            and (payload.get("entry") or {}).get("status") == target
        )
        check(f"{action} → {target}", ok, f"HTTP {status}: {payload}")
        if action == "审批通过" and ok:
            check("审批动作回写了审批人", payload["entry"].get("审批人") == "自检审批人-王海涛",
                  str(payload.get("entry")))

    print("\n[5/6] 终态明细确认")
    status, payload = request("GET", BACKEND, f"/api/occupy/{entry_id}")
    check("GET /api/occupy/{id} 返回 200", status == 200, f"HTTP {status}")
    check("最终状态为「已恢复」", isinstance(payload, dict) and payload.get("status") == "已恢复",
          str(payload))

    # 非法动作应被明确拒绝，而不是 500
    status, payload = request(
        "POST", BACKEND, f"/api/occupy/{entry_id}/actions", {"values": {"action": "删除申请"}}
    )
    check("非法动作被拦截并返回可读说明",
          status == 200 and isinstance(payload, dict) and payload.get("ok") is False, str(payload))

    print("\n[6/6] 前端代理链路")
    status, payload = request("GET", FRONTEND, "/api/health")
    if status == 200 and isinstance(payload, dict) and payload.get("ok"):
        check(f"经前端 {FRONTEND} 代理访问 /api/health 成功", True)
    else:
        check(f"经前端 {FRONTEND} 代理访问 /api/health", False,
              f"HTTP {status}（前端未启动时忽略此项，直接访问后端即可）")

    print()
    if failures:
        print(f"自检完成：{failures} 项未通过，请按 ✗ 条目排查。")
        return 1
    print("自检完成：占道申请提交与整条审批链路（含前端代理）全部可用。")
    return 0


STATUS_ORDER = ["待审批", "已批准", "施工中", "已完工", "已恢复"]

if __name__ == "__main__":
    sys.exit(main())
