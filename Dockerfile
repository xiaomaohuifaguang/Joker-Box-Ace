# Joker Box Ace 镜像（python:3.12-slim 与 build_linux.sh 同源，行为已验证）
FROM python:3.12-slim

# 时区：项目时间戳是应用侧本地时间（见 CLAUDE.md），容器默认 UTC 必须修正；
# slim 镜像不带 tzdata，只设 ENV 无效
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*
ENV TZ=Asia/Shanghai

WORKDIR /app

# 依赖按 uv.lock 精确锁定（pyproject.toml 里已配清华镜像源）
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv -i https://pypi.tuna.tsinghua.edu.cn/simple \
    && uv sync --frozen --no-dev --no-cache

COPY app ./app
COPY run.py ./

# 端口由 .env 的 APP_PORT 决定（默认 8000），此处仅为文档作用
EXPOSE 8000

# 单进程运行（多实例扩容靠多容器 + Nacos 负载均衡，见 CLAUDE.md）
CMD [".venv/bin/python", "run.py"]
