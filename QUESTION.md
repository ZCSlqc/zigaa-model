# 标注系统问题清单

> 最后更新: 2026-06-29
> 分类: 🟥 编译错误 / 阻塞 | 🟧 正确性 | 🟨 安全/性能 | 🟩 代码质量

---

## 🟥 编译错误 / 阻塞

### Q1: `_loadGen` 未声明 — AnnotateView.vue + PreviewView.vue

两个视图的 `loadImage()` 和 watch 回调中引用了 `_loadGen` 计数器做竞态保护，但都**漏写了 `let _loadGen = 0` 的声明**。
- `AnnotateView.vue`: watch (line ~1208), `loadImage()` (line ~496) 引用 `_loadGen` 但未声明
- `PreviewView.vue`: `loadImage()` (line ~274) 引用 `_loadGen` 但未声明

**影响**: Vite HMR 直接挂掉，白屏。

---

### Q2: `hasChanges` watch 在 reset 后误报

`AnnotateView.vue` 中的 `watch(() => store.annotationData, ..., { deep: true })` 在 `resetAnnotation` 执行 `store.annotationData = JSON.parse(...)` 时触发，将 `hasChanges` 设为 `true`。但紧接着 `savedSnapshot` 也被同步了，所以 UI 仍显示"有未保存更改"。

**影响**: 重置后 hasChanges 误报 true，直到下次手动保存才归零。

---

## 🟧 正确性问题

### Q3: `_origIdx` 在 `deleteEntry` 后变 stale

`currentEntries` computed 中 `_origIdx: i` 是 `va` 数组的索引。`deleteEntry` 调用 `va.splice(origIdx, 1)` 删除元素后，后续所有 `_origIdx` 全部错位。再次编辑/删除其他标注会操作错误索引。

**触发条件**: 连续 delete → edit 同一个标注。

**影响**: 编辑到错误的标注条目。

---

## 🟨 安全 / 性能

### Q4: 后端路径遍历 — `annotations.py`

所有标注端点 (`get_annotation`, `save_annotation`, `download_image`, `delete_image`, `delete_folder`) 的 `image_path` / `folder_path` 从 URL `{path}` 参数获取，**不做 `..` 序列过滤**。FastAPI 的 `{path:path}` 不自动解析 `..`。

```
GET /api/annotations/{id}/defect/../../etc/passwd/download
```

**影响**: 越权访问模型目录之外的文件。

---

### Q5: 下载接口未走统一 HTTP 客户端

`AnnotateView` 和 `PreviewView` 均用原生 `fetch()` 调用 `/download` 端点，手动从 localStorage 取 JWT token。与 axios interceptor 分离，没有统一的 `downloadAnnotation()` API 函数。

**影响**: 重复代码；token 存储机制变更时只改一处即可。

---

### Q6: 后端数据库并发更新无锁

`save_annotation`, `delete_folder`, `delete_image` 修改 `DataPackage` 后直接 `db.commit()`，无行级锁（`SELECT ... FOR UPDATE`）或乐观锁。并发操作同一条记录会丢失更新。

**影响**: 高频标注/删除场景数据不一致。

---

### Q7: `sanitize_dir_name` 不完整

`services/helper.py` 用 `name.replace("..", "")` 仅删除 `..` 字符串，但对 `...`（变成 `.`）或 `....`（变成 `..`）不处理，可被路径遍历绕过。

---

## 🟩 代码质量

### Q8: `_origIdx` computed 值失效后无自动刷新

与 Q3 相关 — `currentEntries` 返回时缓存 `_origIdx`，数组被 splice 后这些值不再有效，computed 不会自动刷新。

---

### Q9: Toolbar.vue 未使用的 import / CSS

- `import { ElMessageBox, ElMessage }` — `ElMessage` 未使用
- `.btn-reprocess` CSS 定义了但模板中无对应按钮

---

### Q10: `deleteFolder` 在 annotation store return 中重复返回

`annotation.ts` lines 536, 546 均 return `deleteFolder: deleteFolderFn`。第二次覆盖第一次，无害但代码异味。

---

### Q11: 类型安全缺失

- `resource.ts`: `editParameter(data: any)`, `saveAnnotation(data: any)` — 应为 `AnnotationData`
- `resource.ts`: `getUploadStatus(resourceType: string)` — 应为 union type
- `annotation.ts`: `buildTree` 参数使用 `any[]`

---

### Q12: `base64ToBlob` / `b64ToBlob` 重复代码

`AnnotateView.vue` 和 `PreviewView.vue` 各定义了一个相同的 base64 转 Blob 函数。

---

### Q13: 图片加载无 abort 机制

`AnnotateView` 和 `PreviewView` 的 `new window.Image()` 在快速切图时不会 abort 前一次加载，尽管用了 `_loadGen` 守卫，但前一次请求仍在网络层运行，浪费带宽。

---

### Q14: `getStagePoint` 无 null 守卫

