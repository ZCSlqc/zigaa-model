# 前端架构

> Vue 3 + Vite + TypeScript + Element Plus + Konva + Pinia

## 整体架构

```
                    ┌─────────────┐
                    │  Vue 3 App   │
                    │  main.ts     │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌───▼────┐ ┌────▼────┐
        │  Router   │ │ Pinia  │ │Element  │
        │  + Guards │ │ Stores │ │ Plus    │
        │           │ │(3)     │ │ + Konva │
        └───────────┘ └────────┘ └─────────┘
              │            │
              └────────────┼────────────┐
                           │            │
              ┌────────────┼────────────┤
              │            │            │
        ┌─────▼───┐ ┌─────▼───┐ ┌─────▼───┐
        │  views/ │ │compnts/ │ │  api/   │
        │  9 pages│ │ layout  │ │ + utils │
        │         │ │ upload  │ │         │
        │         │ │ download│ │         │
        │         │ │annotate │ │         │
        └─────────┘ └─────────┘ └─────────┘
                           │
                    ┌──────▼──────┐
                    │  Axios      │
                    │  /api       │
                    └─────────────┘
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 框架 | Vue 3.5 Composition API, `<script setup>` |
| 构建 | Vite 8, TypeScript 6, vue-tsc |
| UI | Element Plus 2.14 (zhCN) |
| 画布 | Konva 10 + vue-konva 3.4 |
| 状态 | Pinia 3 |
| 路由 | Vue Router 5 (history) |
| HTTP | Axios + 分级超时 |
| 编辑器 | CodeMirror 6 + JSON |
| 样式 | SCSS + CSS 变量（设计令牌） |

## 核心模块

### 路由与守卫 (router/index.ts)

10 条路由，`beforeEach` 单守卫：

| 路径 | 页面 | 守卫 |
|------|------|------|
| `/` | redirect | isLoggedIn ? /project : /login |
| `/login` | LoginView | 公开，已登录 → /project |
| `/user` | UserCenterView | requiresAuth |
| `/user/password` | PasswordView | requiresAuth |
| `/project` | ProjectView | requiresAuth |
| `/model/:modelId` | ModelDetailView | requiresAuth |
| `/annotate/:modelId` | AnnotateView | requiresAuth, `?type=good\|defect\|test\|template` |
| `/preview/:modelId` | PreviewView | requiresAuth, `?type` |
| `/guide` | GuideView | requiresAuth |
| `/admin` | AdminPanel | requiresAdmin |

- 已登录访问 `/login` → 重定向 `/project`
- 无 token 访问受保护路由 → 重定向 `/login`
- `/admin` 需 `role === 'admin'`
- axios 响应拦截器：401 → 清 localStorage → `router.push('/login')`

### 状态管理 (stores/)

| Store | 职责 |
|-------|------|
| `auth` | token/username/role，同步 localStorage，`isAdmin` computed |
| `project` | projects/models 列表，CRUD，训练/测试操作，`pollStatus` 本地更新 |
| `annotation` | 资源树、标注数据 va[]、图片选择、标注状态、文件夹回调 |

### HTTP 客户端 (api/client.ts)

- Axios 实例，`baseURL: '/api'`，默认超时 30s
- 长超时在 API 层指定：`resource.ts` LONG_TIMEOUT = 1200000ms = 20min（分片上传 chunk / 下载 init）
- 训练/测试在 API 层指定：`model.ts` timeout = 1200000ms = 20min（trainModel, runTest, downloadModelInit）
- 请求拦截器：`Authorization: Bearer <token>`
- 响应拦截器：401 → 清 localStorage → `router.push('/login')`
- Vite proxy：`/api` → `http://localhost:8111`

**超时策略**：

| 接口 | 超时 |
|------|------|
| 普通 CRUD / 标注 / 轮询 | 30s |
| ZIP `upload-chunk` / `download-init` / `downloadModelInit` | 20min |
| `trainModel` / `runTest` | 20min |

### 工具层

