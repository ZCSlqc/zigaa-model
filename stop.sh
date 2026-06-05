#!/usr/bin/env bash
set -euo pipefail

PROJECT="zigaa-model"
BACKEND_PID="/tmp/${PROJECT}_backend.pid"
FRONTEND_PID="/tmp/${PROJECT}_frontend.pid"

echo "🛑 停止中..."

pids=()
for f in "$BACKEND_PID" "$FRONTEND_PID"; do
  if [ -f "$f" ]; then
    pids+=("$(cat "$f"):$f")
  fi
done

# 温柔停止
for entry in "${pids[@]}"; do
  pid="${entry%%:*}"
  kill "$pid" 2>/dev/null || true
done
sleep 1

# 还在跑就强杀，然后清理
for entry in "${pids[@]}"; do
  pid="${entry%%:*}"
  pfile="${entry##*:}"
  kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
  rm -f "$pfile"
done

echo "✅ 已停止"
