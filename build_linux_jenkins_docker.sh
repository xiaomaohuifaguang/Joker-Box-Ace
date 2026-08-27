#!/usr/bin/env bash
# Jenkins 专用：构建 Linux 离线包
# 场景：Jenkins 跑在 Docker 容器里，docker CLI 通过挂载的 /var/run/docker.sock 调宿主机 daemon，
#       因此 -v 必须传【宿主机】路径（Jenkins 容器内的 $WORKSPACE 路径宿主机不认识）。
# 用法: bash build_linux_jenkins_docker.sh
# 宿主路径默认下方值，可在 Jenkins 任务环境变量里用 HOST_WORKSPACE 覆盖
set -euo pipefail
cd "$(dirname "$0")"

HOST_WORKSPACE="${HOST_WORKSPACE:-/app/jenkins_home/workspace/Joker-Box-Ace/project}"

docker run --rm -v "$HOST_WORKSPACE":/src -w /src python:3.12-slim bash -c "
  pip install -q uv -i https://pypi.tuna.tsinghua.edu.cn/simple &&
  python build_offline.py &&
  chown -R 1000:1000 dist
"

echo "✅ Linux 包构建完成，见 dist/ 目录"
