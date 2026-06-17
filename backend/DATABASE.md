# 数据库 Schema

> MySQL `zigaa_platform` utf8mb4 | 主键 UUID String(36) | 时间 String(32) ISO
> 核心原则：数据库只做台账记录（路径、数量、错误报告），绝不存实体文件
> 架构流程见 [ARCHITECTURE.md](./ARCHITECTURE.md)

## MySQL 配置

| 配置项 | 值 |
|--------|------|
| 主机 | 127.0.0.1 |
| 端口 | 3306 |
| 数据库 | zigaa_platform |
| 字符集 | utf8mb4 |
| 用户 | zigaa / zigaa123 |

`.env` 通过 `DB_HOST`/`DB_PORT`/`DB_USER`/`DB_PASSWORD`/`DB_NAME` 拼接连接串。

### 初始化

```sql
CREATE DATABASE zigaa_platform CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'zigaa'@'%' IDENTIFIED BY 'zigaa123';
GRANT ALL PRIVILEGES ON zigaa_platform.* TO 'zigaa'@'%';
FLUSH PRIVILEGES;
```

### 连接池

```python
engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20, pool_pre_ping=True, pool_recycle=3600)
```

## ER 关系

```
users (1) ────< (N) projects
                 │
                 ├───< (N) model_info
                         ├───< (1-5) data_packages
                           resource_type: good / defect / test / template / parameter
```

全部 `cascade="all, delete-orphan"` 级联删除。

## 表结构

### users

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | VARCHAR(36) | PK, uuid4() | |
| username | VARCHAR(100) | UNIQUE, NOT NULL | |
| password_hash | VARCHAR(255) | NOT NULL | bcrypt |
| role | VARCHAR(20) | NOT NULL, DEFAULT 'user' | user / advanced / admin |
| created_at | VARCHAR(32) | DEFAULT now_iso | UTC ISO |
| uploaded_at | VARCHAR(32) | DEFAULT now_iso | UTC ISO |

### projects

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | VARCHAR(36) | PK, uuid4() | |
| name | VARCHAR(200) | NOT NULL | |
| description | TEXT | DEFAULT '' | |
| owner_id | VARCHAR(36) | FK users.id CASCADE, NOT NULL | |
| created_at | VARCHAR(32) | DEFAULT now_iso | |
| uploaded_at | VARCHAR(32) | DEFAULT now_iso | |

Index: `idx_projects_owner_id(owner_id)`

### model_info

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | VARCHAR(36) | PK, uuid4() | |
| name | VARCHAR(200) | NOT NULL | |
| description | TEXT | DEFAULT '' | |
| project_id | VARCHAR(36) | FK projects.id CASCADE, NOT NULL | |
| status | JSON | nullable | 三维度状态 JSON（见下方） |
| upload_path | VARCHAR(500) | nullable | 本地训练传输路径 |
| created_at | VARCHAR(32) | DEFAULT now_iso | |
| uploaded_at | VARCHAR(32) | DEFAULT now_iso | |

Index: `idx_model_info_project_id(project_id)`

**status JSON** (单列三维度):

```json
{
  "file_status": {"status": "idle"},       // idle → ready → invalid
  "training_status": {"status": "idle"},   // idle → training → success/failure + error
  "test_status": {"status": "idle"}        // idle → generating → success/failure + error
}
```

状态流转见 [ARCHITECTURE.md](./ARCHITECTURE.md)。

### data_packages

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | VARCHAR(36) | PK, uuid4() | |
| model_id | VARCHAR(36) | FK model_info.id CASCADE, NOT NULL | |
| resource_type | VARCHAR(20) | NOT NULL | good / defect / test / template / parameter |
| file_path | VARCHAR(500) | NOT NULL | |
| passed_count | INT | DEFAULT 0 | |
| failed_count | INT | DEFAULT 0 | |
| errors | JSON | DEFAULT `{}` | key=path，value={type, level?, message} |
| msgs   | JSON | DEFAULT `{}` | key=path，value={width, height, channels, category} |
| created_at | VARCHAR(32) | DEFAULT now_iso | |
| uploaded_at | VARCHAR(32) | DEFAULT now_iso | |

UniqueConstraint: `uq_model_resource(model_id, resource_type)`

parameter 资源的 passed/failed/errors 全为 0/空 dict。test/template 资源的 failed_count = 0。
errors 和 msgs 均为 dict，key 为图片相对路径。category 默认 undefined（none）。

## 索引

| 表 | 索引 | 字段 | 说明 |
|----|------|------|------|
| data_packages | UNIQUE | (model_id, resource_type) | 防止重复上传同类型 |
| model_info | INDEX | project_id | 查询项目下所有模型 |
| projects | INDEX | owner_id | 查询用户下所有项目 |