| 模块 | 职责 |
|------|------|
| `composables/useDelayedLoading` | 500ms 延迟 loading，Set 多 key / 单 key 变体 |
| `composables/useDebounceSearch` | 300ms 防抖搜索 |
| `composables/useDownloadManager` | 分片下载：init → 3 线程并行 → IndexedDB → Blob → 浏览器 |
| `utils/download-db.ts` | IndexedDB 持久化：chunks + sessions，prefix scan 优化 |
| `utils/model-status.ts` | 状态解析 / 标签类型 / 显示文本 / 按钮文本 / 角色标签 |
| `utils/format.ts` | `formatDate()` 日期格式化 |

## 关键业务流程

### ZIP 多文件队列上传

```
用户                    ZipUpload                     后端
 │                        │                             │
 ├── 选多个 ZIP ────────► │                             │
 │                        ├── 暂存区列表（可添加/删除）    │
 ├── 点击"上传"──────────► │                             │
 │                        ├── 同名文件去重               │
 │                        │                             │
 │                        ├── 文件 1: upload-init ───► │
 │                        ├── 文件 1: chunk loop ────► │  64MB chunk
 │                        ├── 文件 1: upload-complete► │
 │                        │◄── processing ───────────── │  立即返回（含 estimated_seconds）
 │                        │                             │
 │                        ├── 文件 1: 轮询 status ───► │  5s 间隔
 │                        │  倒计时每秒 -1，到 2s 停住  │
 │                        │◄── completed ────────────── │  状态文件保留（过期清理）
 │                        ├── emit(uploaded)            │
 │                        │                             │
 │                        ├── 文件 2: 同样流程 ──────► │  串行
 │                        │       ...                    │
 │                        ├── emit(all-uploaded)         │
 │                        └── 队列清空                   │
```

**关键点**：
- **同名去重**：`startUpload` 时对比队列中已有文件名，重复跳过并提示
- **串行上传**：一个传完再下一个，后端处理同类型串行 FIFO
- **upload-complete 立即返回**：后端异步拼接+解压，前端无需长超时
- **独立进度**：每个文件独立进度条、独立轮询 timer、独立倒计时 timer
- **倒计时**：后端 `estimated_seconds = max(5, GB * 6)`，每秒 -1 到 2s 停住
- **取消**：清除所有 timer + abort，后端异步继续不受影响
- **断点续传**：uploadId = FNV-1a(modelId + type + name + size + mtime)

### 分片下载

```
用户                    DownloadDialog               后端              浏览器
 │                        │                             │                 │
 ├── 点击下载 ───────────► │                             │                 │
 │                        ├── download-init ─────────► │  打包 ZIP      │
 │                        │◄── session_id + chunks ──── │                 │
 │                        │                             │                 │
 │                        ├── 3 线程并行 ─────────────► │                 │
 │                        │   chunk 1 ◄─────────────── │  8MB chunk     │
 │                        │   chunk 2 ◄─────────────── │                 │
 │                        │   chunk 3 ◄─────────────── │                 │
 │                        │                             │                 │
 │                        ├── saveChunk(IndexedDB)     │  断点续传       │
 │                        ├── 速度/ETA 实时更新 (EMA)   │                 │
 │                        │                             │                 │
 │                        ├── 全部完成 → Blob 组装      │                 │
 │                        ├── download-cleanup ──────► │                 │
 │                        ├── ObjectURL → <a>.click()  │           ◄───── │
 │                        ├── deleteSession(IndexedDB) │                 │
 │◄── 浏览器下载触发 ────── │                             │ ─────────────── │
```

**关键点**：
- `CONCURRENCY = 3`，并行下载分片
- **IndexedDB 持久化**（`zigaa-downloads`），刷新不丢失，断点续传
- 速度计算：EMA（0.3 新 + 0.7 旧）
- `startWithSession` 可跳过 init，用已有 session 数据直接下载

### 标注系统 (Konva + Pinia)

