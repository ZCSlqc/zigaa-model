# Zigaa 大模型云平台 — 部署手册

本手册面向**首次部署**的运维/开发同事。按照步骤操作，可在干净的 Linux 服务器上完成部署。

预估部署时间：**30 分钟**（不含安装 MySQL）

---

## 1. 环境要求

### 1.1 操作系统

- **Linux**，推荐 Ubuntu 20.04+ 或 CentOS 8+
- 本手册以 Ubuntu 为例，其他发行版命令略有不同

### 1.2 硬件

| 资源 | 最低 | 推荐 |
|------|------|------|
| CPU | 2 核 | 4 核+ |
| 内存 | 4 GB | 8 GB+ |
| 磁盘 | 20 GB | 50 GB+（图片压缩/ZIP 解压需要大量临时空间） |

### 1.3 软件

| 软件 | 版本 | 用途 |
|------|------|------|
| Python | >= 3.10 | 后端运行环境 |
| Node.js | >= 18 | 前端构建和开发服务器 |
| MySQL | >= 8.0 | 数据库 |
| uv | 最新 | Python 包管理器（比 pip 快） |
| git | 任意 | 拉取代码 |

---

## 2. 安装前置依赖

### 2.1 安装 Python

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3 python3-venv

# 验证
python3 --version
# 输出应为 Python 3.10 或更高
```

### 2.2 安装 Node.js（使用 nvm）

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc
nvm install 18
node --version
npm --version
```

### 2.3 安装 MySQL 8.0

```bash
sudo apt install -y mysql-server-8.0
sudo systemctl start mysql
sudo systemctl enable mysql
```

验证：
```bash
mysql -u root -p -e "SELECT VERSION();"
```

### 2.4 安装 uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv --version
```

### 2.5 安装 git（通常已预装）

```bash
sudo apt install -y git
```

---

## 3. 获取代码

```bash
git clone <仓库地址>
cd zigaa-model
```

项目目录结构：

```
zigaa-model/
├── backend/          # FastAPI 后端
├── frontend/         # Vue 3 前端
├── uploads/          # 模型资源文件（自动创建）
├── log/              # 运行日志（自动创建）
├── .env              # 环境变量配置（需手动创建）
├── pyproject.toml    # Python 依赖
├── init.sh           # 初始化脚本
├── start.sh          # 启动脚本
└── stop.sh           # 停止脚本
```

---

## 4. 配置环境变量

在项目根目录创建 `.env` 文件：

```bash
nano .env
```

填入以下内容，**根据实际情况修改**：

```ini
# ===== 认证 =====
# JWT 签名密钥，必须修改！使用 uuidgen 生成随机值
# 生成命令: uuidgen
JWT_SECRET=4d39ff06-9430-40f6-8357-543da74c6d84

# ===== 数据库 =====
# MySQL 连接信息
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=zigaa
DB_PASSWORD=zigaa123
DB_NAME=zigaa_platform

# ===== 文件存储路径（重要） =====
# 模型资源存储位置（相对路径，相对于 backend/ 目录）
# 默认 ../uploads 即项目根目录下的 uploads/ 文件夹
# 这里存放用户上传的图片、压缩图、预览图、标注 JSON
UPLOAD_DIR=../uploads

# 上传临时目录（绝对路径）
# ZIP 文件解压和打包时需要大量临时空间，建议放在大磁盘分区
# 确保此目录存在且有写权限
UPLOAD_TMP_DIR=/data/tmp

# 训练数据输出目录（绝对路径）
# 模型训练/测试时，数据会传输到此目录
# 外部训练系统从此目录读取数据和写入结果
TRAINING_DIR=/data/zigaa

# ===== CORS 配置 =====
# 允许的前端访问地址，留空则只允许 localhost + 127.0.0.1
CORS_HOST=                         # 留空只允许 localhost；填服务器 IP 允许远程访问
CORS_PORT=3111

# ===== 其他配置 =====
# 临时文件清理时间（小时），超过此时长的未完成任务临时文件会被自动删除
CLEANUP_STALE_HOURS=48

# 前端轮询训练/测试状态的间隔（毫秒），10000 = 10 秒
VITE_POLL_INTERVAL=10000

