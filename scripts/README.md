# 数据库脚本说明

本目录包含 `hna` 数据库的初始化与数据导入脚本。

## 文件清单

| 文件 | 说明 |
|------|------|
| `create_tables.sql` | 创建所有业务表与后台管理表 |
| `init_data.sql` | 插入默认角色、权限、用户、系统配置、功能开关 |
| `init_database.py` | 一键执行建表 + 初始数据（推荐首次使用） |
| `import_data.py` | 将 `data/` 目录下的 Excel 文件导入到 MySQL |
| `build_knowledge_graph.py` | 从已有数据构建 Neo4j 知识图谱（保留脚本） |

## 前置要求

1. MySQL 已启动，且已创建数据库 `hna`（脚本也会自动创建）。
2. 项目根目录 `.env` 文件已正确配置 MySQL 连接信息：
   ```env
   MYSQL_HOST=localhost
   MYSQL_PORT=3306
   MYSQL_USER=root
   MYSQL_PASSWORD=你的密码
   MYSQL_DATABASE=hna
   ```
3. Python 依赖已安装：
   ```bash
   pip install pymysql sqlalchemy python-dotenv pandas openpyxl bcrypt
   ```

## 使用步骤

### 1. 初始化数据库（建表 + 默认数据）

```bash
python scripts/init_database.py
```

如果 `.env` 中的密码不正确，可通过命令行传入：

```bash
python scripts/init_database.py --mysql-password 你的密码
```

仅建表：

```bash
python scripts/init_database.py --create-only
```

仅重新插入初始数据：

```bash
python scripts/init_database.py --seed-only
```

### 2. 导入业务数据

将 `data/` 目录下的 Excel 文件导入 MySQL：

```bash
python scripts/import_data.py --clear --batch-size 2000
```

参数说明：
- `--clear`：导入前清空业务表（首次导入建议加上）。
- `--batch-size`：每批插入行数，默认 2000。医嘱表较大，可适当增大以提升速度。
- `--mysql-password`：覆盖 `.env` 中的 MySQL 密码。

完整示例：

```bash
python scripts/import_data.py --mysql-password 你的密码 --clear --batch-size 5000
```

导入成功后，会从入院/出院数据自动重建 `patients` 和 `visits` 表。

## 默认账号

执行 `init_data.sql` 后会生成以下账号：

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 系统管理员 |
| doctor | doctor123 | 医生 |

**生产环境请务必修改默认密码。**

## 后台权限模型

- `roles`：角色表（admin / department_manager / doctor / viewer）
- `permissions`：权限表
- `role_permissions`：角色-权限多对多关联
- `user_roles`：用户-角色多对多关联

新增用户时，先插入 `users`，再在 `user_roles` 中绑定角色即可。