```
         ┌──────────────────────────────────────┐
         │         AnnotateView.vue             │
         │                                      │
         │  ┌──────────┐    ┌─────────────────┐ │
         │  │ 画布区    │    │ 图片面板 280px  │ │
         │  │ (flex:1) │    │                 │ │
         │  │          │    │ ImagePanel      │ │
         │  │ Toolbar  │    │ 文件路径          │ │
         │  │ (top)    │    │ ┌─────────────┐ │ │
         │  │          │    │ │ TreeItem    │ │ │
         │  │ v-stage  │    │ │ (recursive) │ │ │
         │  │ ──────── │    │ │             │ │ │
         │  │ bg image │    │ 全部展开/折叠   │ │
         │  │ v-path   │    │ 高亮自动置顶    │ │
         │  │ v-line   │    └─────────────┘ │ │
         │  │ v-label  │  两种模式：         │ │
         │  └──────────┘                     │
         └──────────────────────────────────────┘
                          │
                  annotation.ts (Pinia)
                          │
                  ┌───────▼───────┐
                  │  va[]         │
                  │  tree[]       │
                  │  currentImage │
                  └───────────────┘
```

**数据格式**：

```json
{
  "va": [
    {
      "label": 1,
      "labelname": "裂纹",
      "pts": [{"x": 100, "y": 200}, {"x": 150, "y": 180}, ...]
    }
  ],
  "width": 3024, "height": 3024, "wl": 2.5, "ww": 2.5
}
```

**交互**：

| 模式 | 光标 | 核心行为 |
|------|------|----------|
| `draw` | crosshair | 点击添加顶点，悬停最后一点（红）撤回，悬停第一点≥3点（绿）闭合 |
| `select` | default | 拖拽顶点，Shift+点击删除顶点，点击边插入顶点，点击标签编辑 |

- 坐标在**原始图片像素空间**，画布通过 `scale` 缩放
- HIT_RADIUS = 4px 屏幕像素，`4 / scale` 检测
- EDGE_HIT_RADIUS = 3px 屏幕像素，点击边插入顶点用
- 视图状态持久化: 缩放/平移全局保留，切换图片不重置，仅首次加载时 `centerImage()`
- 边宽度 `ANNOTATION_EDGE_WIDTH / scale`，顶点半径 `ANNOTATION_VERTEX_RADIUS / scale`（hover `ANNOTATION_VERTEX_HOVER_RADIUS / scale`），边hover `ANNOTATION_EDGE_HOVER_WIDTH / scale`，删除按钮 `ANNOTATION_DELETE_BTN_RADIUS / scale` — 5个参数均在 .env 配置
- 绘制灵敏度：`HIT_RADIUS`、`EDGE_HIT_RADIUS`、`DRAW_MIN_IMAGE_DIST`、`DRAW_MIN_SCREEN_DIST` 均通过 `VITE_*` 环境变量配置
- **Tree 折叠高亮**：从时间戳文件夹起沿路径找第一个折叠的文件夹高亮（蓝色），全展开则高亮图片本身。高亮在 `good/original` 之下生效，不冒泡到注入层
- **树列表滚动置顶**：切换图片、点击折叠/展开、点击"全部展开/全部折叠"时，高亮节点自动 `scrollIntoView({ block: 'start' })`
- 撤销：从 `initialSnapshot` 恢复 `annotationData`
- 快捷键：Tab 切换模式 / Space 撤回点 / Ctrl+S 保存 / Ctrl+Z 撤销 / ← → 切换图片
- **显示标签/隐藏标签**：控制多边形标签的显示/隐藏
- **显示轮廓/隐藏轮廓**（橙色按钮）：控制多边形填充和边的显示/隐藏（顶点、删除按钮、标签不受影响）
- test/template 资源 → PreviewView 只读渲染（右键平移 + 滚轮缩放）
- **画布标题栏**：canvas 顶部显示 `图片路径：xxx | 通道数：N（灰度/彩色） | 分辨率：W×H`。通道数来自 msgs 元信息，由后端 `image-info` 端点按需返回

### 测试预览流程

