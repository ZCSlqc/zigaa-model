# 后端架构

> FastAPI + SQLAlchemy + MySQL + PyJWT + bcrypt + OpenCV

## 整体架构

```
                    ┌─────────────┐
                    │  FastAPI     │
                    │  main.py     │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
   ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
   │  Middleware │ │    Router   │ │   Startup   │
   │  CORS       │ │   (6 APIs)  │ │  Seeds      │
   │  ReqTime    │ │             │ │  Cleanup    │
   └─────────────┘ └─────────────┘ └─────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌───▼────┐ ┌────▼────┐
        │   core/   │ │  api/  │ │services/│
        │  auth+jwt │ │ 6 APIs │ │ helpers │
        │  database │ │        │ │ queue   │
        │   config  │ │        │ │ upload  │
        └───────────┘ └────────┘ └─────────┘
              │            │            │
              └────────────┼────────────┘
                           │
                    ┌──────▼──────┐
                    │   MySQL     │
                    │  + Filesystem│
                    └─────────────┘
```

## 启动流程

`main.py` 按以下顺序初始化：

1. 创建目录 `UPLOAD_DIR`、`UPLOAD_TMP_DIR`
2. 一次性清理过期缓存：分片上传、下载会话、ZIP 状态
3. `init_db()` — 建表
4. `seed_users()` — 种子用户 zigaa (admin) / zigaatest (user)
5. `_daily_cleanup_worker()` — daemon 线程，每天凌晨执行一次清理
6. FastAPI 实例 → Middleware → Router → StaticFiles

## 核心模块

### 配置系统 (core/config.py)

手动解析 `.env`（`key=value`，跳过注释）。关键配置：

| 变量 | 说明 | 默认 |
|------|------|------|
| `JWT_SECRET` | **必填**，无 fallback | — |
| `DATABASE_URL` | DB_HOST/DB_USER/... 拼接 | mysql+pymysql://... |
| `UPLOAD_DIR` | 上传目录 | `{BASE_DIR}/uploads` |
| `UPLOAD_TMP_DIR` | 临时目录 | `/data/tmp` |
| `TRAINING_DIR` | 训练注册目录 | `/data/zigaa` |
| `CLEANUP_STALE_HOURS` | 过期缓存保留时长 | 48 |

### 认证系统 (core/auth.py)

- **bcrypt** 密码哈希
- **JWT HS256 24h**，claims: `sub`(username) / `role` / `uid`(user_id) / `exp`
- `get_current_user()` — FastAPI 依赖注入，解析 Bearer Token → DB 查用户 → `{username, role, user_id}`，失败 401
- `require_admin()` — role != admin → 403
- `check_model_owner()` — 模型归属校验，失败 404（不泄露资源是否存在）

### 数据库层 (core/database.py + core/models.py)

- 连接池：`pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`, `pool_recycle=3600`
- 4 表级联：`User → Project → ModelInfo → DataPackage`（全部 `cascade="all, delete-orphan"`）
- 详细表结构见 [DATABASE.md](./DATABASE.md)

### API 层 (api/)

6 个路由器，RESTful 风格，统一 tags。完整端点列表见 [STRUCTURE.md](./STRUCTURE.md)。

| 模块 | 前缀 | 职责 |
|------|------|------|
| `auth` | `/api/auth` | 登录/登出/用户信息/改密码 |
| `projects` | `/api/projects` | 项目 CRUD |
| `models` | `/api/models` | 模型 CRUD + 训练/测试/日志/状态轮询/模型下载 |
| `resources` | `/api/resources` | ZIP 分片上传/下载/删除 + 参数 JSON + 磁盘检查 + 目录树 |
| `annotations` | `/api/annotations` | 标注 GET/PUT/DELETE + 文件夹删除 |
| `admin` | `/api/admin` | 管理后台（用户/项目 CRUD） |

## 关键业务流程

### ZIP 分片上传

