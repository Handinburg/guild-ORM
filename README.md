# guild-ORM

一个使用 FastAPI、SQLAlchemy ORM、SQLite、Pydantic 和 JWT 的冒险者工会后端。

当前 V1 使用 Alembic 创建和更新数据库结构。默认数据库文件是项目根目录下的 `guild_alembic_v1.db`；该文件已被 Git 忽略。

## 环境要求

- Windows PowerShell
- Python 3.14（当前验证环境为 Python 3.14.4）

下面的命令都应在项目根目录 `guild-ORM` 中执行。

## 1. 创建并激活虚拟环境

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 阻止执行激活脚本，可仅对当前终端临时放行，然后再次激活：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

确认当前终端使用的是虚拟环境中的 Python：

```powershell
python --version
python -m pip --version
```

## 2. 安装依赖

```powershell
python -m pip install -r requirements.txt
```

`pwdlib[argon2]` 会安装密码哈希所需的 Argon2 支持；不要改成明文密码或仅安装不带 Argon2 支持的密码库。

## 3. 配置 JWT 密钥

先复制示例配置：

```powershell
Copy-Item .env.example .env
```

生成随机密钥，并写入本地 `.env`：

```powershell
$jwtSecret = python -c "import secrets; print(secrets.token_urlsafe(48))"
"JWT_SECRET_KEY=$jwtSecret" | Out-File -FilePath .env -Encoding ascii
```

`.env` 已被 Git 忽略。不要提交真实密钥，也不要把 `.env.example` 中的空值直接用于运行。

## 4. 使用 Alembic 建表

```powershell
alembic upgrade head
```

该命令会按照迁移文件创建或升级 `guild_alembic_v1.db`。以后模型结构发生变化时，应继续通过 Alembic 迁移，不要用 `create_all()` 代替正式迁移。

检查当前迁移版本：

```powershell
alembic current
```

## 5. 启动 FastAPI

```powershell
python -m uvicorn main:app --reload
```

启动后可访问：

- API：<http://127.0.0.1:8000>
- Swagger 文档：<http://127.0.0.1:8000/docs>

## 6. 注册第一个账户

保持服务运行，另开一个 PowerShell 窗口，进入项目目录并激活同一个虚拟环境，然后执行：

```powershell
$registerBody = @{
    username = "guildboss"
    adventurer_name = "会长"
    password = "请换成自己的强密码"
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8000/users/register" `
    -ContentType "application/json" `
    -Body $registerBody
```

注册接口始终创建普通用户，不能通过请求把自己设置为管理员。

## 7. 设置首位管理员

确认上一步注册成功后，在项目根目录运行：

```powershell
python first_admin.py
```

脚本会提示输入登录用户名。输入刚才注册的 `guildboss`；它只会把已经存在的用户设置为管理员，不会创建用户，也不会修改密码。

## 8. 运行测试

```powershell
python -m pytest -q
```

测试使用独立的内存 SQLite 数据库，不会读写 `guild_alembic_v1.db`。

## 常用命令

停止服务：在运行 Uvicorn 的终端按 `Ctrl+C`。

退出虚拟环境：

```powershell
deactivate
```

如果只想把 Alembic 迁移验证到一个临时数据库，可以在当前 PowerShell 会话中临时覆盖目标地址：

```powershell
$env:ALEMBIC_DATABASE_URL = "sqlite:///./temporary_migration_check.db"
alembic upgrade head
Remove-Item Env:ALEMBIC_DATABASE_URL
```

验证结束后可删除 `temporary_migration_check.db`。不要把测试数据库提交到 Git。