`AnnotateView.vue` 中 `getStagePoint` 调用 `stage.getRelativePointerPosition()` 但没有检查 stage 是否为 null。

---

### Q15: ImagePanel 模板中 Pinia ref `.value` 冗余

`store.modelId.value` 和 `store.resourceType.value` 在模板中不需要 `.value`，Vue 自动解包。

---

## 📋 总结（第 1 轮检查）

| 严重度 | 数量 | 类别 |
|--------|------|------|
| 🟥 编译错误 | 2 | `_loadGen` 未声明, `hasChanges` 误报 |
| 🟧 正确性 | 2 | `_origIdx` stale, reset 行为 |
| 🟨 安全/性能 | 4 | 路径遍历, fetch 绕过 interceptor, DB 无锁, sanitize 不完整 |
| 🟩 代码质量 | 8 | 重复代码, 类型缺失, 未使用 import/CSS, 冗余 `.value`, 加载 abort, null 守卫 |

---

# 标注系统问题清单（第 2 轮检查）

> 最后更新: 2026-06-29
> 分类: 🟥 编译错误 / 阻塞 | 🟧 正确性 | 🟨 安全/性能 | 🟩 代码质量

---

## 🟥 编译错误 / 阻塞

### Q16: `_loadGen` 未声明 — 已确认，两视图均缺 `let _loadGen = 0`

AnnotateView.vue 和 PreviewView.vue 的 `loadImage()` 和 watch 回调中使用 `_loadGen++` 和 `const loadGen = _loadGen`，但文件中从未声明。TypeScript 编译未报错可能是因为 `vue-tsc --noEmit` 的 strict 模式未启用，但 Vite HMR 会在运行时直接报错。

**影响**: 白屏，无法进入标注页面。

---

### Q17: `hasChanges` watch 在 `resetAnnotation` 后误报

`AnnotateView.vue` 中 `watch(() => store.annotationData, ..., { deep: true })` 在 `resetAnnotation` 执行 `store.annotationData = JSON.parse(...)` 时触发 → `hasChanges = true`。但紧接着 `savedSnapshot` 也被同步了。

**影响**: 重置后 hasChanges UI 误报 true，直到下次手动保存才归零。

**修复方案**: `resetAnnotation` 中同步设置 `store.hasChanges = false`。

---

## 🟧 正确性问题

### Q18: `currentEntries` computed 中 `_origIdx` 在连续 delete 后错位（已记录为 Q3/Q8）

`deleteEntry` 调用 `va.splice(origIdx, 1)` 后，`currentEntries` computed 仍返回基于新 `va` 映射的新数组，但之前 for 循环中的 `entry._origIdx` 值已 stale。连续操作会删除/编辑到错误索引。

**触发条件**: 在 select 模式下连续点击多个标注的删除按钮。

**影响**: 删除到错误的标注，甚至可能越界。

---

### Q19: `updateDisplayTreeAfterCategoryChange` 对 computed 返回值 splice — 死代码

`displayTree` 是 `computed()`，每次依赖变化都会返回新对象。`updateDisplayTreeAfterCategoryChange` 直接对 `displayTree.value` 中的 folder 的 `children` 数组做 `splice`。但下一次 `displayTree` 重新计算时（如任何依赖变化），这个 splice 会被覆盖。

**影响**: 当 categoryFilter 激活时，此 splice 完全无效，是死代码。实际移除效果依赖 `sourceTree` 中 `found.category` 的变更。

---

### Q20: `handleStageMouseUp` 中连续 delete 在 for 循环内 — 与 Q18 同类

`handleStageMouseUp` 的 delete 按钮检查：
```ts
for (const entry of currentEntries.value) {
  // ...
  deleteEntry(entry._origIdx)
  return
}
```
此处有 `return`，所以不会连续删除。但后续如果再有人改写成无 return 的循环，就会触发 Q18。

---

### Q21: `selectImage` 递归重试后 `_pendingSwitch` 可能被提前清零

```ts
if (_pendingSwitch) {
  for (let i = 0; i < MAX_RETRIES && _pendingSwitch; i++) { ... }
  if (_pendingSwitch) return selectImage(img)
}
_pendingSwitch = true
try { ... } finally { _pendingSwitch = false }
```
第二次 `selectImage(img)` 进入后，如果 `imageSwitchGuard` 中的 `currentImage.value?.path === img.path` 匹配（因为第一次的 watch 可能已经触发了图片切换），则直接 return，不设置 `_pendingSwitch`。此时第一次的 `finally` 块已将 `_pendingSwitch = false`。这本身没有问题。但如果 `imageSwitchGuard` 不匹配（旧 watch 还未完成），第二次调用会重新进入。逻辑基本正确。

---

## 🟨 安全 / 性能

### Q22: URL path 参数未编码 — `resource.ts`

`saveAnnotation`, `deleteImage`, `deleteFolder`, `updateImageMsg` 均直接将 `imagePath`/`folderPath` 拼入 URL 路径段，未使用 `encodeURIComponent()`。如果文件名包含空格、中文等特殊字符，axios 可能不编码或错误编码。