```
前端                           后端                              文件系统
 │                              │                                 │
 ├── upload-init ─────────────► │                                 │
 │                              ├── init_upload() ─────────────► upload-chunks/{id}.json
 │◄── upload_id + chunks ────── │                                 │
 │                              │                                 │
 ├── upload-chunk (N 次) ────► │                                 │
 │                              ├── save_chunk() ──────────────► upload-chunks/{id}/{n}
 │◄── progress ──────────────── │  文件锁 fcntl.flock 幂等         │
 │                              │                                 │
 ├── upload-complete ─────────► │                                 │
 │                              ├── set_uploading() 互斥锁        │
 │                              ├── enqueue_assemble_and_process()► upload-status/{id}.json
 │◄── {"status":"processing"} ─ │  立即返回                        │
 │                              │   [后台 assemble 线程]          │
 │                              │   ├── assemble_upload() ─────► assembled.zip
 │                              │   ├── 解压 ZIP ─────────────► /data/tmp/tmp_xxx/
 │                              │   ├── cleanup_upload() ──────► 清理分片 + ZIP
 │                              │   └── 入队 (传 extract_dir)     │
 │                              │   [后台 worker 队列]            │
 │                              │   ├── _process_extracted_dir()│
 │                              │   │   ├── 复制到 original/    │
 │                              │   │   ├── process_images_parallel()
 │                              │   │   │   └── cv2 ThreadPoolExecutor
 │                              │   │   ├── validate_annotations (仅 defect)
 │                              │   │   └── 更新 DataPackage ─► MySQL
 │                              │   ├── 更新状态 completed        │
 │                              │   └── shutil.rmtree(extract_dir)│
 │                              │                                 │
 ├── upload-status 轮询 ──────► │  读状态文件（不删除，过期清理）  │
 │◄── completed/result ──────── │                                 │
```

**关键点**：
- **断点续传**：uploadId 由 FNV-1a hash(modelId + type + name + size + mtime) 生成，同文件复用
- **文件锁**：`fcntl.flock` 保护 meta 读写，原子写入（写临时文件 + `os.replace`）
- **互斥**：`set_uploading(True)` 防止重复处理，已存在则 409
- **两阶段异步**：assemble 线程（拼接+解压+清理分片）与 worker 队列（复制+图片处理）解耦，通过 extract_dir 传递
- **队列**：按 `(model_id, resource_type)` 串行 FIFO（daemon 线程），保证追加顺序
- **图片处理**：OpenCV `cv2.imread` + `cv2.imencode` + `ThreadPoolExecutor`（GIL 释放，真正并行），`min(4, cpu_count)` 线程
- **状态文件**：`upload-status/{id}.json` 持久化，`upload-status` 端点返回 completed/failed 后删除，未完成的 `CLEANUP_STALE_HOURS` 兜底
- **预估时间**：`max(5, GB * 6)` 秒，写入状态文件供前端倒计时

### ZIP 分片下载

```
前端                           后端                          文件系统
 │                              │                              │
 ├── download-init ───────────► │                              │
 │                              ├── _get_resource_src_dir() ─► uploads/{model_id}/{type}/original/
 │                              ├── 打包 ZIP (ZIP_STORED) ──► /data/tmp/tmp_xxx.zip
 │                              ├── create_download_session()► download-sessions/{id}.json
 │◄── session_id + chunks ──── │  8MB chunk, total_chunks     │
 │                              │                              │
 ├── download-chunk (3 并行) ─► │                              │
 │                              ├── get_chunk()                │
 │                              │   ├── _read_meta(threading.Lock)
 │                              │   │   更新 last_accessed     │
 │                              │   └── seek + read ────────► tmp_xxx.zip
 │◄── chunk bytes + Range ──── │                              │
 │                              │                              │
 │   IndexedDB 持久化 + Blob 组装                               │
 │   ──► 浏览器下载触发                                           │
 │                              │                              │
 ├── download-cleanup ────────► │                              │
 │                              ├── delete_session()          │
 │                              │   ├── 删除 meta             │
 │                              │   └── 删除临时 ZIP ────────► 清理
 │◄── success ──────────────── │                              │
```

