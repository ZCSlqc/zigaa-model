# Zigaa 大模型云平台 — 全局总纲

工业缺陷检测平台的数据管理 Web 应用。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + TypeScript + Element Plus + Konva + Pinia |
| 后端 | FastAPI + SQLAlchemy + MySQL + PyJWT + bcrypt + OpenCV |
| 包管理 | uv（后端）+ npm（前端） |

## 文档导航

| 文件 | 内容 |
|------|------|
| `README.md` | 安装与启动 |
| `DEPLOY.md` | 部署手册（零基础部署指南，含配置详解） |
| `PLAN.md` | 实施规划（已实现功能、后续迭代） |
| `backend/CLAUDE.md` | 后端核心约束 |
| `backend/ARCHITECTURE.md` | 后端整体架构与业务流程 |
| `backend/STRUCTURE.md` | 后端目录/ORM/API/services 索引 |
| `backend/DATABASE.md` | 数据库 schema |
| `frontend/CLAUDE.md` | 前端核心约束 |
| `frontend/ARCHITECTURE.md` | 前端整体架构与业务流程 |
| `frontend/STRUCTURE.md` | 前端目录/路由/Store/标注系统索引 |
| `frontend/STYLE.md` | 视觉设计令牌/布局/组件规范 |


## 全局约束

- 后端 `snake_case`，前端 `camelCase`/`PascalCase`（组件/类型），URL `kebab-case`，JSON `snake_case`
- 主键 UUID（String(36)），不用自增整数
- JWT Bearer Token 24h，角色 `user`/`advanced`/`admin`，401 → 清 localStorage → 跳转 /login
- 接口 RESTful，错误 `{ "detail": "..." }`，分页 `page`/`page_size`
- JWT_SECRET 必须 .env 设置，无 fallback
- **后端改前端不动** — 前端不写 mapper 适配层，唯一例外是展示层格式化
- 代码注释默认不写，仅 WHY 不直观时才加

## 启动

```bash
./init.sh    # 首次初始化
./start.sh   # 日常启动（后端 8111 + 前端 3111）
./stop.sh    # 停止
```

## 系统账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| zigaa | zigaa123 | admin |
| zigaatest | zigaa123 | user |

## 开发铁律

- 按 `PLAN.md` 执行，不再重复确认
- 同一时间只推进**唯一子模块**，闭环再进下一个
- 严禁批量读取源码，只读当前层级 CLAUDE.md
- 测试通过后直接 commit
- UI 修改必浏览器实测
