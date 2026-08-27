#!/usr/bin/env bash
# 在 Windows 开发机上用 Docker 构建 Linux 离线包（构建过程需要联网拉依赖，产出的包离线可用）
# 用法: bash build_linux.sh
set -euo pipefail
cd "$(dirname "$0")"

docker run --rm -v "$PWD":/src -w /src python:3.12-slim bash -c "
  pip install -q uv -i https://pypi.tuna.tsinghua.edu.cn/simple &&
  python build_offline.py
"

echo "✅ Linux 包构建完成，见 dist/ 目录"
