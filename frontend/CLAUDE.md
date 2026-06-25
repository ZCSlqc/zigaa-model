# Zigaa 前端 — 核心约束

> Vue 3 + Vite + TypeScript + Element Plus + Konva + Pinia
> 包管理: npm | 文档索引: [ARCHITECTURE.md](./ARCHITECTURE.md) [STRUCTURE.md](./STRUCTURE.md) [STYLE.md](./STYLE.md)

## 架构概览

整体架构、核心模块、关键业务流程见 [ARCHITECTURE.md](./ARCHITECTURE.md)。

## 构建

```bash
npm run dev      # dev server 3111，proxy /api → localhost:8111
npm run build    # vue-tsc → vite build
```

## 入口

`main.ts`: createApp → createPinia → router → ElementPlus(zhCN) → VueKonva → 注册图标 → mount('#app')

## 路由守卫

- `/login` 公开，已登录重定向 `/project`
- 其余需 token（localStorage）
- `/admin` 需 `role === 'admin'`
- 401 响应拦截器 → 清 localStorage → `router.replace('/login')`

## 标注系统核心原则

- 数据格式 `va[]`，坐标在**原始图片像素空间**
- Konva 画布 `v-stage` 以原图尺寸渲染，缩放通过 `scale` 控制
- HIT_RADIUS = 4px 屏幕像素，检测半径 `4 / scale`
- 边宽度 `ANNOTATION_EDGE_WIDTH / scale`，顶点半径 `ANNOTATION_VERTEX_RADIUS / scale`（hover `ANNOTATION_VERTEX_HOVER_RADIUS / scale`），边hover `ANNOTATION_EDGE_HOVER_WIDTH / scale`，删除按钮 `ANNOTATION_DELETE_BTN_RADIUS / scale` — 5个参数均在 .env 配置
- 两种模式: `draw`(crosshair) / `select`(default)；移除 pan 模式，平移由鼠标拖拽实现
- 撤销: 从 initialSnapshot 恢复 annotationData，而非重新加载服务器
- 视图状态持久化: 缩放/平移不随图片切换重置，全局保留 `scale`/`panX`/`panY`
- hover 检测在 select 模式下使用 stage DOM rect 计算鼠标坐标，不受 canvas-title 高度影响
- Tree 折叠高亮: 从时间戳文件夹起沿路径找第一个折叠的文件夹高亮（蓝色），全展开则高亮图片本身
- 树列表滚动置顶: 切换图片 / 折叠展开 / 全部展开 / 全部折叠时，高亮节点自动 scrollIntoView({ block: 'start' }) 置顶
- 图片路径显示: 面板顶部"全部展开/全部折叠"按钮上方显示当前图片 rel_path（相对 original/ 的相对路径），最多 2 行，悬停完整路径
- Tree 架构: sourceTree 为唯一真实数据源，displayTree 为 computed 视图层（`sourceTree.map(folder => {..., children: filter(children)})`），筛选时生成新浅拷贝数组
- 文件夹下载: ImagePanel/TreeItem 支持点击下载文件夹，弹出确认 → 进度弹窗，复用 useDownloadManager
- 路径工具: `utils/path.ts` 提供 `extractRelPath()`，从 URL 路径提取 rel_path（去除 `/original/` 前缀），全代码库统一使用
- 分类筛选: 面板右侧下拉筛选（全部/未标完/待确认），displayTree 实时过滤，计数联动更新
- canvas-title 区域: 图片信息（路径/通道/分辨率）+ 分类按钮（默认/未标完/待确认），互斥点击修改当前图片分类
- 图片外绘制: canvas 内图片外的点自动 clamp 到 `[0, imgW]×[0, imgH]` 边界
- 键盘左右切换限制在筛选树内，支持循环
- 路径规范: `path` = URL 路径（显示），`rel_path` = 相对于 original/ 的相对路径（标注操作/删除/文件夹）
- `category` 始终有值（`none`/`undone`/`pending`），TreeFile 不再用 `original_rel_path`

## 三态保存系统

- `annotationData`: 当前编辑态（用户操作修改的目标对象）
- `initialSnapshot`: 加载时的副本（`JSON.parse(JSON.stringify(res.data))`），用于撤销恢复
- `savedSnapshot`: 最后成功保存的副本，`save()` 前比较 `annotationData vs savedSnapshot`，相等则跳过 API 调用
- `save(isSilent, isAuto)`: `(true,true)`=静默自动保存（切图用），`(false,true)`=带 toast 自动保存，`(true,false)`=静默手动保存，`(false,false)`=带 toast 手动保存
- 每次成功保存后更新 `savedSnapshot`

## 切图流程

1. `selectImage(newImg)`: ① `save(oldImg)` ② `annotationData=null` ③ `currentImage=newImg`
2. watch 触发: ④ 清空 drawing 状态 ⑤ `await loadImage()` ⑥ `await store.loadAnnotation(newImg)`
3. 串行执行，确保先替换底图再加载新标注

## 绘制轮廓保存

- `finishPolygon` 弹出 label 对话框 → 回调中 `va.push()` → `save(true, false)`
- save 在 push 之后执行（避免保存空数据）

完整标注系统流程见 [ARCHITECTURE.md](./ARCHITECTURE.md)。

## 状态轮询

- ProjectView: 仅当有 `training` 或 `generating` 状态的模型时 10s 轮询，无活跃任务自动暂停
- `onActivated` 重新触发 startPolling

## Loading 交互规范

- 500ms 延迟显示 loading（`startLoading`/`stopLoading`），防止闪
- `:loading="isLoading(key)"` 每个按钮独立 key
- 不加 `:loading-text`，保留原按钮文字
- `hasLoading()` 判断是否有任何操作进行中，用于 `:disabled` 互斥兄弟按钮
- Dialog 内按钮如需即时反馈，使用独立 ref 绕过 500ms 延迟
- `useDelayedLoading()` 支持多 key（ProjectView、ModelDetailView），`useSingleLoading()` 单 key（AdminPanel）

## 分片下载

- `useDownloadManager` 管理所有下载状态（percentage/speed/eta/status）
- `cancel()` 仅设置 `isActive=false` + `controller.abort()`，是同步操作
- 清理在 `finally` 块中执行：`pendingCleanup` 在 `start()`/`downloadChunks()` 中设置，无论成功失败都调用
- `start()` 调用 `downloadInit` → `downloadChunks`；`startWithSession()` 跳过 init 直接下载
- `finishDownload`：Blob 组装 → 浏览器下载 → 发 `download-finished` 事件 → 后台异步 `deleteSession`
- 大文件（> chunk*200）先尝试 FileSystem API，失败回退 Blob
- **超时配置**：`downloadInit`/`downloadChunk` 使用 `LONG_TIMEOUT=1200000`（20min），其他操作 `DEFAULT_TIMEOUT=60000`

## 下载组件

- `BatchDownloadDialog.vue`：资源批次下载 + 文件夹下载，多批次顺序执行，每批次等待弹窗完成
- `DownloadDialog.vue`：模型下载（ProjectView），单一文件下载场景

## 板块规范

- 组件 `PascalCase.vue`，scoped SCSS
- Store Composition API `defineStore`
- API 统一走 `api/` 模块，禁止组件内直接 axios
- Props 显式类型，不用 `any`
- `camelCase`（变量/函数），`PascalCase`（组件/类型），UTF-8
- 删除操作需 `ElMessageBox.confirm` 二次确认
- Element Plus 已配置中文 locale（zhCN）
- 多处重复的代码立即抽取到 composables/ 或 utils/
