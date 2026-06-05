# Zigaa 大模型云平台 — 实施规划

> 工业缺陷检测平台的数据管理 Web 应用 + 本地模型训练
> 创建于 2026-05-13 | 最后更新 2026-06-04

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

端口: 后端 8111 / 前端 3111

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

- Konva 画布三种模式: draw（绘制轮廓）/ select（编辑）/ pan（平移）
- 多边形绘制: 点击打点、悬停末点回退、悬停起点闭合
- 标签输入、顶点拖拽、删除图元、撤销
- 目录树（递归 TreeItem）+ 标注状态点 + 缩略图
- 良品/缺陷/测试/模板资源切换
- 工具栏: 模式切换 / 保存 / 删除标注 / 撤销 / 删除图片 / 标签显隐
- 画布外点击取消绘制中多段线
- test/template 预览模式（只读，隐藏绘制/保存/删除标注/撤销）

### 本地训练与测试系统

- 训练：合并传输+触发，复制到 `TRAINING_DIR/{product_type}/{username}/{model_id}/`，写注册索引 JSON + status.json
- 测试生成：训练成功后触发，复制 test 数据到训练目录，写注册索引 `{product_type}/test/`
- 测试预览：test_status 为 success 时，标注 JSON 直接从 `upload_path/log/test/` 读取
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
