# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库工作时提供指引。

## 常用命令

依赖管理用 **uv**（`pyproject.toml` 里配置了清华镜像源）：

- `uv sync` — 按 `uv.lock` 安装依赖
- `python run.py` — 启动开发服务（host/port/reload 均取自 `settings`）
- `python build_offline.py` — 构建 Windows 离线部署包（见下文「离线部署」）
- `bash build_linux.sh` — 用 Docker 构建 Linux 离线部署包
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
- **注册 IP**：`_register_ip()` 优先读 `NACOS_REGISTER_IP`（容器/多网卡环境必须显式配成外部可达 IP），留空才自动探测；探测结果存 `app.state.nacos_ip`，注销必须用同一个。
- **端口单一来源**：监听端口和注册端口都必须是 `settings.APP_PORT`。启动一律走 `python run.py`（或等效地不传 `--port` 的 uvicorn 调用），**禁止在命令行/部署脚本里硬编码端口**，否则注册信息与实际监听不一致。
- **单进程运行**：不要用 uvicorn `--workers > 1`。多 worker 会重复注册同一个 `IP:端口` 实例、生命周期互相打架；扩容量靠多跑进程/容器，由 Nacos 做负载均衡和故障摘除。
- **统一返回体**：JSON 接口一律返回 `HttpResult.ok(...)` / `HttpResult.fail(...)`（`app/models/response.py`）。`main.py` 有全局异常处理器，未捕获异常兜底为 `HttpResult` 500。
- **日志**：用标准 `logging`（`main.py` 里 basicConfig），不要 `print`。
- `app/api/`、`app/services/` 目前是空包，新增路由建议在 `api/` 下用 APIRouter 组织，在 `main.py` 挂载。

## 路由分层

`main.py` 只做装配（建 app、挂静态目录、异常处理、include 路由），**不写任何路由**：

- **页面**（返回 HTML）→ `app/pages.py`
- **JSON 接口**（返回 `HttpResult`）→ `app/api/` 下按领域拆模块，统一在 `app/api/router.py` 汇总 include
- **系统路由**（`/alive`、`/favicon.ico`）→ `app/api/system.py`，路径必须保持稳定（外部监控/探针依赖），不加业务前缀
- 路由层只收参、调 `services/`、包返回体，不写业务逻辑

## 登录鉴权

单账号（`AUTH_USERNAME`/`AUTH_PASSWORD` 走 `.env`），HMAC 无状态 token，**不需要 Redis**，多机实例可独立验签。

- 中间件在 `app/core/middleware.py`：`/alive`、`/static`、`/login`、`/api/auth/login` 放行；未登录时**页面 302 到 /login、API 返回 401 HttpResult**
- token 签发/校验在 `app/core/security.py`；Cookie（HttpOnly）和 `Authorization: Bearer` 两种携带方式都认
- **`AUTH_SECRET_KEY` 多机部署必须显式配置且各实例一致**，留空则每次启动随机生成（会互踢，有启动告警）
- 无状态 token 无法主动吊销，靠 `AUTH_TOKEN_TTL` 兜底；需要"立即踢人"时再加黑名单
- **未来 API-Key**：在 middleware.py 的 `_CREDENTIAL_CHECKERS` 列表里追加一个校验函数即可，管道和下游零改动

## 前端 UI

路线：**Jinja2 服务端渲染 + Tailwind v4 浏览器版 + daisyUI 5**，全部静态资源本地化（内网无外网，不用 CDN），不引入 Node 构建链。

- `app/static/vendor/` 放第三方库整文件（升级就整文件替换），自有代码在 `css/`、`js/`
- 所有页面继承 `templates/layouts/base.html`；**加载顺序不能乱**：daisyui.css → daisyui-themes.css → tailwind.browser.js
- 主题用 `<html data-theme>` + localStorage，切换器在 base.html 导航栏；主题必须在样式加载前应用（head 顶部内联脚本），否则刷新闪主题
- Tailwind 浏览器版是开发向的（每页实时编译）；以后要优化首屏，换 Tailwind standalone CLI 构建期出 CSS，仍不需要 Node

## 离线部署（build_offline.py）

目标机零安装、无外网：包 = 独立解释器 + 已装好的依赖 + 代码 + `.env`（由 `.env.example` 复制生成）。Windows 包本机直出，Linux 包用 Docker（`python:3.12-slim` 容器跑同一份脚本，产出的 wheel 自然是 Linux 版）。

关键设计（都是踩过的坑，勿回退）：

- **不搬运 .venv**（pyvenv.cfg 绑死构建机路径），而是拷贝 `sys.base_prefix` 指向的独立解释器，依赖直接装进它的 site-packages
- 删除解释器里的 `EXTERNALLY-MANAGED` 标记，否则 pip 拒绝安装
- `alibabacloud-*` 系列依赖只有 sdist，必须先 `pip wheel` 转 wheel 才能 `--no-index` 离线安装
- 安装用 `--no-hashes` 的 requirements（自建 wheel 与 sdist 哈希对不上）；完整性由 wheel 构建期的 hash 校验保证
- 启动脚本统一跑 `run.py`，端口只认 `.env`；Linux 包基于 Debian 12 运行时，目标机需兼容的 glibc