```
用户                       ModelDetailView              后端
 │                            │                          │
 ├── 点击"预览"(test) ──────► │                          │
 │                            ├── resolveTestStatus()    │
 │                            │                          │
 │                            │  test_status === 'success'?
 │                            │  ├── yes:                 │
 │                            │  │  ElMessage.success     │
 │                            │  │  "测试已成功，加载对应JSON标注"
 │                            │  └── no:                  │
 │                            │      ElMessage.warning    │
 │                            │      "测试未完成，标注数据可能为空"
 │                            │                          │
 ├──► 跳转 /preview/{id}?type=test                       │
 │                            │                          │
 ├──► PreviewView 加载 ──────► │                          │
 │   annotationStore.loadModel()                         │
 │   ├── getResourceTree() ──────────────────────────► │  读 uploads/目录树
 │   │  (图片列表，不变)                                │
 │   ├── 选图片 → getAnnotation() ──────────────────► │  _get_annotation_path()
 │   │                                                │  ├── test + success → upload_path/test/
 │   │                                                │  └── 否则 → uploads/test/original/
 │   │◄── {"va": [...]} ──────────────────────────── │
 │   └── 渲染标注叠加层                                │
```

**关键点**：
- 资源树（图片列表）始终从 `uploads/` 读取，不变化
- JSON 标注路径根据 test_status 动态切换
- 测试未完成仍可进入预览，但标注可能为空
- 无需迁移操作，直接读 `upload_path/test/`
- **画布标题栏**：同 AnnotateView，显示图片路径、通道数、分辨率
- **ImagePanel**：共享组件，test/template 下显示为"测试图片"/"模板图片"
- **标注渲染**：只读显示 va[]（填充+边+标签），无 hover 交互、无顶点拖拽

### 日志查看

| 按钮 | 位置 | 接口 | 说明 |
|------|------|------|------|
| 训练日志 | ProjectView | `GET /models/{id}/log/training` | 弹出对话框显示最后 100 行 |
| 测试日志 | ModelDetailView（测试资源区） | `GET /models/{id}/log/test` | 同上 |

- 前端 store: `getLogs` / `getTestLogs`，返回 `res.data.log` 纯文本
- 对话框用 `<pre>` 渲染，`max-height: 400px` 可滚动

### 项目页面状态轮询

- `ProjectView` 轮询间隔 = `VITE_POLL_INTERVAL`（.env 配置，默认 10s）
- 仅当有 `training` 或 `generating` 状态时运行，所有完成后自动暂停
- `onActivated` 重新触发（从子路由返回，`<keep-alive>` 缓存）

## 核心组件详解

### components/Upload/ZipUpload.vue — 分片上传组件

管理大文件 ZIP 的分片上传全流程。

| 功能 | 说明 |
|------|------|
| 文件选择 | 支持多文件，每个文件独立队列项 |
| 分片计算 | 默认 64MB/片，自动计算 total_chunks |
| 上传流程 | `upload-init` → 循环 `upload-chunk` → `upload-complete` |
| 进度显示 | 实时百分比 + 已传 / 总计 |
| 异步处理 | `upload-complete` 返回后轮询 `upload-status`，显示处理倒计时 |
| 并发控制 | 同时最多 3 个分片上传（不同文件可并行） |

### components/Download/DownloadDialog.vue — 分片下载组件

模型或资源 ZIP 的分片下载，支持大文件。

| 功能 | 说明 |
|------|------|
| 初始化 | `downloadModelInit` 或 `resource_download_init`，后端打包 ZIP |
| 并行下载 | 3 线程同时请求不同分片 |
| 持久化 | 分片存入 IndexedDB，页面刷新不丢失 |
| 拼接 | 所有分片到齐后用 `Blob` 拼接 |
| 保存 | `a.click()` 触发浏览器下载 |
| 清理 | `downloadCleanup` 删除后端临时 ZIP |

### views/AnnotateView.vue — 标注编辑器

基于 Konva 的多边形标注编辑器，是前端最复杂的组件。

**工具栏**：返回 / 绘制轮廓 / 编辑/选择 / 保存标注 / 删除标注 / 撤销标注 / 删除图片 / 显示标签-隐藏标签 / 显示轮廓-隐藏轮廓（橙色）/ 良品-缺陷

**两种模式**：

| 模式 | 光标 | 操作 |
|------|------|------|
| `draw`（绘制轮廓） | crosshair | 单击加点、长按拖拽连续加点、靠近首点闭合 |
| `select`（选择编辑） | default/pointer | 拖拽顶点、点击边中点加顶点、Shift+点击删除顶点、删除整个标注 |

**坐标系统**：

