#!/usr/bin/env bash
# 装齐前后端依赖：后端按 requirements.lock 完整锁定安装，前端按 package-lock.json 安装。
# 已安装的部分由调用方（preflight）判断是否跳过；本脚本幂等，可重复执行。
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT_DIR/backend/.venv"

if [ ! -x "$VENV/bin/python" ]; then
  echo "[install] 创建后端虚拟环境 backend/.venv"
  if ! python3 -m venv "$VENV" 2>/dev/null; then
    cat >&2 <<'EOF'
✗ python3 -m venv 失败（Debian/Ubuntu 常见：未安装 python3-venv）。
  解决办法二选一：
    1. sudo apt-get install python3-venv（或 python3.11-venv）
    2. pip install --user virtualenv && python3 -m virtualenv backend/.venv
EOF
    exit 1
  fi
fi

echo "[install] 安装后端依赖（requirements.lock，版本完整锁定）"
"$VENV/bin/pip" install -q -r "$ROOT_DIR/backend/requirements.lock"

echo "[install] 安装前端依赖（npm ci，按 package-lock.json 锁定安装）"
(cd "$ROOT_DIR/frontend" && npm ci)

echo "[install] 依赖安装完成"
