#!/usr/bin/env bash
# 构建 Docker 镜像并导出离线分发包（在线构建，离线分发）
# 用法: bash build_docker.sh
# 本地与 Jenkins（DooD）通用：docker build 上下文由客户端打包发送，不涉及宿主机路径
set -euo pipefail
cd "$(dirname "$0")"

APP=$(grep -m1 '^name' pyproject.toml | cut -d'"' -f2)
VER=$(grep -m1 '^version' pyproject.toml | cut -d'"' -f2)
IMAGE="$APP:$VER"

echo "🔨 构建镜像 $IMAGE ..."
docker build -t "$IMAGE" -t "$APP:latest" .

echo "📦 导出离线包..."
mkdir -p dist
docker save "$IMAGE" | gzip > "dist/$APP-$VER-docker.tar.gz"

echo "✅ 完成"
echo "  镜像: $IMAGE（另附 :latest）"
echo "  离线包: dist/$APP-$VER-docker.tar.gz"
echo ""
echo "目标机使用："
echo "  gunzip -c $APP-$VER-docker.tar.gz | docker load"
echo "  docker compose up -d     # 或参考下方 docker run："
echo "  docker run -d --name $APP --env-file .env -e NACOS_REGISTER_IP=<宿主机IP> \\"
echo "    -p <端口>:<端口> -v /opt/$APP/data:/app/data $IMAGE"