# ===== 前端：标注编辑器尺寸（画布像素） =====
VITE_ANNOTATION_EDGE_WIDTH=0.6          # 边宽度（顶点描边复用此值）
VITE_ANNOTATION_VERTEX_RADIUS=1         # 顶点半径
VITE_ANNOTATION_VERTEX_HOVER_RADIUS=2.5 # 顶点 hover 半径
VITE_ANNOTATION_EDGE_HOVER_WIDTH=2.5    # 边 hover 宽度
VITE_ANNOTATION_DELETE_BTN_RADIUS=5     # 删除按钮半径

# ===== 前端：标注交互灵敏度 =====
VITE_HIT_RADIUS=4               # 顶点检测半径（屏幕像素）
VITE_EDGE_HIT_RADIUS=3          # 边插入检测半径（屏幕像素）
VITE_DRAW_MIN_IMAGE_DIST=1.5    # 拖拽绘制最小图片像素间距（取 max(图片间距, 屏幕间距/scale)，防止缩小后点过度密集）
VITE_DRAW_MIN_SCREEN_DIST=8     # 拖拽绘制最小屏幕像素间距（取 max(图片间距, 屏幕间距/scale)，防止缩小后点过度密集）
```

### 配置项详解

| 配置项 | 作用 | 默认值 | 修改影响 |
|--------|------|--------|----------|
| `JWT_SECRET` | API 认证密钥，所有请求都需要用它验证 | 无 | **必须修改**，泄露后可被伪造登录 |
| `DB_HOST` | MySQL 服务器地址 | `127.0.0.1` | 数据库不在本机时需改 |
| `DB_PORT` | MySQL 端口 | `3306` | 非标准端口需改 |
| `DB_USER` | 数据库用户名 | `zigaa` | 需与数据库创建的用户一致 |
| `DB_PASSWORD` | 数据库密码 | `zigaa123` | 生产环境务必修改 |
| `DB_NAME` | 数据库名 | `zigaa_platform` | 需预先创建 |
| `UPLOAD_DIR` | **资源存储路径**，存放所有模型数据 | `../uploads` | 修改后需确保目录存在且有足够空间 |
| `UPLOAD_TMP_DIR` | **上传临时目录**，ZIP 解压/打包用 | `/data/tmp` | 必须是大磁盘分区，空间至少是最大 ZIP 文件的 2 倍 |
| `TRAINING_DIR` | **训练数据目录**，训练/测试数据的传输目标 | `/data/zigaa` | 外部训练系统需能访问此目录 |
| `CLEANUP_STALE_HOURS` | 过期临时文件清理时间 | `48` | 上传中断超过此时长的文件会被清理 |
| `VITE_POLL_INTERVAL` | 前端轮询间隔 | `10000` | 改小会增加服务器压力，改大会降低响应速度 |
| `CORS_HOST` | 允许的前端访问 IP，留空则只允许 localhost/127.0.0.1 | 空 | 远程访问需填服务器 IP |
| `CORS_PORT` | 前端端口 | `3111` | 前端端口变更时同步修改 |
| `VITE_HIT_RADIUS` | 顶点检测半径（屏幕像素） | `4` | 调整鼠标靠近顶点时触发的灵敏度 |
| `VITE_HIT_RADIUS` | 顶点检测半径（屏幕像素） | `4` | 调整鼠标靠近顶点时触发的灵敏度 |
| `VITE_EDGE_HIT_RADIUS` | 边插入检测半径（屏幕像素） | `3` | 调整鼠标靠近标注边时触发插入的灵敏度 |
| `VITE_DRAW_MIN_IMAGE_DIST` | 拖拽绘制时两个点之间的最小图片像素间距 | `1.5` | 取 `max(图片间距, 屏幕像素/scale)`，防止缩小后点过度密集 |
| `VITE_DRAW_MIN_SCREEN_DIST` | 拖拽绘制时两个点之间的最小屏幕像素间距 | `8` | 取 `max(图片间距, 屏幕像素/scale)`，防止缩小后点过度密集 |

---

## 5. 创建数据库

**正常方式**（知道 root 密码）：

```bash
mysql -u root -p
```

```sql
CREATE DATABASE IF NOT EXISTS zigaa_platform DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'zigaa'@'%' IDENTIFIED BY 'zigaa123';
GRANT ALL PRIVILEGES ON zigaa_platform.* TO 'zigaa'@'%';
FLUSH PRIVILEGES;
EXIT;
```

> **注意**：如果修改了 `.env` 中的 `DB_USER`/`DB_PASSWORD`/`DB_NAME`，上面的 SQL 也要同步修改。

**免密登录**（忘记 root 密码）：

```bash
# 1. 启动免密模式
sudo mysqld_safe --skip-grant-tables --skip-networking &
sleep 3
mysql -u root

