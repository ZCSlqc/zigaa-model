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
- 三种模式: `draw`(crosshair) / `select`(default) / `pan`(move)
- 撤销: 从服务器重新加载当前图片原始标注 JSON
- 视图状态持久化: 缩放/平移不随图片切换重置，全局保留 `scale`/`panX`/`panY`
- hover 检测在 select 模式下使用 stage DOM rect 计算鼠标坐标，不受 canvas-title 高度影响
- Tree 折叠高亮: 从时间戳文件夹起沿路径找第一个折叠的文件夹高亮（蓝色），全展开则高亮图片本身
- 树列表滚动置顶: 切换图片 / 折叠展开 / 全部展开 / 全部折叠时，高亮节点自动 scrollIntoView({ block: 'start' }) 置顶
- 图片路径显示: 面板顶部"全部展开/全部折叠"按钮上方显示当前图片 rel_path，最多 2 行，悬停完整路径

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

## 板块规范

- 组件 `PascalCase.vue`，scoped SCSS
- Store Composition API `defineStore`
- API 统一走 `api/` 模块，禁止组件内直接 axios
- Props 显式类型，不用 `any`
- `camelCase`（变量/函数），`PascalCase`（组件/类型），UTF-8
- 删除操作需 `ElMessageBox.confirm` 二次确认
- Element Plus 已配置中文 locale（zhCN）
- 多处重复的代码立即抽取到 composables/ 或 utils/
