# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库工作时提供指引。

## 常用命令

依赖管理用 **uv**（`pyproject.toml` 里配置了清华镜像源）：

- `uv sync` — 按 `uv.lock` 安装依赖
- `python run.py` — 启动开发服务（host/port/reload 均取自 `settings`）
- `test_main.http` — JetBrains HTTP Client 手工测试文件（端口跟随 `.env`）

目前未配置测试框架和 linter。

## 配置约定

所有配置只能走 `app/config.py` 里的单例：`from app.config import settings`。
基于 `pydantic-settings`，读取仓库根目录的 `.env`（路径已钉死，与启动目录无关），优先级：**真实环境变量 > .env > 代码默认值**，`extra="ignore"` 允许 `.env` 存在多余键。

- `.env` 含真实 Nacos 凭据，已被 gitignore，**绝不能提交**
- 新增配置项时同步更新 `.env.example`（只放 key 不放真实值）

## 架构要点

FastAPI + Nacos 服务发现的微服务骨架，跨文件才能看清的设计如下：

- **生命周期总入口是 `app/nacos_registry.py` 的 `lifespan()`**，`NACOS_ENABLED` 开关在这里生效。新增生命周期资源（数据库连接池等）必须嵌套进这个函数，不要直接改 `main.py` 的 `lifespan=` 参数。
- **注册容错设计**：注册在后台 asyncio 任务里跑，不阻塞启动；失败重试 3 次后只记日志，服务继续运行；注册时的 IP 存 `app.state.nacos_ip`，注销必须用同一个 IP。
- **服务名**：注册名走 `NACOS_SERVICE_NAME`，留空回退 `APP_NAME`（见 `_service_name()`），不要在别处拼接。
- **统一返回体**：JSON 接口一律返回 `HttpResult.ok(...)` / `HttpResult.fail(...)`（`app/models/response.py`）。`main.py` 有全局异常处理器，未捕获异常兜底为 `HttpResult` 500。
- **日志**：用标准 `logging`（`main.py` 里 basicConfig），不要 `print`。
- `app/api/`、`app/services/` 目前是空包，新增路由建议在 `api/` 下用 APIRouter 组织，在 `main.py` 挂载。