# 2. 在 MySQL 中重置密码
FLUSH PRIVILEGES;
ALTER USER 'root'@'localhost' IDENTIFIED BY '新密码';
EXIT;

# 3. 重启 MySQL 恢复正常模式
sudo systemctl restart mysql
```

---

## 6. 创建系统目录

```bash
# 创建临时目录和训练目录
sudo mkdir -p /data/tmp /data/zigaa

# 设置权限（$USER 是当前登录用户）
sudo chown -R $USER:$USER /data/tmp /data/zigaa
```

**目录用途**：

| 目录 | 用途 | 空间需求 |
|------|------|----------|
| `/data/tmp` | ZIP 解压临时区，上传一个 10GB ZIP 需要约 20GB 临时空间 | 至少 20GB |
| `/data/zigaa` | 训练数据存放区，模型训练/测试时数据传输至此 | 根据数据量 |
| `项目根目录/uploads/` | 模型资源（原图、压缩图、预览图、标注） | 根据数据量 |

---

## 7. 初始化项目

```bash
./init.sh
```

**这个脚本会自动完成**：
1. 检查 Python、Node.js、npm、uv、MySQL 是否已安装
2. 检查 `.env` 文件是否存在
3. 验证数据库连接
4. 创建 `uploads/` 和 `log/` 目录
5. 创建 Python 虚拟环境（`.venv/`）
6. 安装后端 Python 依赖
7. 安装前端 npm 依赖

**常见问题**：

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `缺少: mysql` | MySQL 未安装或未加入 PATH | 安装 MySQL 或 `sudo apt install mysql-client` |
| `数据库不可达` | `.env` 中的数据库信息错误或数据库未启动 | 检查配置并 `sudo systemctl start mysql` |
| `Permission denied` | 脚本没有执行权限 | `chmod +x init.sh` |
| `uv: command not found` | uv 未安装或环境变量未生效 | `source ~/.bashrc` 后重试 |

---

## 8. 启动服务

```bash
./start.sh
```

**这个脚本会**：
1. 杀掉残留的旧进程
2. 启动后端（端口 8111，日志写入 `log/backend.log`）
3. 等待后端就绪（最多 15 秒）
4. 启动前端开发服务器（端口 3111，日志写入 `log/frontend.log`）
5. 等待前端就绪（最多 15 秒）

**验证**：

```bash
# 检查后端
curl http://localhost:8111/docs
# 应返回 HTML（Swagger API 文档）

# 检查前端
curl http://localhost:3111
# 应返回 HTML
```

**访问地址**：

| 服务 | 地址 |
|------|------|
| 前端应用 | http://服务器IP:3111 |
| API 文档 | http://服务器IP:8111/docs |

> **远程访问**：如果服务器有防火墙，需开放 3111 和 8111 端口：
> ```bash
> sudo ufw allow 3111/tcp
> sudo ufw allow 8111/tcp
> ```

---

## 9. 日常运维

### 9.1 启动 / 停止 / 重启

```bash
./start.sh   # 启动
./stop.sh    # 停止
./stop.sh && ./start.sh   # 重启
```

### 9.2 查看日志

```bash
# 后端日志（实时）
tail -f log/backend.log

# 前端日志（实时）
tail -f log/frontend.log

# 最近 100 行
tail -n 100 log/backend.log
```

### 9.3 修改配置后

修改 `.env` 中的配置后，**必须重启服务**才能生效：

```bash
./stop.sh
./start.sh
```

### 9.4 修改代码后

- **后端**：Uvicorn 的 `--reload` 模式会自动重启，修改 Python 文件后无需手动操作
- **前端**：Vite 开发服务器会自动热更新，修改后浏览器刷新即可

### 9.5 备份数据

```bash
# 备份数据库
mysqldump -u zigaa -p zigaa_platform > backup_$(date +%Y%m%d).sql

