#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# 优先使用可用的虚拟环境；环境缺失或损坏时回退到系统 Python。
PYTHON=""
if [ -x .venv/bin/python ] && .venv/bin/python -c "import fastapi" >/dev/null 2>&1; then
  PYTHON=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1 && python3 -c "import fastapi" >/dev/null 2>&1; then
  PYTHON="python3"
else
  echo "未找到可用的 Python 环境（缺少 fastapi），请先安装依赖" >&2
  exit 1
fi

exec "$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
