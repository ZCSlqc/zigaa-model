# Zigaa 后端 — 核心约束

> FastAPI + SQLAlchemy + MySQL + PyJWT + bcrypt + OpenCV
> 包管理: uv | 文档索引: [ARCHITECTURE.md](./ARCHITECTURE.md) [STRUCTURE.md](./STRUCTURE.md) [DATABASE.md](./DATABASE.md)

## 架构概览

整体架构、核心模块、关键业务流程见 [ARCHITECTURE.md](./ARCHITECTURE.md)。

## 启动入口（main.py）

`os.makedirs` → 清理过期缓存 → `init_db()` → `seed_users()` → `daily_cleanup` daemon → `FastAPI()` → Middleware（ReqTime + CORS）→ `include_router(...)` → `mount("/uploads", StaticFiles)`

RequestTimeMiddleware 记录 `scope["start_time"]`（ASGI 层），用于大文件传输日志计时。

## 认证

- JWT Bearer Token，24h，`get_current_user` → `{username, role, user_id}`
- 角色：`user` / `advanced` / `admin`
- `require_admin` → role != 'admin' 403
- `check_model_owner` → 404（不泄露资源是否存在）
- 训练/测试端点：`role != 'user'` 才能执行

## 数据库

```python
engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

`get_db()` yield db，FastAPI 依赖注入自动关闭。Schema 见 [DATABASE.md](./DATABASE.md)。

## 模型状态系统

单一 `status` JSON 列，三维度独立：

```json
{
  "file_status": {"status": "idle"},      // idle → ready → invalid
  "training_status": {"status": "idle"},  // idle → training → success/failure
  "test_status": {"status": "idle"}       // idle → generating → success/failure
}
```

状态读写函数（services/resource.py）保留其他维度不变。流转细节见 [ARCHITECTURE.md](./ARCHITECTURE.md)。

## 文件存储

uploads 在项目根目录，不在 backend/ 下。路径布局见 [ARCHITECTURE.md](./ARCHITECTURE.md)。

`app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR))` 提供静态服务。

## 下载查询参数

- `arrange_name`：`download-init` 支持此查询参数，按指定文件夹打包 ZIP（标注树文件夹下载场景）

## 路径规范

- `path`: URL 路径，格式 `/uploads/{model_id}/{resource_type}/original/{rel}`，用于显示/缩略图
- `rel_path`: 相对于 original/ 的相对路径，如 `timestamp/filename`，用于所有标注操作（保存/删除/文件夹）
- `build_resource_tree` 返回 path（URL 路径），前端从中提取 rel_path（去掉 `/original/` 前缀）
- `os.path.join` 行为：参数含绝对路径会丢弃前缀，因此所有文件操作使用相对路径

## 标注图片下载

- 路由：`GET /annotations/{model_id}/{resource_type}/{image_path:path}/download`
- 返回 `{"image": base64, "annotation": base64|null}`（base64 编码的图片 + 标注 JSON）
- 使用 `Response(content=json.dumps(payload), media_type="application/json")` 避免 FastAPI 默认序列化问题
- 前端用 `fetch` 获取 JSON，`atob` 解码 base64 → `Blob`，分别触发下载
- 标注不存在时 `annotation` 字段为 null，只下载图片

## 文件夹删除

- 路由定义顺序：`/folder/{path}` 在前，`/{image_path:path}` 在后（避免 `path:path` 贪婪匹配吞掉 `folder/` 前缀）
- 前端传 rel_path（不含 `/original/` 前缀），后端 `os.path.join(orig_base, folder_path)` 直接拼接
- 三层同步删除：original（shutil.rmtree）/ compress & preview（存在才删）
- `_find_top_empty_dir` + `_sync_rmdir_layers` 清理连续空目录

## ZIP 上传下载

分片上传/下载/异步队列/倒计时/清理流程见 [ARCHITECTURE.md](./ARCHITECTURE.md)。

关键文件：
- `services/chunk_upload.py` — 分片上传（文件锁 + 原子写入）
- `services/chunk_download.py` — 分片下载（threading.Lock + 原子写入）
- `services/zip_queue.py` — 两阶段异步：assemble 线程（拼接+解压+清理）+ worker 队列（per model+type 串行，传 extract_dir）
- `api/resources.py` — `_process_extracted_dir`（从解压目录复制+图片处理+DB写入，构建 msgs+errors dict）
- `api/annotations.py` — 单图标注 GET/PUT/DELETE + 文件夹删除 + PATCH msgs + 图片下载（base64 编码）。删除使用 `_find_top_empty_dir` 查找连续空目录，original/compress/preview 三端同步清理，`_cleanup_and_update_ledger` 统一处理台账
- `services/helper.py` — OpenCV 图片并行处理（ThreadPoolExecutor + GIL 释放）

## 板块规范

- `Depends(get_db)` + `Depends(get_current_user)` 依赖注入
- 新增 API 必须加 `tags`
- `snake_case`，UTF-8
- 文件上传 `os.path.basename()` 防路径穿越
- 每个模型每种 resource_type 只允许一条 data_packages 记录（UNIQUE）
- Python 环境用 `uv venv`
- 日志到 stdout（`start.sh` 重定向到 `/log/backend.log`）