# 备份用户上传的资源
tar -czf uploads_$(date +%Y%m%d).tar.gz uploads/
```

### 9.6 默认账号

| 用户名 | 密码 | 角色 | 说明 |
|--------|------|------|------|
| zigaa | zigaa123 | admin | 管理员，可管理用户 |
| zigaatest | zigaa123 | user | 普通用户 |

> **生产环境**：首次登录后请立即修改密码。

---

## 10. 常见问题

### 10.1 MySQL 连接失败

```
❌ 数据库 zigaa_platform 不可达
```

**排查**：
```bash
# 1. MySQL 是否运行？
sudo systemctl status mysql

# 2. 手动测试连接
mysql -h 127.0.0.1 -P 3306 -u zigaa -pzigaa123 -e "USE zigaa_platform"

# 3. 检查 .env 中的配置是否和数据库一致
cat .env | grep DB_
```

### 10.2 端口被占用

```
Error: listen EADDRINUSE: address already in use :::8111
```

**解决**：
```bash
# 查找占用端口的进程
sudo lsof -i :8111
sudo lsof -i :3111

# 杀掉进程或先运行 stop.sh
./stop.sh
```

### 10.3 磁盘空间不足

上传 ZIP 文件时报错 `磁盘空间不足`：

```bash
# 检查磁盘使用
df -h

# 清理临时文件
rm -rf /data/tmp/*

# 检查上传目录大小
du -sh uploads/
```

### 10.4 前端能访问但 API 请求 404

**本地**：检查后端是否运行
```bash
curl http://localhost:8111/docs
```

**远程**：额外确认以下事项：
- `CORS_HOST` 已设置为服务器 IP（或留空允许所有来源）
- 防火墙开放 3111 和 8111 端口

```bash
sudo ufw allow 3111/tcp
sudo ufw allow 8111/tcp
```

### 10.5 后端启动失败

```bash
# 查看错误日志
cat log/backend.log

# 常见原因：
# 1. Python 依赖未安装 → .venv/bin/pip list 检查
# 2. .env 中 JWT_SECRET 未设置 → 必须非空
# 3. 端口被占用 → lsof -i :8111
```

### 10.6 下载/训练超时

下载大型 ZIP 或训练时如果报超时，属于正常现象——超时已设为 20 分钟。如果仍觉得不够，可以修改前端 API 配置：

```bash
# 修改超时（20 分钟 = 1200000 毫秒）
# frontend/src/api/model.ts  → trainModel / runTest / downloadModelInit 的 timeout
# frontend/src/api/resource.ts → LONG_TIMEOUT 的值
```

---

## 附录 A：`.env` 完整示例

> 带 `VITE_` 前缀的变量仅前端读取，后端不处理。

```ini
# ===== 后端：认证 =====
JWT_SECRET=<uuidgen 生成随机字符串>

# ===== 后端：数据库 =====
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=zigaa
DB_PASSWORD=你的强密码
DB_NAME=zigaa_platform

# ===== 后端：文件存储 =====
UPLOAD_DIR=../uploads
UPLOAD_TMP_DIR=/data/tmp
TRAINING_DIR=/data/zigaa
CLEANUP_STALE_HOURS=48

# ===== 后端：CORS 跨域 =====
CORS_HOST=192.168.10.160
CORS_PORT=3111

# ===== 前端：标注编辑器尺寸 =====
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

# ===== 前端：轮询间隔（毫秒） =====
VITE_POLL_INTERVAL=10000
```

## 附录 B：目录权限参考

```bash
# 所有目录需当前用户有读写权限
ls -ld uploads/ log/ /data/tmp /data/zigaa
# 输出应类似: drwxr-xr-x  zigaa:zigaa  ...
```

## 附录 C：服务进程

运行 `./start.sh` 后会有两个后台进程：

| 进程 | PID 文件 | 日志文件 |
|------|----------|----------|
| 后端 (uvicorn) | `/tmp/zigaa-model_backend.pid` | `log/backend.log` |
| 前端 (vite) | `/tmp/zigaa-model_frontend.pid` | `log/frontend.log` |