```
用户鼠标 (屏幕像素)
  │
  ▼ e.evt.clientX/clientY
  │
  ▼ stage.getRelativePointerPosition()
  │
  pt = {x, y}  (图片像素坐标)
  │
  ▼
存入 va[].pts
```

- 画布以**原图尺寸**渲染（`v-stage` 的 `width/height` = 原图宽高）
- 缩放通过 `scaleX/scaleY` 实现，不改变数据坐标
- 所有交互点检测都用**图片像素空间**，阈值按 `scale` 缩放

**绘制交互**：

```
mouseDown (draw 模式)
  │
  ├── hoveredPointIdx == 最后一点 → 删除该点（点击撤销）
  ├── hoveredPointIdx == 0 且 >= 3 点 → 闭合多边形 → 弹出标签弹窗
  ├── 点击空白 → 加一个点
  └── 开始拖拽 (isDrawingDrag = true)
        │
        mouseMove
          │
          ├── 距离上一个点 >= max(2, 12/scale) 像素 → 加新点
          └── 检测首点 hover（绿色提示可闭合）
                │
                mouseUp
                  │
                  ├── 靠近首点 → 闭合 → 标签弹窗
                  └── 远离首点 → 保持绘制状态，下次点击继续加点
```

**数据格式**（`va[]`）：

```json
{
  "va": [
    {
      "label": 1,
      "labelname": "划痕",
      "pts": [
        { "x": 100, "y": 200 },
        { "x": 150, "y": 180 },
        { "x": 180, "y": 220 },
        { "x": 120, "y": 250 }
      ]
    }
  ],
  "width": 1920,
  "height": 1080,
  "wl": 0,
  "ww": 0
}
```

- `pts` 是多边形顶点，按绘制顺序排列，首尾不需重复（自动闭合）
- 坐标是**原图像素坐标**，不是画布或屏幕坐标
- `labelname` 是用户输入的标签名

### components/Editor/JsonEditor.vue — JSON 编辑器

CodeMirror 6 包装组件，用于直接编辑标注 JSON 和模型参数。

- 支持语法高亮、缩进、格式错误提示
- 保存时走 `saveAnnotation()` 或 `edit_parameter()` 接口
- 9 级校验同标注编辑器

### composables/useDelayedLoading.ts — 延迟 Loading

防止快速操作时 loading 闪烁。

| 函数 | 作用 |
|------|------|
| `startLoading(key)` | 启动 500ms 倒计时，到时才显示 loading |
| `stopLoading()` | 清除倒计时，隐藏 loading |
| `isLoading(key)` | 当前是否在显示指定 key 的 loading |
| `hasLoading()` | 是否有任何 loading 在进行 |

**两种变体**：
- `useDelayedLoading()` — 基于 `Set<string>`，支持多 key
- `useSingleLoading()` — 单 key，适用于只有一个操作的页面

## 前端状态流转

```
/login ──► POST /auth/login ──► localStorage.setItem('token') ──► /project

/project
  │
  ├── 创建项目 → POST /projects/ → fetchProjects()
  ├── 选择项目 → selectProject(id) → fetchModels(id)
  │
  └── 点击模型 → /model/{id}

/model/{id} (ModelDetailView)
  │
  ├── 上传 good/defect/test 资源
  │     └── ZIP 分片上传 → 异步处理 → 状态更新
  │
  ├── 上传参数 → JSON 文件 → parameter.json
  │
  ├── 训练 → POST /models/{id}/train → 数据传输 → 轮询状态
  │
  ├── 测试 → POST /models/{id}/run-test → 数据传输 → 轮询状态
  │
  └── 标注 → /annotate/{id}?type=good

/annotate/{id} (AnnotateView)
  │
  ├── 左侧图片列表 → build_resource_tree()
  ├── 选图片 → loadAnnotation() → GET /annotations/...
  ├── 绘制多边形 → va[].push({label, labelname, pts})
  ├── 保存 → saveAnnotation() → PUT /annotations/...
  └── 下一张 → selectImage(next) → 标注数据各自独立存储
```

## 文档索引

- 视觉设计令牌：[STYLE.md](./STYLE.md)
- 目录与组件索引：[STRUCTURE.md](./STRUCTURE.md)
- 开发约束：[CLAUDE.md](./CLAUDE.md)
