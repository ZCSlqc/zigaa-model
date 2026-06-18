# Zigaa 大模型云平台 — 实施规划

> 工业缺陷检测平台的数据管理 Web 应用 + 本地模型训练
> 创建于 2026-05-13 | 最后更新 2026-06-18

## 一、项目概述

**定位**: 工业缺陷检测平台，提供数据标注管理 + 本地模型训练全流程。
**用户**: zigaa（admin）/ zigaatest（user），密码 zigaa123

## 二、技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + TypeScript + Element Plus + Konva + vue-konva + Pinia |
| 后端 | FastAPI + SQLAlchemy + MySQL + PyJWT + bcrypt + OpenCV |
| 包管理 | uv（后端）+ npm（前端） |
| 数据库 | MySQL zigaa_platform utf8mb4 |

端口: 后端 8111 / 前端 3111（通过 `.env` 配置 `BACKEND_HOST`/`BACKEND_PORT`/`VITE_BACKEND_URL`，可自定义）

## 配置

- `.env` 统一配置端口和地址：`BACKEND_HOST`、`BACKEND_PORT`、`VITE_BACKEND_URL`
- `start.sh` 和 `vite.config.ts` 均从上述环境变量读取，改一处生效
- CORS `allow_origins=["*"]`（全来源开放，`allow_credentials` 自动切 `False`）

## 三、已实现功能

### 认证与用户

- JWT Bearer Token 24h，localStorage 存储
- 登录 / 登出（router.replace 跳转 /login）/ 改密码（验证原密码）
- 角色 user / advanced / admin，401 → 清 token → 跳转 /login
- 用户中心（信息展示 + 角色标签），导航栏显示用户名和角色标签

### 项目与模型管理

- 项目 CRUD（侧边栏列表 + 新建/删除对话框）
- 模型 CRUD + 状态系统（status JSON 列）
- 模型卡片：数据状态 + 训练状态双标签 + 训练模型 / 训练终止 / 检查日志 / 下载
- 训练按钮：非 ready 和普通用户点击弹出明确错误提示，不灰显
- 有 training/generating 模型时按 `VITE_POLL_INTERVAL` 轮询，无活跃任务自动暂停
- list_models N+1 优化：单次 GROUP BY 查询获取模型数量

### 数据资源管理

- 四种资源类型: good / defect / test / template
- ZIP 分片上传（64MB/chunk，支持断点续传、取消恢复、清除缓存）
- ZIP 分片下载（IndexedDB 持久化 + 断点续传 + 并行 3 线程 + 进度弹窗）
- 模型分片下载（init → chunk → assemble 流程，404 弹 ElMessage 不闪弹窗）
- ZIP 追加模式（同文件不覆盖，相对路径前缀冲突检测 + 自增后缀）
- 参数 JSON 上传 / 在线编辑（CodeMirror）/ 下载 / 删除
- 图片三级存储: original/ + compress/ + preview/
- 标注 JSON 校验器（9 级优先级）
- 删除资源自动清理磁盘 + 数据库台账
- test/template 不校验标注 JSON，可选上传不影响模型状态

### 标注编辑器

