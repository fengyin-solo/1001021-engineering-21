#!/usr/bin/env bash
# 后端一键启动：先做环境诊断，再拉起 uvicorn。
# 诊断退出码：2=依赖缺失，3=环境变量错误，4=代码/示例数据问题；非 0 时不启动，直接给出修复指引。
set -euo pipefail
cd "$(dirname "$0")"

PYTHON=.venv/bin/python

# 1) 虚拟环境：不存在或解释器失效（常见于从别的机器/系统拷贝 .venv）就自动重建。
if [ ! -x "$PYTHON" ] || ! "$PYTHON" -c 'import sys' >/dev/null 2>&1; then
  echo "[run.sh] 未找到可用的 .venv，开始创建虚拟环境……"
  if command -v python3 >/dev/null 2>&1 && python3 -m venv --help >/dev/null 2>&1; then
    python3 -m venv .venv
  elif command -v virtualenv >/dev/null 2>&1; then
    virtualenv .venv
  else
    cat >&2 <<'EOF'
[run.sh] 无法创建虚拟环境（依赖缺失，非环境变量问题）：
  当前系统 Python 既没有 venv 模块也没有 virtualenv。
  - Debian/Ubuntu：sudo apt-get install python3-venv
  - 或先安装：python3 -m pip install --user virtualenv
  然后重新执行本脚本。
EOF
    exit 2
  fi
fi

# 2) 依赖：关键包缺失时按锁定文件安装；安装失败明确归为依赖问题。
if ! "$PYTHON" -c 'import fastapi, uvicorn, pydantic, dotenv' >/dev/null 2>&1; then
  echo "[run.sh] 检测到依赖未安装，按 requirements.txt 安装……"
  if ! "$PYTHON" -m pip install --disable-pip-version-check -r requirements.txt; then
    cat >&2 <<'EOF'
[run.sh] 依赖安装失败（网络或 pip 源问题，非环境变量问题）。
可指定内网镜像后重试，例如：
  .venv/bin/pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
EOF
    exit 2
  fi
fi

# 3) 启动前诊断：Python 版本 / 依赖 / 环境变量 / 示例数据。
if ! "$PYTHON" scripts/preflight.py; then
  code=$?
  case "$code" in
    2) echo "[run.sh] 依赖环境未就绪，已停止启动（见上面的修复指引）。" >&2 ;;
    3) echo "[run.sh] 环境变量配置有误，已停止启动（检查根目录 .env 或参考 .env.example）。" >&2 ;;
    *) echo "[run.sh] 前置诊断未通过（退出码 $code），已停止启动。" >&2 ;;
  esac
  exit "$code"
fi

# 4) 读取监听地址（环境变量优先，默认本地回环）。
HOST="${APP_HOST:-127.0.0.1}"
PORT="${APP_PORT:-8000}"

echo "[run.sh] 启动后端：http://${HOST}:${PORT}（API 文档 /docs，健康检查 /api/health）"
exec "$PYTHON" -m uvicorn app.main:app --host "$HOST" --port "$PORT"
