# 视觉设计

> 基于 Element Plus 2.14 默认主题的精细化定制
> 设计令牌在 `src/styles/variables.scss` 以 CSS 变量定义
> 布局与组件架构见 [ARCHITECTURE.md](./ARCHITECTURE.md)

## 设计令牌

### 颜色

| 令牌 | 色值 | 用途 |
|------|------|------|
| `--color-primary` | `#409eff` | 主按钮、链接、活跃状态 |
| `--color-primary-dark` | `#337ecc` | 主色 hover |
| `--color-success` | `#67c23a` | 成功、可用 |
| `--color-warning` | `#e6a23c` | 警告、训练中、高级用户标签 |
| `--color-danger` | `#f56c6c` | 错误、失败、删除、管理员标签 |
| `--color-info` | `#909399` | 次要信息、普通用户标签 |

### 文字

| 令牌 | 色值 | 用途 |
|------|------|------|
| `--text-primary` | `#303133` | 主要文字 |
| `--text-regular` | `#606266` | 正文 |
| `--text-secondary` | `#909399` | 次要、提示 |
| `--text-placeholder` | `#c0c4cc` | 占位 |

### 背景 / 边框

| 令牌 | 色值 | 用途 |
|------|------|------|
| `--bg-page` | `#f5f7fa` | 页面背景 |
| `--bg-card` | `#ffffff` | 卡片、面板 |
| `--bg-hover` | `#f5f7fa` | 悬浮高亮 |
| `--border-color` | `#dcdfe6` | 标准边框 |
| `--border-light` | `#e4e7ed` | 浅色边框 |

### 间距

| 令牌 | 值 |
|------|-----|
| `--spacing-xs` | `4px` |
| `--spacing-sm` | `8px` |
| `--spacing-md` | `16px` |
| `--spacing-lg` | `24px` |
| `--spacing-xl` | `32px` |

### 圆角 / 阴影

| 令牌 | 值 |
|------|-----|
| `--radius-sm` | `4px` |
| `--radius-md` | `8px` |
| `--radius-lg` | `12px` |
| `--shadow-sm` | `0 2px 4px rgba(0,0,0,0.05)` |
| `--shadow-md` | `0 2px 12px rgba(0,0,0,0.1)` |
| `--shadow-lg` | `0 4px 20px rgba(0,0,0,0.15)` |

## 布局

### 导航栏

`NavBar.vue` 固定顶部 56px，白色背景 `--shadow-sm`。Logo 左、链接中（absolute 居中）、用户区右。

### 页面内容

```scss
.page-content {
  padding: 80px 24px 24px;
  max-width: 1200px;
  margin: 0 auto;
}
```

### 项目页面

```
┌──────────┬─────────────────────────┐
│ 侧边栏   │      主内容区            │
│ 260px    │   grid auto-fill 280px  │
└──────────┴─────────────────────────┘
```

### 标注编辑器

```
┌──────────────────────────────┬──────────┐
│ 画布区 (flex:1, #1A1A2E)      │ 侧栏 280px│
│ 工具栏绝对定位顶部             │ 目录树    │
│ 底部状态栏绝对定位             │           │
└──────────────────────────────┴──────────┘
```

### 登录页

全屏渐变 `#667EEA → #764BA2`，卡片 400px `--radius-lg` `--shadow-lg`。

## 按钮规范

所有按钮统一 `<el-button>`，通过 `type` / `link` / `text` 组合。

| 场景 | 写法 | 效果 |
|------|------|------|
| 主要操作 | `type="primary"` | 蓝色填充 |
| 危险操作 | `type="danger"` | 红色填充 |
| 取消/关闭 | 默认 | 灰色边框 |
| 次要操作 | `type="primary" link` | 蓝色文字链接 |
| 文字操作 | `type="primary" text` | 蓝色文字 |

### Loading 交互

- 500ms 延迟显示
- `:loading="isLoading(key)"` 每个按钮独立 key
- 不加 `:loading-text`，保留原按钮文字
- `hasLoading()` 用于 `:disabled` 互斥兄弟按钮

## 卡片

```scss
.model-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.2s;
  cursor: pointer;

  &:hover { box-shadow: var(--shadow-md); }
}
```

网格: `grid-template-columns: repeat(auto-fit, minmax(365px, 1fr))`（卡片 `min-width: 365px`）

## 反馈组件

| 场景 | 组件 | 配置 |
|------|------|------|
| 操作成功 | `ElMessage.success` | duration 2000ms |
| 操作失败 | `ElMessage.error` | duration 3000ms |
| 加载状态 | `v-loading` | 全屏或区块 |
| 空状态 | `el-empty` | 页面级 200px / 行级 60px |
| 删除确认 | `ElMessageBox.confirm` | 重要实体用对话框 |

## 规范

- 样式不内联，组件只引用 CSS 变量和全局 class
- 卡片统一用 CSS 变量组合
- `<style scoped>` 只加必要修饰类，不改全局样式
- SCSS 文件：`styles/main.scss`（入口，导入 variables）+ `styles/variables.scss`（CSS 变量设计令牌）
