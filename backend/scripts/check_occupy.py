#!/usr/bin/env python3
"""占道施工链路自检：确认「申请提交」与「审批流转」两类接口真的可用。

脚本对一个已经在跑的后端发真实 HTTP 请求（只用标准库，无需额外依赖）：
  1. GET  /api/health                 服务存活、示例数据已灌入
  2. GET  /api/occupy?status=...      待审批→…→已恢复 各阶段样例都在
  3. POST /api/occupy                 提交一条新的占道申请
  4. POST /api/occupy/{id}/actions    审批被缺字段拦下 -> 补全后审批通过 -> 逐级流转到已恢复
  5. （可选）经前端 vite 代理再走一遍列表，确认浏览器侧链路也通

退出码：0 全部通过；1 有检查项失败；2 连不上服务。

用法：
  backend/.venv/bin/python scripts/check_occupy.py
  backend/.venv/bin/python scripts/check_occupy.py --base http://127.0.0.1:8000 --proxy http://127.0.0.1:5173
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

EXPECTED_CHAIN = ["待审批", "已批准", "施工中", "已完工", "已恢复"]


class CheckFailure(Exception):
    pass


def request(base: str, path: str, payload: dict[str, Any] | None = None, timeout: float = 5.0) -> tuple[int, Any]:
    url = base.rstrip("/") + path
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, body


def wait_for_service(base: str, attempts: int = 20) -> None:
    for _ in range(attempts):
        try:
            status, _ = request(base, "/api/health", timeout=2.0)
            if status == 200:
                return
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    raise CheckFailure(f"连不上后端 {base}，服务是否已启动？（先执行 make dev 或 make backend）")


def main() -> int:
    parser = argparse.ArgumentParser(description="占道施工审批链路自检")
    parser.add_argument("--base", default="http://127.0.0.1:8000", help="后端直连地址")
    parser.add_argument("--proxy", default="http://127.0.0.1:5173", help="前端 vite 代理地址，传空字符串可跳过")
    args = parser.parse_args()

    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    try:
        wait_for_service(args.base)

        # 1) 健康检查
        status, body = request(args.base, "/api/health")
        check("健康检查 GET /api/health", status == 200 and body.get("ok") is True,
              f"modules={body.get('modules')} occupy={body.get('occupy')}" if isinstance(body, dict) else str(body))

        # 2) 完整审批链各阶段样例
        seen: dict[str, int] = {}
        for stage in EXPECTED_CHAIN:
            status, body = request(args.base, f"/api/occupy?status={urllib.parse.quote(stage)}&size=200")
            count = body.get("total", 0) if isinstance(body, dict) else 0
            seen[stage] = count
            check(f"示例数据含「{stage}」", status == 200 and count > 0, f"{count} 条")

        # 3) 提交一条新的占道申请
        apply_no = "OCCU-CHECK-001"
        status, body = request(args.base, "/api/occupy", {"values": {
            "施工编号": apply_no,
            "施工位置": "自检：示范路 K0+000 至 K0+100",
            "占用范围": "自检用临时占用，长100米宽3米",
            "施工内容": "链路自检：管道碰头",
            "申请人": "自检脚本·测试申请人",
        }})
        created = isinstance(body, dict) and body.get("ok") and isinstance(body.get("entry"), dict)
        entry = body.get("entry", {}) if isinstance(body, dict) else {}
        check("提交占道申请 POST /api/occupy", status == 200 and created,
              body.get("message", "") if isinstance(body, dict) else str(body))
        if not created:
            raise CheckFailure("申请未创建，后续审批动作无法继续")
        entry_id = entry["id"]
        check("新申请初始为「待审批」", entry.get("status") == "待审批", f"id={entry_id}")

        # 缺必填字段应被拦下（重复编号同样要给可读错误）
        status, body = request(args.base, "/api/occupy", {"values": {"施工编号": apply_no}})
        check("重复编号 / 缺字段被拦下并返回原因",
              isinstance(body, dict) and body.get("ok") is False and "缺少必填字段" in body.get("message", ""),
              body.get("message", "") if isinstance(body, dict) else str(body))

        # 4) 审批流转：先缺审批人 -> 被拦；补全 -> 审批通过；再逐级走到底
        status, body = request(args.base, f"/api/occupy/{entry_id}/actions",
                               {"values": {"action": "审批通过"}})
        check("审批缺审批人/占用期限被拦下",
              isinstance(body, dict) and body.get("ok") is False and "审批人" in body.get("message", ""),
              body.get("message", "") if isinstance(body, dict) else str(body))

        steps = [
            ("审批通过", {"审批人": "自检脚本·审批人", "占用期限": "2026-10-01 至 2026-10-10"}),
            ("开始施工", {}),
            ("施工完成", {}),
            ("恢复通行", {}),
        ]
        current = entry
        for action, extra in steps:
            status, body = request(args.base, f"/api/occupy/{entry_id}/actions",
                                   {"values": {"action": action, **extra}})
            ok = isinstance(body, dict) and body.get("ok") is True
            current = body.get("entry", current) if isinstance(body, dict) else current
            check(f"动作「{action}」", ok and isinstance(current, dict) and current.get("status"),
                  f"-> {current.get('status')}" if isinstance(current, dict) else str(body))

        check("链路终点为「已恢复」且不再待处理",
              isinstance(current, dict) and current.get("status") == "已恢复" and current.get("pending") is False,
              f"pending={current.get('pending') if isinstance(current, dict) else '?'}")

        # 回退/跨级必须被拒
        status, body = request(args.base, f"/api/occupy/{entry_id}/actions",
                               {"values": {"action": "开始施工"}})
        check("终态上重复/回退动作被拦下",
              isinstance(body, dict) and body.get("ok") is False,
              body.get("message", "") if isinstance(body, dict) else str(body))

        # 5) 经前端 vite 代理访问（浏览器实际走的路径）
        if args.proxy:
            try:
                status, body = request(args.proxy, "/api/occupy?size=1")
                check("经前端代理访问列表 GET :5173/api/occupy",
                      status == 200 and isinstance(body, dict) and "items" in body,
                      "前后端代理链路正常")
            except Exception as exc:  # noqa: BLE001
                check("经前端代理访问列表 GET :5173/api/occupy", False,
                      f"连不上前端代理（若只起了后端可忽略）：{exc}")

    except CheckFailure as exc:
        print(f"\n[自检] 无法执行：{exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"\n[自检] 发生异常：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)
    print(f"\n[自检] 占道施工提交+审批链路：{passed}/{total} 项通过")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