- Konva 画布两种模式: draw（绘制轮廓）/ select（编辑）（已移除 pan 模式，平移由鼠标拖拽实现）
- 多边形绘制: 点击打点、悬停末点回退、悬停起点闭合
- 标签输入、顶点拖拽、删除图元、撤销（从 initialSnapshot 恢复，而非重新加载）
- 目录树（递归 TreeItem）+ 标注状态点 + 缩略图
- 良品/缺陷/测试/模板资源切换
- 工具栏: 模式切换 / 保存 / 删除标注 / 撤销 / 删除图片 / 显示标签-隐藏标签 / 显示轮廓-隐藏轮廓（橙色）/ 良品-缺陷
- 图片外绘制: canvas 内图片外的点自动 clamp 到 `[0, imgW]×[0, imgH]` 边界
- select 模式 hover 检测使用 stage DOM rect 计算，不受 canvas-title 高度影响
- Tree 架构: sourceTree 为唯一真实数据源，displayTree 为 computed 视图层（每次筛选时浅过滤生成），tree 节点为浅拷贝
- 图片面板分类筛选：按 none/undone/pending 过滤 tree，实时更新计数，切换时清理无关 canvas
- canvas-title 区域分类按钮（默认/未标完/待确认），单图修改分类，tree 与 canvas 同步响应
- 键盘左右切换限制在筛选树内，支持循环
- DataPackage errors 从 list 重构为 dict（key=path），msgs dict 存储图片元信息（width/height/channels/category）
- 数据库迁移：确保 msgs 列存在，errors list→dict，扫描图片填充 msgs
- 后端目录树 build_resource_tree 返回 path（URL 路径），前端从中提取 rel_path（去掉 `/original/` 前缀），rel_path 用于所有标注操作
- 路径标准：path = URL 路径（用于显示），rel_path = 相对路径（用于标注保存/删除/文件夹操作）
- 文件夹删除：前端发送 rel_path，后端 os.path.join 直接拼接（original/compress/preview 三层），删除路由定义在 delete_image 之前避免 path:path 贪婪匹配
- 标注编辑器三态保存：annotationData（当前编辑态）/ initialSnapshot（加载时快照，给撤销用）/ savedSnapshot（最后保存态，跳过优化），save 前比较 annotationData vs savedSnapshot 决定是否调用 API
- 切图流程：selectImage 中先 save(oldImg) → annotationData=null → currentImage=newImg → watch 中串行执行 loadImage() → loadAnnotation()
- 防并发切图：selectImage 通过 _pendingSwitch 标记防止快速连击导致 race condition
- loadImage 返回 Promise，onload/onerror 用 Promise 包装，watch 中 await 等待图片完全加载后再加载标注
- 绘制轮廓保存：finishPolygon 弹出 label 对话框，回调中 va.push() → save()，避免 save 在 push 之前执行
- 自动保存：10s 定时器仅在 select 模式启动，save 参数 (isSilent, isAuto) 控制 toast 显示（false/true=自动保存，true/false=静默保存）
- 删除逻辑重构：_find_top_empty_dir 统一查找删除连续空目录，三端（original/compress/preview）同步清理，_cleanup_and_update_ledger 统一处理台账
- test/template 预览模式（只读，隐藏绘制/保存/删除标注/撤销）

### 本地训练与测试系统

- 训练：合并传输+触发，复制到 `TRAINING_DIR/{product_type}/{username}/{model_id}/`，写注册索引 JSON + status.json
- 测试生成：训练成功后触发，复制 test 数据到训练目录，写注册索引 `{product_type}/test/`
- 测试预览：test_status 为 success 时，标注 JSON 直接从 `upload_path/test/` 读取
- 读取 `status.json` 并同步到数据库（`VITE_POLL_INTERVAL` 轮询 poll_status，training + test 双状态）
- 训练/测试终止（写 status.json failure）
- 模型下载（训练完成后的 model/ 文件夹，分片下载）
- 回调接口（model-trainer 内网回调更新状态）
- train_model / run_test 前校验：普通用户 403

### 分片上传稳定性

- 文件锁（fcntl.flock）防并发写入 meta
- 原子写入（tmp + os.replace）
- owner_id 缓存于 meta，upload-chunk 跳过 DB 查询
- upload-complete 互斥锁（uploading 标记 + 409 重入保护）
- 缓存 uploaded_chunks 列表，不扫描文件系统
- 清除缓存：前端清 sessionStorage + 后端删分片目录

### 管理后台

- 用户管理: 列表 / 创建 / 角色切换(user/advanced/admin) / 重置密码 / 删除
- 项目管理: 全局列表（含模型子表）/ 删除，支持按项目名称和所属用户搜索
- 权限校验：共享 `check_model_owner`（core/auth.py），统一 ModelInfo 查询 + 项目所有权检查