**关键点**：
- **直接打包 original/**：`_get_resource_src_dir` 返回 `uploads/{model_id}/{type}/original/` 整体，不取子目录
- **8MB chunk**，ZIP_STORED（无压缩省 CPU）
- **`threading.Lock`** 保护 meta（`flock` 基于 PID，同进程多线程不互斥）
- **原子写入**：先写 `.tmp` 再 `os.replace`，避免并发读到空文件
- **兜底清理**：`download-init` 失败时自动删除 ZIP + `CLEANUP_STALE_HOURS`（默认 48h）定时清理

### 模型训练流程

```
前端                           后端                          文件系统
 │                              │                              │
 ├── 点击"训练模型"────────────► │                              │
 │                              ├── 清旧目录 ──────────────► rmtree(dest_dir)
 │                              │                              │
 │                              ├── _transfer_model_data()    │
 │                              │   遍历 good/defect/template  │
 │                              │   shutil.copytree(          │
 │                              │     uploads/{type}/original/│
 │                              │     dest_dir/{type}/        │
 │                              │   )                         │
 │                              │   复制 parameter.json ────► dest_dir/
 │                              │   创建 log/training/ ─────► dest_dir/
 │                              │                              │
 │                              ├── 写 status.json ────────► {"training_status": "training"}
 │                              ├── 写 training.log ───────► 模型开始训练，请等待
 │                              ├── 写注册索引 ───────────► training/{timestamp}_{user}_{id}.json
 │                              ├── DB: training_status=training
 │◄── success ───────────────── │                              │
 │                              │                              │
 ├── poll-status 轮询 ────────► │  读 status.json ─────────► 外部系统写入结果
 │                              ├── 同步到 DB                 │
 │◄── training_status ───────── │                              │
 │                              │                              │
 ├── 点击"终止训练"────────────► │                              │
 │                              ├── 写 status.json ───────► {"training_status": "failure", "error": "manual stop"} │
 │                              ├── DB: training_status=failure │
 │◄── success ───────────────── │                              │
```

**数据传输细节**：
- `_transfer_model_data` 遍历 `good`/`defect`/`template`，直接将 `uploads/{model_id}/{type}/original/` 整体复制到 `dest_dir/{type}/`
- `product_type` 从 `parameter.json` 读取，决定 `TRAINING_DIR/{product_type}/{username}/{model_id}/`
- 注册索引路径：`{TRAINING_DIR}/{product_type}/training/{timestamp}_{username}_{id}.json`
- 索引内容包含 `status.json` 路径 + 所有资源路径（不含 test）
- 日志占位：`log/training/training.log` 写入时间戳 + "模型开始训练，请等待"

### 测试生成流程

```
前端                           后端                          文件系统
 │                              │                              │
 ├── 点击"测试生成"────────────► │                              │
 │                              ├── 删除旧 test/log/test ──► dest_dir/
 │                              │                              │
 │                              ├── shutil.copytree(          │
 │                              │   uploads/test/original/    │
 │                              │   dest_dir/test/            │
 │                              │ )                           │
 │                              ├── 创建 log/test/ ─────────► dest_dir/
 │                              ├── 写 status.json ────────► {"test_status": "generating"}
 │                              ├── 写注册索引 ───────────► test/{timestamp}_{user}_{id}.json
 │                              ├── DB: test_status=generating
 │◄── success ───────────────── │  索引包含 test 资源路径      │
 │                              │                              │
 ├── poll-status 轮询 ────────► │  读 status.json ─────────► 外部系统写入结果
 │                              ├── 同步到 DB                 │
 │◄── test_status ───────────── │                              │
 │                              │                              │
 ├── 点击"终止测试"────────────► │                              │
 │                              ├── 写 status.json ───────► {"test_status": "failure", "error": "manual stop"} │
 │                              ├── DB: test_status=failure   │
 │◄── success ───────────────── │                              │
```

**测试索引差异**：与训练索引相比，测试索引 `_build_resource_paths(dest_dir, include_test=True)` 包含 `test` 和 `log_test` 路径。

### 标注读取流程

```
前端                           后端                          文件系统
 │                              │                              │
 ├── 选择图片 ─────────────────► │                              │
 │                              ├── _get_annotation_path()    │
 │                              │                              │
 │                              │  resource_type == "test" ?   │
 │                              │  ┌── yes:                     │
 │                              │  │  查 DB → upload_path       │
 │                              │  │  test_status == "success" ?│
 │                              │  │  ├── yes:                  │
 │                              │  │  │   upload_path/test/ │
 │                              │  │  │   └──► JSON 标注文件     │
 │                              │  │  └── no:                   │
 │                              │  └── no (good/defect/etc):   │
 │                              │      uploads/{type}/original/ │
 │                              │      └──► JSON 标注文件       │
 │                              │                              │
 │◄── {"va": [...], ...} ────── │                              │
```

**标注路径逻辑**：
- `good`/`defect`/`template`：JSON 标注与图片同在 `uploads/{model_id}/{type}/original/`
- `test` 且 `test_status == "success"`：JSON 标注从 `upload_path/test/` 读取（测试框架输出位置）
- `test` 且状态非 success：fallback 到 `uploads/{model_id}/test/original/`
- 图片路径始终走 `uploads/`（`build_resource_tree` 不变）

### 模型状态系统

单一 `status` JSON 列，三维度独立流转：

```
文件:   idle ──► ready ──► invalid       (DataPackage 台账驱动)
训练:   idle ──► training ──► success/failure  (status.json 外部系统)
测试:   idle ──► generating ──► success/failure (status.json 外部系统)
```

- 状态读写函数保留其他维度不变
- `_ensure_status_dict` 兼容旧格式
- `train_model`：数据传输 → 写 `status.json` → 注册索引 → DB 更新
- `poll_status`：前端 10s 轮询（`VITE_POLL_INTERVAL`），读 `status.json` → 同步到 DB

### 日志读取

| 接口 | 路径 | 说明 |
|------|------|------|
| `GET /{id}/log/training` | `dest_dir/log/training/*.log` | 训练日志，返回最后 100 行 |
| `GET /{id}/log/test` | `dest_dir/log/test/*.log` | 测试日志，返回最后 100 行（generating/success/failure 均可读） |

- 读取 `.log` 文件，`f.readlines()[-100:]` 取最新 100 行
- 返回 `{"log": "..."}` 纯文本

### 测试删除保护

`DELETE /{id}/test`：如果 `test_status == "generating"` 返回 400，阻止在测试生成中删除测试数据。

### 标注校验系统 (services/validator.py)

9 级优先级校验 `va[]` JSON 格式，命中即返回：

| 级别 | 颜色 | 校验项 |
|------|------|--------|
| 1 | 红 | 缺少标注 JSON（不调入 validator，由调用方处理） |
| 2 | 红 | JSON 格式错误 |
| 3 | 红 | 缺少对象结构 / va 字段 |
| 4 | 红 | va 不是数组 |
| 5 | 红 | va 为空数组 |
| 6 | 黄 | entry 缺少 pts 或 pts 为空 |
| 7 | 黄 | pts 元素缺少 x/y |
| 8 | 黄 | 缺少 width/height |
| 9 | 黄 | 宽高与实际图片不匹配 |

### 定时清理系统

| 时机 | 操作 |
|------|------|
| 启动时 | `cleanup_stale_uploads()` + `cleanup_stale_downloads()` + `cleanup_stale_status()` |
| 每日凌晨 | daemon 线程 `_daily_cleanup_worker`，同上 |

- 分片上传缓存：`CLEANUP_STALE_HOURS`（默认 48h），以 meta 文件为入口
- 下载会话：`CLEANUP_STALE_HOURS`（默认 48h），以 `last_accessed` 判断
- ZIP 状态：`upload-status` 端点在返回 completed/failed 结果后即时删除，未完成的由 `CLEANUP_STALE_HOURS` 兜底

## 文件存储

### uploads/ (模型资源)

```
uploads/{model_id}/{type}/
├── original/        # 原始图片 + 标注 JSON（按时间戳子目录追加）
├── compress/        # 400px max, JPEG q60 (OpenCV INTER_AREA)
└── preview/         # 原尺寸, JPEG q95
```

静态挂载 `app.mount("/uploads", StaticFiles(...))`。

### /data/tmp/ (临时文件)

```
/data/tmp/
├── upload-chunks/{upload_id}/    # 分片 0,1,2... + .json meta
├── download-sessions/            # 下载会话 .json
├── upload-status/                # ZIP 处理状态 .json（endpoint 返回后删除，过期兜底）
└── tmp_xxx.zip                   # 下载临时 ZIP
```

### /data/zigaa/ (训练注册索引)

```
/data/zigaa/{product_type}/
├── {username}/{model_id}/
│   ├── good/                     # 良品数据（从 uploads 复制）
│   ├── defect/                   # 缺陷数据（从 uploads 复制）
│   ├── template/                 # 模板数据（从 uploads 复制）
│   ├── model/                    # 训练产出模型文件
│   ├── parameter.json            # 模型参数
│   ├── status.json               # 外部系统读写
│   └── log/
│       └── training/             # 训练日志
│           └── training.log
└── training/                     # 训练注册索引目录
    └── {timestamp}_{user}_{id}.json
```

**训练注册索引**内容（`_build_resource_paths(dest_dir, include_test=False)`）：

```json
{
  "status": "<dest_dir>/status.json",
  "detail": "<username>_<project_id>_<model_name>",
  "good": "<dest_dir>/good",
  "defect": "<dest_dir>/defect",
  "template": "<dest_dir>/template",
  "parameter": "<dest_dir>/parameter.json",
  "model": "<dest_dir>/model",
  "log_training": "<dest_dir>/log/training"
}
```

### /data/zigaa/ (测试注册索引)

```
/data/zigaa/{product_type}/
├── {username}/{model_id}/
│   ├── good/                     # 良品数据
│   ├── defect/                   # 缺陷数据
│   ├── template/                 # 模板数据
│   ├── test/                     # 测试数据（run_test 时从 uploads 复制）
│   ├── model/                    # 模型文件
│   ├── parameter.json            # 模型参数
│   ├── status.json               # 外部系统读写
│   └── log/
│       ├── training/             # 训练日志
│       └── test/                 # 测试结果 JSON（标注数据）
└── test/                         # 测试注册索引目录
    └── {timestamp}_{user}_{id}.json
```

**测试注册索引**内容（`_build_resource_paths(dest_dir, include_test=True)`）：

```json
{
  "status": "<dest_dir>/status.json",
  "detail": "<username>_<project_id>_<model_name>",
  "good": "<dest_dir>/good",
  "defect": "<dest_dir>/defect",
  "test": "<dest_dir>/test",
  "template": "<dest_dir>/template",
  "parameter": "<dest_dir>/parameter.json",
  "model": "<dest_dir>/model",
  "log_training": "<dest_dir>/log/training",
  "log_test": "<dest_dir>/log/test"
}
```

**区别**：测试索引比训练索引多出 `test`、`log_test` 两个路径字段。两个索引各自位于独立目录，文件名格式 `{YYYYMMDD_HHMMSS}_{username}_{model_id}.json`。

## 服务模块详解

### services/chunk_upload.py — 分片上传

处理大文件分片上传的核心模块，支持断点续传。

| 函数 | 职责 |
|------|------|
| `init_upload()` | 创建上传会话，写入 meta JSON（文件名、大小、分片数） |
| `save_chunk()` | 保存单个分片到磁盘，原子写入（先写临时文件再 rename） |
| `get_upload_status()` | 返回上传进度（已传分片数 / 总分片数） |
| `set_uploading()` | 标记上传会话为处理中，防止并发重复处理 |
| `assemble_upload()` | 所有分片到齐后按顺序拼接为完整 ZIP |
| `cleanup_upload()` | 删除分片和 meta 文件 |
| `cleanup_stale_uploads()` | 清理过期（> `CLEANUP_STALE_HOURS`）的未完成情况 |

**关键机制**：`fcntl.flock` 保护 meta 文件读写（OS 级文件锁，跨进程有效），防止并发写入导致数据损坏。

### services/chunk_download.py — 分片下载

模型 ZIP 分片下载模块，前端可并行请求多个分片。

| 函数 | 职责 |
|------|------|
| `create_download_session()` | 创建下载会话，记录 ZIP 路径、大小、分片信息 |
| `get_chunk()` | 按索引从 ZIP 读取指定大小的数据块 |
| `delete_session()` | 清理会话 meta 文件 |
| `cleanup_stale_downloads()` | 清理过期下载会话 |

**关键机制**：`threading.Lock` + `_atomic_write()` 写入 meta；CHUNK_SIZE = 8MB。

### services/zip_queue.py — ZIP 两阶段异步处理

两阶段异步：assemble 线程（拼接+解压+清理分片）→ worker 队列（图片处理），通过 extract_dir 解耦。

| 函数 / 类 | 职责 |
|-----------|------|
| `ProcessingQueue` | 每模型每类型一个队列，保证同一模型的上传串行处理 |
| `enqueue_assemble_and_process()` | 启动后台 assemble 线程（拼接+解压+入队），API 立即返回 |
| `_process_one()` | 从队列取任务，调用 `_process_extracted_dir()` 处理已解压目录 |
| `get_upload_status()` | 返回 ZIP 处理进度（文件锁读取，不删除状态文件） |
| `_delete_status()` | 删除状态文件（由 `upload-status` 端点在返回结果后调用） |

**关键机制**：daemon 线程持续消费队列，per model+type 的 `queue.Queue` 确保同一模型不会并发处理。assemble 线程与 worker 队列通过 extract_dir 解耦。

### services/helper.py — 图片处理 + 工具函数

使用 OpenCV（`cv2`）和图片并行处理 + 用户名/目录名校验。

| 函数 | 职责 |
|------|------|
| `sanitize_dir_name()` | 将字符串 sanitize 为安全的文件夹名（过滤 `..`、`/` 等） |
| `validate_username()` | 严格校验用户名（1-32 字符，字母+数字+下划线+中文） |
| `is_supported_image()` | 检查文件扩展名是否为支持的图片格式 |
| `get_image_size()` | 读取图片宽高 |
| `_process_image_worker()` | 单张图片处理：压缩（最大边 400px）+ 预览（原尺寸 q95） |
| `process_images_parallel()` | 使用 `ThreadPoolExecutor` 并行处理多张图片（min(4, cpu_count) 线程） |

**常量**：`VALID_ROLES = ("user", "advanced", "admin")`

**关键机制**：OpenCV 释放 GIL，多线程可真正并行。输出写到 `compress/` 和 `preview/` 目录。

### services/resource.py — 资源状态管理

模型资源和状态的读写操作。

| 函数 | 职责 |
|------|------|
| `validate_new_annotations()` | 校验新增图片标注 JSON（仅 defect，检查缺失） |
| `set_file_status()` | 设置文件状态（idle → ready → invalid） |
| `set_training_status()` | 设置训练状态，保留其他维度 |
| `set_test_status()` | 设置测试状态，保留其他维度 |
| `update_model_status()` | 根据 DataPackage 台账自动计算文件状态 |
| `clear_resource()` | 删除某类型资源的文件系统数据和台账 |
| `clear_model()` | 删除模型所有资源 |
| `update_single_image_error()` | 单图标注保存/删除后更新错误台账 |

### services/directory.py — 目录路径

| 函数 | 职责 |
|------|------|
| `get_model_dir()` | 返回 `uploads/{model_id}/` |
| `get_resource_dir()` | 返回 `uploads/{model_id}/{type}/` |
| `build_resource_tree()` | 遍历 `original/` 目录，生成图片树结构（只扫描图片文件） |

### api/resources.py — image-info 端点

| 端点 | 职责 |
|------|------|
| `GET /{model}/{type}/image-info?path=<xxx>` | 获取图片信息：宽高、通道数（`cv2.IMREAD_UNCHANGED` 读取原图，1=灰度, 3=彩色） |

按需调用（选图片时），前端 `channelsCache` 缓存每张图片的通道数，切换回来时优先使用旧值/缓存值，避免闪烁。不增加建树或上传的额外开销。

### services/validator.py — 标注校验

9 级优先级校验 `va[]` JSON 格式，详见**标注校验系统**章节。

---

## 数据流

```
前端请求
  │
  ▼
RequestTimeMiddleware（记录开始时间）
  │
  ▼
CORS Middleware
  │
  ▼
FastAPI Router
  │
  ├── get_current_user() ──► 解析 JWT ──► {username, role, user_id}
  │         │
  │         ├── 无效 token ──► 401
  │         └── 有效 ──► 继续
  │
  ├── check_model_owner() ──► DB 查询 ──► 404（统一不泄露资源存在性）
  │
  ▼
业务逻辑 (services/)
  │
  ├── 数据库操作 ──► SQLAlchemy ORM ──► MySQL
  ├── 文件操作 ──► 读写 uploads/ /data/tmp/ /data/zigaa/
  └── ZIP 处理 ──► zip_queue daemon 线程 ──► 异步处理
```

---

## 安全机制

### JWT 认证流程

```
登录 ──► 验证密码（bcrypt） ──► create_token() ──► HS256 签名 ──► 返回 token
                                                         │
使用 ──► Authorization: Bearer {token} ──► get_current_user()
                                   │          │
                                   │          ├── decode_token() ──► 验签 + 检查过期
                                   │          ├── 查 DB 用户是否存在
                                   │          └── 返回 {username, role, user_id}
```

- Token 有效期 24 小时，过期后重新登录
- `JWT_SECRET` 必须通过 `.env` 设置，代码中无 fallback

### 权限模型

| 角色 | 权限 |
|------|------|
| `user` | 创建项目/模型、上传/下载资源、标注（无权训练/测试） |
| `advanced` | user 的所有权限 + 训练/测试 |
| `admin` | 所有权限 + 管理后台（用户 CRUD） |

- `require_admin()`：非 admin 返回 403
- `check_model_owner()`：非资源所有者返回 404（不泄露资源是否存在）
- 训练/测试端点：`role != 'user'` 才能执行（防止普通访客触发）

### 路径安全

- ZIP 解压检查路径穿越：文件名含 `..` 或 `/` 开头直接拒绝
- 文件上传使用 `os.path.basename()` 丢弃路径前缀
- 静态文件服务通过 `app.mount("/uploads", StaticFiles)` 限制在上传目录内

---

## 文档索引

- 目录与 API 端点：[STRUCTURE.md](./STRUCTURE.md)
- 数据库 schema：[DATABASE.md](./DATABASE.md)
- 开发约束：[CLAUDE.md](./CLAUDE.md)
