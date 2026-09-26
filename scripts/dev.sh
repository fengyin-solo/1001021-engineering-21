#!/usr/bin/env bash
# 一键本地开发：检查工具链 -> 安装/校验锁定依赖 -> 构建前端 -> 同时启动前后端 -> 打印自检入口。
# 用法：./scripts/dev.sh
# 前置：Node.js >= 20、Python >= 3.10（后端 venv 会自动创建，需要 python3-venv 或 virtualenv）。
set -euo pipefail
cd "$(dirname "$0")/.."

BACKEND_URL="http://127.0.0.1:${APP_PORT:-8000}"
FRONTEND_URL="http://127.0.0.1:5173"

pids=()
cleanup() {
  if [ ${#pids[@]} -gt 0 ]; then
    kill "${pids[@]}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

echo "== 1/5 检查工具链 =="
if ! command -v node >/dev/null 2>&1; then
  echo "[dev] 未找到 node（依赖缺失）。请安装 Node.js >= 20：https://nodejs.org/" >&2
  exit 2
fi
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
if [ "$NODE_MAJOR" -lt 20 ]; then
  echo "[dev] Node 版本过低：当前 $(node -v)，要求 >= 20。" >&2
  exit 2
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "[dev] 未找到 python3（依赖缺失）。请安装 Python >= 3.10。" >&2
  exit 2
fi
PY_MAJOR="$(python3 -c 'import sys;print(sys.version_info[0])')"
PY_MINOR="$(python3 -c 'import sys;print(sys.version_info[1])')"
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
  echo "[dev] Python 版本过低：$(python3 --version)，要求 >= 3.10。" >&2
  exit 2
fi
echo "    node $(node -v)，npm $(npm -v)，$(python3 --version)"

echo "== 2/5 后端依赖（锁定版本，首次运行会创建 .venv）=="
if [ ! -x backend/.venv/bin/python ]; then
  if python3 -m venv --help >/dev/null 2>&1; then
    python3 -m venv backend/.venv
  elif command -v virtualenv >/dev/null 2>&1; then
    virtualenv backend/.venv
  else
    echo "[dev] Python 缺少 venv 模块（依赖缺失，非环境变量问题）。" >&2
    echo "      Debian/Ubuntu 执行：sudo apt-get install python3-venv；或：python3 -m pip install --user virtualenv" >&2
    exit 2
  fi
fi
# 优先按完整锁文件安装，保证传递依赖也一致。
backend/.venv/bin/python -m pip install --disable-pip-version-check -q \
  -r backend/requirements.txt
backend/.venv/bin/python backend/scripts/preflight.py

echo "== 3/5 前端依赖（按 package-lock.json 安装，可复现）=="
if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm ci)
else
  echo "    node_modules 已存在，跳过安装；如需强制重建：rm -rf frontend/node_modules && npm ci"
fi

echo "== 4/5 构建校验前端（vue-tsc 类型检查 + vite build）=="
(cd frontend && npm run build)

echo "== 5/5 启动后端与前端 =="
(
  cd backend
  HOST_FROM_ENV="${APP_HOST:-127.0.0.1}"
  exec ./.venv/bin/python -m uvicorn app.main:app \
    --host "$HOST_FROM_ENV" --port "${APP_PORT:-8000}"
) &
pids+=($!)

(cd frontend && exec npm run dev -- --strictPort) &
pids+=($!)

sleep 1
cat <<EOF

──────────────────────────────────────────────────────────────
  平台已启动：
    前端页面  $FRONTEND_URL
    后端接口  $BACKEND_URL/api/health
    API 文档  $BACKEND_URL/docs
  启动时已自动灌入占道施工完整链路示例：
    待审批 → 已批准 → 施工中 → 已完工 → 已恢复
  自检入口（另开一个终端执行，验证申请提交与审批接口）：
    make check
  或：
    backend/.venv/bin/python backend/scripts/check_occupy.py
  按 Ctrl+C 停止前后端。
──────────────────────────────────────────────────────────────

EOF

wait