### 其他

- 使用教程页面（GuideView）
- 预览页面（PreviewView，只读查看图片）
- 500ms 延迟 loading（composables/useDelayedLoading，独立 key 互不干扰）
- 共享工具函数（utils/format.ts, utils/model-status.ts 含角色标签/标签类型）
- 下载管理器（composables/useDownloadManager + utils/download-db IndexedDB 持久化）
- 下载组件（components/Download/DownloadDialog，进度弹窗 + 速度/ETA）
- 后端大文件日志（ZIP 上传/下载/传输耗时分段记录）
- 后端健壮性修复：ZIP 软链接穿越、分片清理检查 uploading、磁盘检查日志、index 路径 normpath
- 配置集中化：`.env` 统一端口/地址，`start.sh`/`vite.config.ts`/`config.py` 均从环境变量读取，CORS 全来源开放
- Bug 修复：`annotation.ts` 中 `updateImageMsgFn` 变量名 `cat` → `category`（拼写错误导致本地状态更新为 `undefined`）

## 四、数据模型

数据库详见 `backend/DATABASE.md`。核心表: users, projects, model_info, data_packages。

模型状态（单一 `status` JSON 列，三维度）:
```
文件:   idle → ready/invalid （由 DataPackage 台账驱动，update_model_status）
训练:   idle → training → success/failure（外部系统通过 status.json）
测试:   idle → generating → success/failure（外部系统通过 status.json）
```
三维度独立，`_ensure_status_dict` 保证结构完整。train_model 合并传输+触发训练。

## 五、文件存储

uploads 在项目根目录，不在 backend/ 下。

```text
zigaa-model/uploads/
├── {model_id}/
│   ├── good/original/ + compress/ + preview/
│   ├── defect/original/ + compress/ + preview/
│   ├── test/original/ + compress/ + preview/
│   ├── template/original/ + compress/ + preview/
│   └── parameter.json
```

训练目录: `TRAINING_DIR/{product_type}/{username}/{model_id}/`
临时目录: `UPLOAD_TMP_DIR/upload-chunks/{upload_id}/`

## 六、标注数据格式

```typescript
interface AnnotationData {
  va: Array<{
    label: number          // 自增数字
    labelname: string      // 用户输入
    pts: Array<{x: number, y: number}>  // 开放多边形
  }>
  width: number, height: number, wl: number, ww: number
}
```

坐标在原始图片像素空间，前端只做显示缩放。

## 七、后续迭代

| # | 功能 | 优先级 | 说明 |
|---|------|--------|------|
| 1 | 分页 | 中 | 管理后台列表 |
| 2 | Docker 部署 | 中 | docker-compose |
| 3 | SQLite → PostgreSQL | 低 | SQLAlchemy 层不动 |
| 4 | 操作审计日志 | 低 | 记录关键操作 |

## 八、开发铁律

- 后端改前端不动，前端不写 mapper 适配层
- 同一时间只推进唯一子模块，闭环再进下一个
- 严禁批量读取源码，只读当前层级 CLAUDE.md
- 测试通过后直接 commit
- UI 修改必浏览器实测
- 代码注释默认不写，仅 WHY 不直观时才加

## 九、文档导航

| 文件 | 内容 |
|------|------|
| `README.md` | 安装与启动 |
| `CLAUDE.md` | 全局总纲 |
| `backend/CLAUDE.md` | 后端核心约束 |
| `backend/STRUCTURE.md` | 后端目录/ORM/API/services 索引 |
| `backend/DATABASE.md` | 数据库 schema |
| `frontend/CLAUDE.md` | 前端核心约束 |
| `frontend/STRUCTURE.md` | 前端目录/路由/Store/标注系统索引 |
| `frontend/STYLE.md` | 视觉设计令牌/布局/组件规范 |
