#!/usr/bin/env bash
# 一条命令把工程链路跑通：
#   预检 → 装依赖（缺失才装）→ 前端构建验证 → 起后端 → 起前端（preview 构建产物）
#   → 健康检查轮询 → 自动跑占道施工审批链路自检
# 用法：scripts/dev-up.sh
# 停止：Ctrl-C（脚本会同时收掉前后端两个子进程）
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT_DIR/backend/.venv"
BACKEND_HOST="127.0.0.1"
BACKEND_PORT="${APP_PORT:-8000}"
FRONTEND_PORT="${VITE_PORT:-5173}"
BACKEND_PID=""
FRONTEND_PID=""

log() { printf '\n\033[1;36m[dev-up]\033[0m %s\n' "$1"; }

cleanup() {
  log "收到退出信号，停止前后端服务……"
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
  wait 2>/dev/null
}
trap cleanup EXIT INT TERM

# 存在根 .env 时先载入，保证预检与启动看到的是同一套环境变量
if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT_DIR/.env"
  set +a
fi

log "第 1 步：启动预检（命令、依赖、环境变量）"
if ! "$ROOT_DIR/scripts/preflight.sh" all; then
  log "第 2 步：依赖缺失，开始安装（已安装的部分会跳过）"
  "$ROOT_DIR/scripts/install.sh" || exit 1

  log "复查预检"
  "$ROOT_DIR/scripts/preflight.sh" all || exit 1
fi

# 环境变量/配置是否能正常加载（区分：依赖装好了但变量没配）
if ! "$VENV/bin/python" -c "import sys; sys.path.insert(0, '$ROOT_DIR/backend'); import app.config" 2>"$ROOT_DIR/.config-error"; then
  echo "✗ 配置加载失败，属于环境变量问题而非依赖缺失：" >&2
  cat "$ROOT_DIR/.config-error" >&2
  rm -f "$ROOT_DIR/.config-error"
  exit 1
fi
rm -f "$ROOT_DIR/.config-error"

log "第 3 步：前端构建验证（npm run build：类型检查 + 打包）"
(cd "$ROOT_DIR/frontend" && npm run build) || {
  echo "✗ 前端构建失败，请先修复上面的类型或打包错误" >&2
  exit 1
}

log "第 4 步：启动后端 http://$BACKEND_HOST:$BACKEND_PORT（启动时自动灌入示例数据）"
(
  cd "$ROOT_DIR/backend"
  # shellcheck disable=SC2086
  exec "$VENV/bin/uvicorn" app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT"
) &
BACKEND_PID=$!

log "第 5 步：启动前端 http://$BACKEND_HOST:$FRONTEND_PORT（preview 刚构建出的产物，/api 代理到后端）"
(
  cd "$ROOT_DIR/frontend"
  exec npm run preview -- --host "$BACKEND_HOST" --port "$FRONTEND_PORT" \
    --strictPort
) &
FRONTEND_PID=$!

log "第 6 步：等待后端就绪（最长 30 秒）"
READY=0
for _ in $(seq 1 30); do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "✗ 后端进程提前退出，请查看上方 uvicorn 日志（依赖缺失会在这里表现为 ImportError）" >&2
    exit 1
  fi
  if "$VENV/bin/python" -c "
import urllib.request
urllib.request.urlopen('http://$BACKEND_HOST:$BACKEND_PORT/api/health', timeout=2)
" 2>/dev/null; then
    READY=1
    break
  fi
  sleep 1
done
if [ "$READY" -ne 1 ]; then
  echo "✗ 后端 30 秒内未响应 http://$BACKEND_HOST:$BACKEND_PORT/api/health" >&2
  exit 1
fi

log "第 7 步：占道施工审批链路自检（提交申请 → 审批通过 → 施工 → 完工 → 恢复通行）"
FRONTEND_BASE="http://$BACKEND_HOST:$FRONTEND_PORT" \
  "$VENV/bin/python" "$ROOT_DIR/scripts/smoke_check.py" "http://$BACKEND_HOST:$BACKEND_PORT"
SMOKE_RESULT=$?

cat <<EOF

────────────────────────────────────────────────────────────
服务已启动并完成自检（退出码 $SMOKE_RESULT）：
  前端页面：http://$BACKEND_HOST:$FRONTEND_PORT
  后端接口：http://$BACKEND_HOST:$BACKEND_PORT/api/health
  接口文档：http://$BACKEND_HOST:$BACKEND_PORT/docs
  重复自检：make check
按 Ctrl-C 停止全部服务。
────────────────────────────────────────────────────────────
EOF

# 自检失败不直接退出：服务还活着，保留现场供排查；前台等子进程
wait "$BACKEND_PID"
