"""构建离线部署包（目标机零安装、无外网、解压即用）

用法：
    Windows 包:  python build_offline.py
    Linux 包:    bash build_linux.sh        # 用 Docker 跑本脚本，产出 Linux 包

设计要点（踩坑后的结论，勿随意改）：
    1. 不搬运 .venv —— venv 的 pyvenv.cfg 绑死构建机绝对路径，不可移植。
       改为拷贝 python-build-standalone 独立解释器（uv 管理的那份，天生可搬），
       依赖直接装进它的 site-packages。
    2. 删掉解释器里的 EXTERNALLY-MANAGED 标记，否则 pip 拒绝安装（PEP 668）。
    3. 部分依赖（alibabacloud-* 系列）只有 sdist 没有 wheel，pip install --no-index
       无法离线构建，所以先用 pip wheel 统一转成 wheel 再离线安装。
    4. 安装用的 requirements 不能带 hash —— 自建的 wheel 与 sdist 哈希对不上。
       完整性由 wheel 构建步骤的 hash 校验保证。
    5. 启动脚本统一跑 run.py，端口等配置只认 .env，不在脚本里硬编码。
"""
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
PYPI_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"

IS_WIN = sys.platform == "win32"
TAG = "windows" if IS_WIN else "linux"

# Windows 控制台默认 GBK，打不了 emoji
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def run(cmd: list[str], **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def write_linux_scripts(pkg: Path, py_cmd: str):
    """生成 Linux 运维脚本：start/stop/restart/status + systemd 单元模板"""
    scripts = {
        # 默认后台启动（对标 Tomcat startup.sh）；-f 前台模式供调试和 systemd 使用
        "start.sh": f"""#!/usr/bin/env bash
# 启动服务。用法: ./start.sh          后台启动（默认）
#                ./start.sh -f       前台启动（调试用，Ctrl+C 停止）
cd "$(dirname "$0")"
PID_FILE=app.pid
LOG_FILE=app.log

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "已在运行 (PID $(cat "$PID_FILE"))"; exit 1
fi

if [ "${{1:-}}" = "-f" ] || [ "${{1:-}}" = "--foreground" ]; then
  exec {py_cmd} run.py
fi

nohup {py_cmd} run.py >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
echo "已启动 (PID $(cat "$PID_FILE"))，日志: $LOG_FILE"
""",
        # 优雅停止优先：TERM 让 lifespan 走完（Nacos 注销靠它），超时再 KILL
        "stop.sh": """#!/usr/bin/env bash
# 停止服务（先优雅关闭，15s 超时后强制）
cd "$(dirname "$0")"
PID_FILE=app.pid

if [ ! -f "$PID_FILE" ]; then
  echo "未运行（无 $PID_FILE）"; exit 0
fi
PID=$(cat "$PID_FILE")
if ! kill -0 "$PID" 2>/dev/null; then
  echo "进程已不存在，清理 $PID_FILE"; rm -f "$PID_FILE"; exit 0
fi

kill "$PID"
for _ in $(seq 1 15); do
  kill -0 "$PID" 2>/dev/null || break
  sleep 1
done
if kill -0 "$PID" 2>/dev/null; then
  echo "优雅停止超时，强制结束 (kill -9)"; kill -9 "$PID"
fi
rm -f "$PID_FILE"
echo "已停止 (PID $PID)"
""",
        "restart.sh": """#!/usr/bin/env bash
cd "$(dirname "$0")"
./stop.sh && ./start.sh
""",
        # 两层检查：PID 存活 = 进程在；/alive 通 = 服务真活着
        "status.sh": """#!/usr/bin/env bash
cd "$(dirname "$0")"
PID_FILE=app.pid

if [ ! -f "$PID_FILE" ] || ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "未运行"; exit 1
fi
PID=$(cat "$PID_FILE")
PORT=$(grep -E '^APP_PORT=' .env 2>/dev/null | cut -d= -f2)
PORT=${PORT:-8000}
HTTP=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "http://127.0.0.1:$PORT/alive")
echo "进程运行中 (PID $PID)，/alive 探测: HTTP ${HTTP:-不可达}"
[ "$HTTP" = "200" ]
""",
        # systemd 单元模板：有 systemd 的服务器推荐用这个托管
        "app.service": f"""[Unit]
Description=Joker Box Ace
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
# 部署时把 /opt/joker-box-ace 改成实际解压目录
WorkingDirectory=/opt/joker-box-ace
ExecStart=/opt/joker-box-ace/{py_cmd} run.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
""",
    }
    for name, content in scripts.items():
        f = pkg / name
        f.write_text(content, encoding="utf-8", newline="\n")
        if name.endswith(".sh"):
            f.chmod(0o755)


def main():
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    app_name, version = meta["name"], meta["version"]
    pkg = DIST / f"{app_name}-{version}-{TAG}"

    if pkg.exists():
        shutil.rmtree(pkg)
    pkg.mkdir(parents=True)

    # ── 1. 拷贝独立解释器 ──────────────────────────────────────
    # sys._base_executable / sys.base_prefix：即使本脚本跑在 venv 里也能定位到
    # 真正的底层解释器（uv 管理的 standalone 或容器里的系统 Python）
    base_exe = Path(getattr(sys, "_base_executable", sys.executable)).resolve()
    base_prefix = Path(sys.base_prefix).resolve()
    py_rel = base_exe.relative_to(base_prefix)      # 解释器在 runtime 内的相对路径
    print(f"📦 拷贝独立解释器: {base_prefix}")
    shutil.copytree(base_prefix, pkg / "runtime",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    runtime_py = pkg / "runtime" / py_rel

    # PEP 668 标记会让 pip 拒绝往这个解释器里装包，删掉（这是我们自己的拷贝）
    for marker in (pkg / "runtime").rglob("EXTERNALLY-MANAGED"):
        marker.unlink()

    # ── 2. 依赖全部转成 wheel，再离线装进 runtime ───────────────
    reqs_locked = pkg / "requirements-locked.txt"    # 带 hash，用于构建期校验
    reqs_plain = pkg / "requirements.txt"            # 不带 hash，用于安装
    print("📦 导出锁定依赖...")
    run(["uv", "export", "--frozen", "--no-dev", "-o", reqs_locked], cwd=ROOT)
    run(["uv", "export", "--frozen", "--no-dev", "--no-hashes", "-o", reqs_plain], cwd=ROOT)

    wheels = pkg / "_wheels_tmp"
    print("📦 下载/构建全部依赖为 wheel（alibabacloud 等 sdist 在此转 wheel）...")
    run([runtime_py, "-m", "pip", "wheel", "-r", reqs_locked,
         "-w", wheels, "-i", PYPI_MIRROR, "-q"])

    print("📦 离线安装依赖到 runtime...")
    run([runtime_py, "-m", "pip", "install", "--no-index",
         f"--find-links={wheels}", "-r", reqs_plain, "-q", "--no-warn-script-location"])
    shutil.rmtree(wheels)
    reqs_locked.unlink()
    reqs_plain.unlink()

    # ── 3. 拷代码与配置模板 ────────────────────────────────────
    print("📦 拷贝代码与配置...")
    shutil.copytree(ROOT / "app", pkg / "app",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(ROOT / "run.py", pkg / "run.py")
    shutil.copy2(ROOT / ".env.example", pkg / ".env.example")
    # 生成一份默认可跑的 .env（内容为占位值），运维只需按需修改
    shutil.copy2(ROOT / ".env.example", pkg / ".env")

    # ── 4. 启动脚本（统一跑 run.py，端口只认 .env）─────────────
    py_cmd = str(Path("runtime") / py_rel)
    if IS_WIN:
        (pkg / "start.bat").write_text(
            "@echo off\r\ncd /d %~dp0\r\n"
            f"{py_cmd} run.py\r\npause\r\n",
            encoding="utf-8")
    else:
        write_linux_scripts(pkg, py_cmd)

    (pkg / "README-部署.txt").write_text(f"""\
{app_name} v{version} 离线部署包（{TAG} 专用，不可跨平台）
=====================================================
1. 解压到任意位置（路径随意，无依赖）
2. 按需修改 .env（由 .env.example 复制生成）：
   - APP_PORT            服务端口
   - NACOS_SERVER_ADDR   Nacos 地址及账号密码
   - NACOS_REGISTER_IP   多网卡/需要注册特定 IP 时显式填写，留空自动探测
3. 启动：
   Windows: 双击 start.bat
   Linux:   ./start.sh           后台启动（默认；日志 app.log，PID app.pid）
            ./start.sh -f        前台启动（调试用）
            ./stop.sh            停止（优雅关闭，超时强杀）
            ./restart.sh         重启
            ./status.sh          查看状态（进程 + /alive 健康检查）
   有 systemd 的服务器推荐：参考 app.service 用 systemctl 托管
4. 验证：curl http://127.0.0.1:<APP_PORT>/alive

守护进程建议：Windows 用 NSSM 注册为服务；Linux 优先 systemd（app.service）。
""", encoding="utf-8")

    # ── 5. 压缩 ────────────────────────────────────────────────
    print("🗜️ 压缩中...")
    if IS_WIN:
        out = pkg.with_suffix(".zip")
        shutil.make_archive(str(pkg), "zip", root_dir=DIST, base_dir=pkg.name)
    else:
        out = DIST / f"{pkg.name}.tar.gz"
        run(["tar", "-czf", out, "-C", DIST, pkg.name])
    print(f"✅ 打包完成 → {out}")


if __name__ == "__main__":
    main()
