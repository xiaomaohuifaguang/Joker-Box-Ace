"""构建离线部署包：python build_offline.py"""
import platform
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from app.config import settings

with open("pyproject.toml", "rb") as f:
    _project = tomllib.load(f)["project"]

APP_NAME = _project["name"]       # 与 pyproject.toml 保持单一来源
VERSION = _project["version"]
APP_PORT = settings.APP_PORT      # 启动脚本端口跟随配置，不再硬编码

IS_WIN = sys.platform == "win32"
PY_DIR = Path(sys.executable).parent.parent   # uv 管理的解释器根目录
DIST = Path("dist")
TAG = "windows" if IS_WIN else "linux"
PKG = DIST / f"{APP_NAME}-{VERSION}-{TAG}"

def main():
    if PKG.exists():
        shutil.rmtree(PKG)

    # 干净地重建依赖（保证按 lock 精确安装）
    subprocess.run([sys.executable, "-m", "uv", "sync", "--frozen", "--no-dev"],
                   check=True)

    PKG.mkdir(parents=True)
    print("📦 拷贝内置解释器...")
    shutil.copytree(PY_DIR, PKG / "runtime")

    print("📦 拷贝依赖与代码...")
    shutil.copytree(".venv", PKG / ".venv")
    shutil.copytree("app", PKG / "app")
    for f in ("pyproject.toml",):
        shutil.copy2(f, PKG / f)

    # ── 平台差异点 ─────────────────────────────
    py_exe_rel = (r"runtime\python.exe" if IS_WIN
                  else "runtime/bin/python")
    venv_py = (r".venv\Scripts\python.exe" if IS_WIN
               else ".venv/bin/python")

    write_start_script(PKG, py_exe_rel, venv_py)
    write_readme(PKG, py_exe_rel)

    # 收尾压缩
    print(f"🗜️ 压缩中...")
    out = compress(PKG)
    print(f"✅ 打包完成 → {out}")

def write_start_script(PKG, py_exe_rel, venv_py):
    """生成目标机一键启动脚本（在目标平台上直接可执行）"""
    if IS_WIN:
        (PKG / "start.bat").write_text(
            f'@echo off\r\n'
            f'cd /d %~dp0\r\n'
            f'{venv_py} -m uvicorn app.main:app --host 0.0.0.0 --port {APP_PORT} --workers 2\r\n',
            encoding="utf-8")
    else:
        sh = PKG / "start.sh"
        sh.write_text(
            f'#!/usr/bin/env bash\n'
            f'cd "$(dirname "$0")"\n'
            f'{venv_py} -m uvicorn app.main:app --host 0.0.0.0 --port {APP_PORT} --workers 2\n')
        import os; os.chmod(sh, 0o755)

def write_readme(PKG, py_exe_rel):
    note = (
        f"目标机零安装运行说明\n"
        f"===================\n"
        f"1. 解压本目录到任意位置\n"
        f"2. 运行 {'start.bat' if IS_WIN else './start.sh'} 即可启动服务\n\n"
        f"解释器位置: {py_exe_rel}\n"
        f"注意: 本包为 {TAG} 平台专用，不可跨平台使用。\n")
    (PKG / "README-部署.txt").write_text(note, encoding="utf-8")

def compress(PKG: Path) -> Path:
    if IS_WIN:
        out = PKG.with_suffix(".zip")
        shutil.make_archive(str(PKG), "zip", root_dir=DIST, base_dir=PKG.name)
        return out
    else:
        out = DIST / f"{PKG.name}.tar.gz"
        subprocess.run(["tar", "-czf", str(out), "-C", str(DIST), PKG.name], check=True)
        return out

if __name__ == "__main__":
    main()
