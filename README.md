# Zigaa 大模型云平台

> 工业缺陷检测数据管理 Web 应用，提供数据标注管理 + 本地模型训练全流程。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Vue](https://img.shields.io/badge/Vue.js-3.5+-42b883.svg)](https://vuejs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-6.0+-3178c6.svg)](https://www.typescriptlang.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 系统要求

| 资源 | 最低 | 推荐 |
|------|------|------|
| CPU | 2 核 | 4 核+ |
| 内存 | 4 GB | 8 GB+ |
| 磁盘 | 20 GB | 50 GB+（图片压缩 / ZIP 解压需要大量临时空间） |

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + TypeScript + Element Plus + Konva + Pinia |
| 后端 | FastAPI + SQLAlchemy + MySQL + PyJWT + bcrypt + OpenCV |
| 数据库 | MySQL 8.0 (utf8mb4) |
| 包管理 | uv（后端）+ npm（前端） |

## ✨ 功能特性

- **项目 / 模型管理** — 多级 CRUD，三维状态系统（文件 / 训练 / 测试）
- **ZIP 分片上传** — 断点续传 + 多文件队列 + 异步处理 + 进度倒计时
- **ZIP 分片下载** — 3 线程并行 + IndexedDB 持久化 + 断点续传
- **标注编辑器** — Konva 画布，多边形绘制 / 编辑 / 撤销，9 级 JSON 校验
- **图片预览** — 三级存储（original / compress / preview），多边形标注叠加渲染
- **本地训练 / 测试** — status.json 驱动 + 前端轮询同步 + 日志查看
- **管理后台** — 用户 CRUD + 权限管理 + 项目全局管理
- **三级角色权限** — `user` / `advanced` / `admin`，JWT 24h

## 📋 目录结构

```
zigaa-model/
├── backend/              # FastAPI 后端
│   ├── core/             # 配置 / 认证 / 数据库 / ORM
│   ├── api/              # 6 个路由器 (auth/projects/models/resources/annotations/admin)
│   ├── services/         # 业务逻辑 (上传/下载/队列/图片处理/状态管理)
│   └── main.py           # 启动入口
├── frontend/             # Vue 3 前端
│   └── src/
│       ├── views/        # 9 个页面
│       ├── components/   # 布局 / 上传 / 下载 / 标注 / 编辑器
│       ├── stores/       # Pinia (auth/project/annotation)
│       ├── api/          # Axios 客户端 + 分级超时
│       ├── composables/  # Loading / 防抖 / 下载管理器
│       └── utils/        # IndexedDB / 状态解析 / 格式化
├── uploads/              # 模型资源文件（图片、标注等）
├── log/                  # 运行日志（backend.log / frontend.log）
├── init.sh               # 首次初始化（依赖检查 / 数据库验证 / 环境搭建）
├── start.sh              # 日常启动（后端 8111 + 前端 3111）
├── stop.sh               # 停止服务
├── .env                  # 环境变量
├── pyproject.toml        # Python 依赖声明
└── DEPLOY.md             # 详细部署手册
```

## 🚀 快速开始

### 前置依赖

- **Python** >= 3.10
- **Node.js** >= 18 (含 npm)
- **MySQL** >= 8.0
- **uv** — `curl -LsSf https://astral.sh/uv/install.sh | sh`

### 1. 克隆项目

```bash
git clone <repo-url>
cd zigaa-model
```

### 2. 创建数据库

```bash
mysql -u root -p
```

在 MySQL 中执行：

```sql
CREATE DATABASE IF NOT EXISTS zigaa_platform DEFAULT CHARACTER SET utf8mb4;
CREATE USER IF NOT EXISTS 'zigaa'@'%' IDENTIFIED BY 'zigaa123';
GRANT ALL ON zigaa_platform.* TO 'zigaa'@'%';
FLUSH PRIVILEGES;
EXIT;
```

> **root 免密登录**（忘记密码时）：
> ```bash
> sudo mysqld_safe --skip-grant-tables --skip-networking &
> mysql -u root
> ```
> 然后在 MySQL 中执行：
> ```sql
> FLUSH PRIVILEGES;
> ALTER USER 'root'@'localhost' IDENTIFIED BY '新密码';
> EXIT;
> ```
> 最后重启 MySQL：`sudo systemctl restart mysql`

### 3. 配置环境变量

编辑 `.env` 文件（首次需手动创建）。**后端**自动读取此文件，**前端**通过 Vite 的 `import.meta.env` 读取以 `VITE_` 开头的变量。

```ini
# ===== 后端：认证 =====
JWT_SECRET=<uuidgen 生成随机字符串>

# ===== 后端：数据库 =====
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=zigaa
DB_PASSWORD=zigaa123
DB_NAME=zigaa_platform

# ===== 后端：文件存储 =====
UPLOAD_DIR=../uploads
UPLOAD_TMP_DIR=/data/tmp
TRAINING_DIR=/data/zigaa
CLEANUP_STALE_HOURS=48

# ===== 后端：CORS 跨域 =====
CORS_HOST=192.168.10.160
CORS_PORT=3111

# ===== 前端：标注编辑器尺寸（画布像素） =====
VITE_ANNOTATION_EDGE_WIDTH=0.6
VITE_ANNOTATION_VERTEX_RADIUS=1
VITE_ANNOTATION_VERTEX_HOVER_RADIUS=2.5
VITE_ANNOTATION_EDGE_HOVER_WIDTH=2.5
VITE_ANNOTATION_DELETE_BTN_RADIUS=5

# ===== 前端：标注交互灵敏度 =====
VITE_HIT_RADIUS=4                  # 顶点检测半径（屏幕像素）
VITE_EDGE_HIT_RADIUS=3             # 边插入检测半径（屏幕像素）
VITE_DRAW_MIN_IMAGE_DIST=1.5       # 拖拽绘制最小图片像素间距（取 max(图片间距, 屏幕间距/scale)，防止缩小后点过度密集）
VITE_DRAW_MIN_SCREEN_DIST=8        # 拖拽绘制最小屏幕像素间距（取 max(图片间距, 屏幕间距/scale)，防止缩小后点过度密集）

# ===== 前端：训练/测试状态轮询间隔（毫秒） =====
VITE_POLL_INTERVAL=10000
```

> **生产环境注意**：修改 `JWT_SECRET`、`DB_PASSWORD` 和 `CORS_HOST`，首次登录后请修改默认账号密码。

### 4. 创建系统目录

```bash
sudo mkdir -p /data/tmp /data/zigaa
sudo chown -R $USER:$USER /data/tmp /data/zigaa
```

| 目录 | 用途 | 空间需求 |
|------|------|----------|
| `/data/tmp` | ZIP 解压临时区，上传 10GB ZIP 需要约 20GB 临时空间 | 至少 20GB |
| `/data/zigaa` | 训练数据存放区 | 根据数据量 |

### 5. 初始化

> `init.sh` 会验证数据库连接，因此数据库和用户必须已在第 2 步创建好。

```bash
./init.sh
```

自动完成：依赖检查 → 数据库连接验证 → Python venv → 安装后端依赖 → 安装前端依赖 → 创建 uploads/log 目录。

### 6. 启动

```bash
# 开放端口（有防火墙时，3111 供浏览器访问，8111 供前端 proxy 转发）
sudo ufw allow 3111/tcp
sudo ufw allow 8111/tcp

./start.sh      # 后端 8111 + 前端 3111
./stop.sh       # 停止所有服务
```

| 服务 | 地址 |
|------|------|
| 前端应用 | http://localhost:3111 |
| 后端 API 文档 | http://localhost:8111/docs |

### 7. 日常运维

```bash
./start.sh          # 启动
./stop.sh           # 停止
./stop.sh && ./start.sh   # 重启

tail -f log/backend.log     # 查看后端日志
tail -f log/frontend.log    # 查看前端日志
```

- **修改 `.env`**：必须重启服务 (`./stop.sh && ./start.sh`)
- **修改代码**：后端 Uvicorn 和前端 Vite 均支持热更新，无需手动操作

### 默认账号

| 用户名 | 密码 | 角色 | 说明 |
|--------|------|------|------|
| zigaa | zigaa123 | admin | 管理员，可管理用户 |
| zigaatest | zigaa123 | user | 普通用户 |

## 📖 文档

| 文档 | 内容 |
|------|------|
| [DEPLOY.md](./DEPLOY.md) | 部署手册（零基础部署指南，含配置详解与常见问题） |
| [PLAN.md](./PLAN.md) | 实施规划与后续迭代 |
| [backend/ARCHITECTURE.md](./backend/ARCHITECTURE.md) | 后端整体架构与业务流程 |
| [backend/STRUCTURE.md](./backend/STRUCTURE.md) | 后端目录结构与 API 端点索引 |
| [backend/DATABASE.md](./backend/DATABASE.md) | 数据库 schema |
| [frontend/ARCHITECTURE.md](./frontend/ARCHITECTURE.md) | 前端整体架构与业务流程 |
| [frontend/STRUCTURE.md](./frontend/STRUCTURE.md) | 前端目录结构与模块索引 |
| [frontend/STYLE.md](./frontend/STYLE.md) | 视觉设计令牌与布局规范 |

## 🔧 常见问题

| 问题 | 排查 / 解决 |
|------|------------|
| `数据库不可达` | 检查 MySQL 是否运行 (`systemctl status mysql`)，验证 `.env` 配置 |
| `端口被占用` | `sudo lsof -i :8111` 查找进程，或先运行 `./stop.sh` |
| `磁盘空间不足` | `df -h` 检查，`rm -rf /data/tmp/*` 清理临时文件 |
| `uv: command not found` | `source ~/.bashrc` 使环境变量生效 |
| 前端能访问但 API 404 | 检查后端是否启动 (`curl http://localhost:8111/docs`) |
| 后端启动失败 | 检查 `log/backend.log`，确认 `.env` 中 `JWT_SECRET` 非空 |

## 📝 License

MIT
