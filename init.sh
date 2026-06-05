#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "=== Zigaa 初始化 ==="

# 依赖检查
missing=()
for cmd in python3 node npm uv mysql; do
  command -v "$cmd" &>/dev/null || missing+=("$cmd")
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "❌ 缺少: ${missing[*]}"
  exit 1
fi

# .env 检查
if [ ! -f ".env" ]; then
  echo "❌ 缺少 .env 文件，请先创建并填写数据库连接和 JWT_SECRET"
  exit 1
fi

# 解析数据库连接信息
source <(grep -E '^(DB_HOST|DB_PORT|DB_USER|DB_PASSWORD|DB_NAME)=' .env)
if [ -z "${DB_HOST:-}" ] || [ -z "${DB_NAME:-}" ]; then
  echo "❌ .env 缺少 DB_HOST/DB_NAME 配置"
  exit 1
fi

# 检查数据库是否可达
if ! mysql -h"$DB_HOST" -P"${DB_PORT:-3306}" -u"${DB_USER:-root}" -p"${DB_PASSWORD:-}" -e "USE ${DB_NAME}" &>/dev/null; then
  echo "❌ 数据库 ${DB_NAME} 不可达，请先创建数据库和用户"
  echo "   CREATE DATABASE ${DB_NAME} DEFAULT CHARACTER SET utf8mb4;"
  echo "   CREATE USER '${DB_USER:-zigaa}'@'%' IDENTIFIED BY '${DB_PASSWORD:-zigaa123}';"
  echo "   GRANT ALL ON ${DB_NAME}.* TO '${DB_USER:-zigaa}'@'%'; FLUSH PRIVILEGES;"
  exit 1
fi
echo "✅ MySQL 连接正常"

# 创建必要目录
mkdir -p uploads log

if [ ! -d "${UPLOAD_TMP_DIR:-/data/tmp}" ]; then
  mkdir -p "${UPLOAD_TMP_DIR:-/data/tmp}"
  echo "✅ 创建临时目录 ${UPLOAD_TMP_DIR:-/data/tmp}"
fi

# Python venv
if [ ! -d ".venv" ]; then
  echo "⚙️  创建虚拟环境..."
  uv venv
fi
echo "⚙️  安装 Python 依赖..."
uv pip install -e .

# 前端
echo "⚙️  安装前端依赖..."
cd frontend && npm install && cd ..

echo ""
echo "✅ 初始化完成"
echo "   启动: ./start.sh"
echo "   停止: ./stop.sh"
echo "   后端: http://localhost:8111/docs"
echo "   前端: http://localhost:3111"