**注意**: `AnnotateView` 中 `fetch()` 调用实际用了 `encodeURIComponent()`，但 `resource.ts` API 函数中没有。

---

### Q23: `base64ToBlob` / `b64ToBlob` 重复代码

`AnnotateView.vue` 定义 `base64ToBlob`（模块级别），`PreviewView.vue` 定义 `b64ToBlob`（嵌套在函数内，每次调用重新创建）。

---

### Q24: `getUploadStatus` 的 `resourceType` 参数类型为 `string` 而非 union

应限制为 `'good' | 'defect' | 'test' | 'template'`。

---

### Q25: `editParameter` / `saveAnnotation` 的 `data` 参数类型为 `any`

`editParameter` 应为 `Record<string, unknown>`，`saveAnnotation` 应为 `AnnotationData`。

---

### Q26: `buildTree` 参数使用 `any[]`

`buildTree` 的 `nodes` 参数类型为 `any[]`，应使用 TreeNode 类型。

---

## 🟩 代码质量

### Q27: Toolbar.vue 未使用的 `ElMessage` import

`import { ElMessageBox, ElMessage }` 中 `ElMessage` 从未被调用。

---

### Q28: Toolbar.vue 未使用的 `.btn-reprocess` CSS

模板中无 `btn-reprocess` 类，但 CSS 块定义了该样式。

---

### Q29: `deleteFolder` 在 store return 中重复

`annotation.ts` 返回对象中 `deleteFolder: deleteFolderFn` 出现两次（line 536, 546），第二次覆盖第一次。

---

### Q30: ImagePanel.vue 模板中 `.value` 冗余

`store.modelId.value` 和 `store.resourceType.value` 在 Vue 模板中不需要 `.value`（Pinia setup store 自动解包 ref）。

---

### Q31: ImagePanel.vue 下载默认值 fallback 为 `'defect'`

```ts
store.resourceType.value || (route.query.type as string) || 'defect'
```
从 PreviewView 进入时 `route.query.type` 为 `'test'` 或 `'template'`，但若两者都为空则 fallback 为 `'defect'`，对 preview 场景是错误的。

---

### Q32: TreeItem.vue 递归 `v-for` 使用 `:key="child.name"`

```html
<TreeItem v-for="child in folderNode!.children" :key="child.name" .../>
```
如果同一文件夹下有同名文件（如 `image_001.tif` 和 `image_001.jpg`），React 虚拟 DOM diff 会复用错误的 DOM 节点。应使用 `:key="child.path"`（path 是唯一标识）。

---

### Q33: `labelWidthPx` 的 `pts?` 参数未使用

`AnnotateView.vue` 中 `labelWidthPx` 签名声明了 `pts?` 属性但实际只使用 `labelname/label` 计算文本宽度。`getLabelWithArea` 已将面积文本合并入 label，所以 `labelWidthPx` 不需要 `pts`。但多余的类型声明是代码噪音。

---

### Q34: `loadImage` 无 abort 机制

快速切图时前一个 `new window.Image()` 的 `onload` 可能覆盖后一个的加载结果，即使有 `_loadGen` 守卫，前一次请求仍会浪费网络带宽。

---

### Q35: `handleStageMouseUp` 中 delete 检查有 return，但后续 edit 无此保护

`handleStageMouseUp` 中 delete 有 `return`，edit label 也有 `return`，所以单轮点击不会同时触发多个操作。但如果未来有人修改这个逻辑需要注意。

---

### Q36: `computeFolderSelected` 中 `myIdx` 计算错误

```ts
const myIdx = folderPath.split('/').length - 1
```
对路径 `a/b/c`，`split('/').length - 1 = 2`。但 `firstCollapsedIdx` 的循环从 `imageSegments.slice(0, i + 1)` 构造路径，`i` 从 0 开始。`firstCollapsedIdx` 是 segment 的索引（0-based），`myIdx` 是 path 的深度减 1。如果路径从根目录开始计数不一致，两者可能不对齐。不过当前实现中，`mySegmentIndex`（正常路径）的算法也是 `depth - 1`，两者应一致。仅在无 timestamp 文件夹的 fallback 路径中可能有细微偏差。

---

## 📋 总结（第 2 轮检查）

| 严重度 | 新增数量 | 类别 |
|--------|----------|------|
| 🟥 编译错误 | 1 (重复确认) | `_loadGen` 声明 |
| 🟧 正确性 | 4 | `_origIdx` 连续 delete, computed splice 死代码, reset hasChanges, mouseUp 保护 |
| 🟨 安全/性能 | 5 | URL 编码缺失, 类型缺失 x3, 下载无 abort |
| 🟩 代码质量 | 11 | 未使用 import/CSS, 重复 return, `.value` 冗余, `:key` 使用 name 而非 path, 冗余类型声明 |
