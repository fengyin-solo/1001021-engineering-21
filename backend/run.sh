#!/usr/bin/env bash
# 只启动后端。启动前先预检：依赖缺失或环境变量没配时会给出明确指引，
# 而不是让 uvicorn 崩在半路再回头猜原因。
set -euo pipefail
cd "$(dirname "$0")"
ROOT_DIR="$(cd .. && pwd)"

# 根目录 .env 存在时载入，保证与 scripts/dev-up.sh 的口径一致
if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT_DIR/.env"
  set +a
fi

"$ROOT_DIR/scripts/preflight.sh" backend || exit 1

exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "${APP_PORT:-8000}"
