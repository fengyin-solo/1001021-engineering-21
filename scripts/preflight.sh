#!/usr/bin/env bash
# 启动前预检：把「跑不起来」的原因在真正启动前讲清楚。
# 检查三类问题：命令缺失（python3/node/npm）、后端依赖缺失、环境变量配置错误。
# 用法：scripts/preflight.sh [backend|frontend|all]
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCOPE="${1:-all}"
FAILED=0

fail() {
  echo "✗ $1" >&2
  FAILED=1
}

ok() {
  echo "✓ $1"
}

check_command() {
  if command -v "$1" >/dev/null 2>&1; then
    ok "命令 $1 可用（$($1 --version 2>&1 | head -1)）"
  else
    fail "命令 $1 未安装：请先安装 $2"
  fi
}

# 载入根目录 .env（存在时），让环境变量校验与正式启动口径一致
if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT_DIR/.env"
  set +a
fi

if [ "$SCOPE" = "backend" ] || [ "$SCOPE" = "all" ]; then
  check_command python3 "Python 3.10+（建议 3.11/3.12）"

  VENV_PY="$ROOT_DIR/backend/.venv/bin/python"
  if [ ! -x "$VENV_PY" ]; then
    fail "后端虚拟环境不存在：backend/.venv 缺失，先执行 make install（或 scripts/dev-up.sh 会自动创建）"
  else
    if ! "$VENV_PY" -c "import fastapi, uvicorn, pydantic" >/dev/null 2>&1; then
      fail "后端依赖缺失：fastapi/uvicorn/pydantic 未安装，执行 (cd backend && .venv/bin/pip install -r requirements.lock)"
    else
      ok "后端依赖已安装（fastapi、uvicorn、pydantic 均可导入）"
    fi
    # 配置与环境变量校验：单独跑一遍 config 加载，区分「依赖缺失」与「环境变量没配」
    CONFIG_ERROR="$("$VENV_PY" -c "
import sys
sys.path.insert(0, '$ROOT_DIR/backend')
try:
    from app.config import settings
except Exception as exc:
    print(type(exc).__name__ + ': ' + str(exc))
    sys.exit(1)
" 2>&1)" || {
      fail "环境变量配置错误：${CONFIG_ERROR}"
    }
    [ -z "${CONFIG_ERROR:-}" ] && ok "环境变量校验通过（APP_ENV=${APP_ENV:-local}）"
  fi
fi

if [ "$SCOPE" = "frontend" ] || [ "$SCOPE" = "all" ]; then
  check_command node "Node.js 18+（建议 20 LTS）"
  check_command npm "随 Node.js 一起安装的 npm"

  if [ ! -d "$ROOT_DIR/frontend/node_modules/vite" ]; then
    fail "前端依赖缺失：frontend/node_modules 未安装，执行 (cd frontend && npm ci)"
  else
    ok "前端依赖已安装（node_modules 就绪）"
  fi
fi

if [ "$FAILED" -ne 0 ]; then
  echo "" >&2
  echo "预检未通过：请按上面 ✗ 条目处理后重试；安装依赖可直接执行 make install。" >&2
fi
exit "$FAILED"
