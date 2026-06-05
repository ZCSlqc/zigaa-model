# Frontend 目录结构与模块索引

> 完整架构与流程见 [ARCHITECTURE.md](./ARCHITECTURE.md)

## 目录结构

```
frontend/src/
├── main.ts                  # createApp → Pinia → router → ElementPlus(zhCN) → VueKonva → mount
├── App.vue                  # <keep-alive include="Project"> + <router-view>
├── router/index.ts          # 路由表 + 导航守卫
├── composables/
│   ├── useDelayedLoading.ts # 500ms 延迟 loading（Set 多 key + 单 key）
│   ├── useDebounce.ts       # 防抖搜索 composable
│   └── useDownloadManager.ts # 分片下载管理器（3 线程 + IndexedDB + 速度/ETA）
├── utils/
│   ├── format.ts            # formatDate()
│   ├── model-status.ts      # 模型状态解析/标签/文本/按钮 + 角色标签
│   └── download-db.ts       # IndexedDB 分片下载持久化
├── stores/
│   ├── auth.ts              # token/username/role + localStorage
│   ├── project.ts           # projects/models + 模型操作（训练/测试/日志）
│   └── annotation.ts        # 标注编辑器状态（树/标注数据/图片选择）
├── api/
│   ├── client.ts            # Axios 实例 + JWT 拦截器 + 401 跳转 + 分级超时
│   ├── auth.ts              # 登录/登出/用户信息/改密码
│   ├── project.ts           # 项目 CRUD
│   ├── model.ts             # 模型 CRUD + 训练/测试/训练日志/测试日志/轮询 + 模型分片下载
│   ├── resource.ts          # 分片上传/下载/删除 + 目录树 + 标注 + 参数 + 磁盘检查
│   └── admin.ts             # 管理后台 API
├── components/
│   ├── Layout/
│   │   ├── AppLayout.vue    # 主布局（导航栏 + 内容区）
│   │   └── NavBar.vue       # 顶部导航栏（品牌/链接/用户下拉）
│   ├── Upload/
│   │   ├── ZipUpload.vue    # ZIP 多文件队列上传（分片/轮询/倒计时/取消）
│   │   └── JsonUpload.vue   # 参数 JSON 上传
│   ├── Download/
│   │   └── DownloadDialog.vue # 下载进度弹窗（进度条/速度/ETA/取消）
│   ├── Annotation/
│   │   ├── Toolbar.vue      # 工具栏（模式/保存/删除/资源切换/标签显隐）
│   │   ├── PreviewToolbar.vue # 预览模式工具栏（只读）
│   │   ├── ImagePanel.vue   # 左侧面板（目录树 + 图片计数）
│   │   └── TreeItem.vue     # 递归树节点（文件夹/图片 + 缩略图 + 状态点）
│   └── Editor/
│       └── JsonEditor.vue   # JSON 编辑器（CodeMirror 6）
├── views/
│   ├── LoginView.vue        # 登录页
│   ├── UserCenterView.vue   # 用户中心（角色 + 项目列表）
│   ├── PasswordView.vue     # 修改密码
│   ├── ProjectView.vue      # 项目列表 + 模型卡片（轮询 training 状态）
│   ├── ModelDetailView.vue  # 模型详情（资源上传/下载/状态/参数编辑）
│   ├── AnnotateView.vue     # 标注编辑器（Konva 画布核心）
│   ├── PreviewView.vue      # 图片预览（只读，test/template）
│   ├── GuideView.vue        # 使用教程
│   └── AdminPanel.vue       # 管理后台（用户/项目 CRUD）
└── styles/
    ├── main.scss             # 入口，导入 variables
    └── variables.scss        # 设计令牌（CSS 变量）
```

## Composables

### useDelayedLoading()

500ms 延迟 loading，Set 多 key，适用于多按钮并发（ProjectView）。

```ts
const { loadingActions, startLoading, stopLoading, isLoading, hasLoading } = useDelayedLoading()
```

### useSingleLoading()

单 key 精简版，适用于单 loading 页面（AdminPanel、ModelDetailView）。

```ts
const { loadingAction, startLoading, stopLoading, isLoading } = useSingleLoading()
```

### useDebounceSearch()

```ts
const debouncedFetch = useDebounceSearch(() => { /* fetch */ })
```

### useDownloadManager()

分片下载管理器。

```ts
const { state, start, startWithSession, cancel, reset, formatSize } = useDownloadManager()
// start(config)   — 调 init 然后下载分片
// startWithSession(config, sessionData) — 跳过 init，用已有 session 数据
// config.api.init/chunk/cleanup — 调用方注入具体 API 函数
```

- `CONCURRENCY = 3`，3 个并行 worker
- IndexedDB 断点续传
- 速度 EMA（0.3 新 + 0.7 旧）
- 完成 → Blob → 浏览器保存 → 清理

## Utils

### model-status.ts

```ts
// 文件状态
resolveDataStatus(raw)              → 'idle' | 'ready' | 'invalid'
dataStatusTagType(status)           → Element Plus tag type
dataStatusDisplayText(status)       → 中文显示文本

// 训练状态
resolveTrainingStatus(raw)          → 'idle' | 'training' | 'success' | 'failure'
trainingStatusTagType(status)       → Element Plus tag type
trainingStatusDisplayText(status)   → 中文显示文本
trainButtonText(status)             → 按钮文本
getTrainingFailureReason(status)    → 失败原因

// 测试状态
resolveTestStatus(raw)              → 'idle' | 'generating' | 'success' | 'failure'
testStatusTagType(status)           → Element Plus tag type
testStatusDisplayText(status)       → 中文显示文本
testButtonText(status)              → 按钮文本

// 角色
roleLabel(role)                     → '管理员' | '高级用户' | '普通用户'
roleTagType(role)                   → 'danger' | 'warning' | 'info'
```

### download-db.ts

IndexedDB (`zigaa-downloads`)，模块级连接缓存。

```ts
saveChunk(sessionId, index, data)   // 保存分片
getChunk(sessionId, index)          // 读取分片
getAllDownloadedChunks(sessionId)   // 已下载索引（IDBKeyRange 优化）
saveSession(record)                 // 保存会话元数据
deleteSession(sessionId)            // 清理会话 + 所有分片
getAllSessions()                    // 所有会话
```

## Store 说明

### auth.ts

token/username/role from localStorage。`setAuth()`, `clearAuth()`, `isAdmin` computed。

### project.ts

projects/models/当前项目。CRUD + `trainModel`, `stopTraining`, `getLogs`, `getTestLogs`, `pollStatus`, `runTest`, `stopTest`。

### annotation.ts

modelId/resourceType/annotationData/tree/currentImage。`loadModel`, `switchResourceType`, `selectImage`, `save`, `deleteCurrentImage`, `prevImage`, `nextImage`, `onFolderRemoved`。

## 构建配置

```typescript
// vite.config.ts
server: {
  port: 3111,
  proxy: {
    '/api':     { target: 'http://localhost:8111', changeOrigin: true },
    '/uploads': { target: 'http://localhost:8111', changeOrigin: true },
  },
}
```
