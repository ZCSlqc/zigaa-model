#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PROJECT="zigaa-model"
BACKEND_PID="/tmp/${PROJECT}_backend.pid"
FRONTEND_PID="/tmp/${PROJECT}_frontend.pid"
BACKEND_LOG="$(pwd)/log/backend.log"
FRONTEND_LOG="$(pwd)/log/frontend.log"

# 有 PID 就杀
for f in "$BACKEND_PID" "$FRONTEND_PID"; do
  if [ -f "$f" ]; then
    kill "$(cat "$f")" 2>/dev/null || true
    rm -f "$f"
  fi
done

# 强制清理残留进程（防止僵尸进程堆积）
BACKEND_PORT="${BACKEND_PORT:-8111}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
pkill -f "uvicorn main:app.*${BACKEND_PORT}" 2>/dev/null || true
pkill -f "vite.*--port 3" 2>/dev/null || true

sleep 1

mkdir -p log

echo "🚀 启动中..."

# 后端
PROJECT_ROOT="$(pwd)"
cd backend
$PROJECT_ROOT/.venv/bin/python -m uvicorn main:app --host "${BACKEND_HOST:-0.0.0.0}" --port "${BACKEND_PORT:-8111}" --reload > "$BACKEND_LOG" 2>&1 &
echo $! > "$BACKEND_PID"
cd ..

for i in $(seq 1 15); do sleep 1; curl -s "http://localhost:${BACKEND_PORT}/docs" >/dev/null 2>&1 && break; done
if ! curl -s "http://localhost:${BACKEND_PORT}/docs" >/dev/null 2>&1; then
  echo "❌ 后端启动失败"; cat "$BACKEND_LOG"; exit 1
fi
echo "✅ 后端 $(cat "$BACKEND_PID")"

echo "→ http://localhost:8111"

# 前端
cd frontend
npm run dev -- --host 0.0.0.0 --port 3111 > "$FRONTEND_LOG" 2>&1 &
echo $! > "$FRONTEND_PID"
cd ..

for i in $(seq 1 15); do sleep 1; curl -s http://localhost:3111 >/dev/null 2>&1 && break; done
if ! curl -s http://localhost:3111 >/dev/null 2>&1; then
  echo "❌ 前端启动失败"; cat "$FRONTEND_LOG"; exit 1
fi
echo "✅ 前端 $(cat "$FRONTEND_PID")"

echo "→ http://localhost:3111"
