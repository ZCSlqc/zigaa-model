# Backend 目录结构与 API 索引

> 完整架构与流程见 [ARCHITECTURE.md](./ARCHITECTURE.md)

## 目录结构

```
backend/
├── main.py                # FastAPI 入口 + 种子用户 + 路由注册 + 静态文件挂载
├── core/
│   ├── config.py          # 手动解析 .env，JWT/DB/UPLOAD/TRAINING 配置常量
│   ├── database.py        # engine + SessionLocal + init_db + get_db
│   ├── models.py          # ORM 模型（User, Project, ModelInfo, DataPackage）
│   └── auth.py            # JWT + bcrypt + get_current_user + require_admin + check_model_owner
├── api/
│   ├── auth.py            # 登录/登出/用户信息/改密码
│   ├── projects.py        # 项目 CRUD（所有者权限）
│   ├── models.py          # 模型 CRUD + 训练/测试/日志/轮询 + 模型分片下载
│   ├── resources.py       # ZIP 分片上传/下载/删除 + 参数 JSON + 磁盘检查 + 目录树
│   ├── annotations.py     # 单图标注 GET/PUT/DELETE + 文件夹删除 + PATCH msgs（rel_path 用于操作，path 用于显示）
│   └── admin.py           # 管理后台（用户/项目 CRUD）
└── services/
    ├── helper.py          # OpenCV 图片处理 + 并行 + 用户名校验 + 路径 sanitization
    ├── directory.py       # 目录树构建 + 资源目录路径
    ├── validator.py       # 标注 JSON 校验器（va[] 格式，优先级 1-9）
    ├── resource.py        # 标注校验、台账、清理、模型状态（三维度 JSON）
    ├── chunk_upload.py    # 分片上传管理（init/save/assemble/cleanup，文件锁）
    ├── chunk_download.py  # 分片下载管理（session/chunk/cleanup，threading.Lock）
    └── zip_queue.py       # ZIP 异步处理队列（per model+type 串行，daemon 线程）
```

## 路由注册

| 模块 | 前缀 | tags |
|------|------|------|
| `api.auth` | `/api/auth` | auth |
| `api.projects` | `/api/projects` | projects |
| `api.models` | `/api/models` | models |
| `api.resources` | `/api/resources` | resources |
| `api.annotations` | `/api/annotations` | annotations |
| `api.admin` | `/api/admin` | admin |

## ORM 模型

> 主键/外键 UUID（String(36)），时间字段 String(32) ISO 格式

| 表 | 关键字段 | 约束 |
|----|----------|------|
| `users` | id, username, password_hash, role(user/advanced/admin), created_at, uploaded_at | username unique |
| `projects` | id, name, description, owner_id(FK CASCADE), created_at, uploaded_at | idx_projects_owner_id |
| `model_info` | id, name, description, project_id(FK CASCADE), status(JSON), upload_path, created_at, uploaded_at | idx_model_info_project_id |
| `data_packages` | id, model_id(FK CASCADE), resource_type, file_path, passed_count, failed_count, errors(JSON), created_at, uploaded_at | UNIQUE(model_id, resource_type) |

级联: `User → Project → ModelInfo → DataPackage`（全部 `cascade="all, delete-orphan"`）

详细表结构见 [DATABASE.md](./DATABASE.md)。

## API 端点索引

### auth (`/api/auth`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/login` | 登录 |
| POST | `/logout` | 登出 |
| GET | `/me` | 用户信息 |
| POST | `/change-password` | 改密码 |

### projects (`/api/projects`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 项目列表 |
| POST | `/` | 创建项目 |
| GET | `/{id}` | 项目详情 |
| PUT | `/{id}` | 更新项目 |
| DELETE | `/{id}` | 删除项目（级联清理） |

### models (`/api/models`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 模型列表 |
| POST | `/` | 创建模型 |
| GET | `/{id}` | 模型详情 |
| PUT | `/{id}` | 更新模型 |
| DELETE | `/{id}` | 删除模型 |
| POST | `/{id}/train` | 触发训练 |
| POST | `/{id}/stop-training` | 停止训练 |
| POST | `/{id}/run-test` | 触发测试 |
| POST | `/{id}/stop-test` | 停止测试 |
| GET | `/{id}/log/training` | 训练日志（最后100行） |
| GET | `/{id}/log/test` | 测试日志（最后100行） |
| GET | `/{id}/poll-status` | 轮询状态 |
| POST | `/{id}/model/download-init` | 模型下载初始化 |
| GET | `/{id}/model/download-chunk` | 模型下载分片 |
| POST | `/{id}/model/download-cleanup` | 模型下载清理 |

### resources (`/api/resources`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tree` | 目录树 |
| GET | `/{model}/{type}/image-info` | 图片信息（宽高、通道数） |
| POST | `/{model}/{type}/upload-init` | 上传初始化 |
| POST | `/{model}/{type}/upload-chunk` | 上传分片 |
| POST | `/{model}/{type}/upload-complete` | 上传完成（入队异步） |
| GET | `/{model}/{type}/upload-status/{id}` | 轮询处理状态 |
| GET | `/{model}/{type}/disk-check` | 磁盘空间 |
| POST | `/{model}/parameter/upload` | 参数上传 |
| PUT | `/{model}/parameter` | 编辑参数 |
| GET | `/{model}/parameter` | 获取参数 |
| DELETE | `/{model}/parameter/file` | 删除参数文件 |
| GET | `/{model}/parameter/download` | 下载参数 |
| DELETE | `/{model}/good\|defect\|test\|template\|parameter` | 删除资源（test: generating 时 400） |
| POST | `/{model}/{type}/download-init` | 下载初始化 |
| GET | `/{model}/{type}/download-chunk` | 下载分片 |
| POST | `/{model}/{type}/download-cleanup` | 下载清理 |

### annotations (`/api/annotations`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/{model}/{type}/{image}` | 获取标注 |
| PUT | `/{model}/{type}/{image}` | 保存标注 |
| DELETE | `/{model}/{type}/{image}` | 删除图片 |
| DELETE | `/{model}/{type}/folder/{path}` | 删除文件夹 |
| PATCH | `/{model}/{type}/msg/{path}` | 更新图片 msgs（category） |

### admin (`/api/admin`) — 仅 admin 角色

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/users` | 用户列表 |
| POST | `/users` | 创建用户 |
| PUT | `/users/{id}` | 更新角色 |
| POST | `/users/{id}/reset-password` | 重置密码 |
| DELETE | `/users/{id}` | 删除用户 |
| GET | `/projects` | 项目列表 |
| DELETE | `/projects/{id}` | 删除项目 |
