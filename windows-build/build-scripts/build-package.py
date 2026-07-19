"""Assemble the full Windows build tree.

Runs on Windows (host must have Python 3.11 x64 installed).
Produces build\\ProcessOpt\\  ready for Inno Setup.

Usage:
    python build-package.py

Prerequisites (place in windows-build\\downloads\\):
    - python-3.11.x-embed-amd64.zip
    - postgresql-15.x-x-windows-x64-binaries.zip
    - nats-server-v2.10.x-windows-amd64.zip
    - nssm-2.24.zip

Prerequisites (project state):
    - web\\dist\\ must already be built (cd web && npm run build)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WIN_BUILD = PROJECT_ROOT / "windows-build"
DOWNLOADS = WIN_BUILD / "downloads"
BUILD_DIR = WIN_BUILD / "build"
OUT_ROOT = BUILD_DIR / "ProcessOpt"

# Expected download filenames — update patterns if versions change
PYTHON_EMBED_GLOB = "python-3.11.*-embed-amd64.zip"
POSTGRES_GLOB = "postgresql-15.*-windows-x64-binaries.zip"
NATS_GLOB = "nats-server-v2.10.*-windows-amd64.zip"
NSSM_GLOB = "nssm-*.zip"


def find_one(pattern: str) -> Path:
    matches = list(DOWNLOADS.glob(pattern))
    if not matches:
        print(f"ERROR: not found in downloads/: {pattern}", file=sys.stderr)
        print(f"       See downloads/README.md for URLs.", file=sys.stderr)
        sys.exit(1)
    return matches[0]


def clean_build() -> None:
    print("=== Cleaning previous build ===")
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)


def extract_zip(zip_path: Path, dest: Path, strip_top: bool = False) -> None:
    """Extract zip to dest. If strip_top, remove the single top-level dir."""
    print(f"  Extracting {zip_path.name} → {dest.relative_to(BUILD_DIR)}")
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        if strip_top:
            names = zf.namelist()
            top = names[0].split("/")[0]
            for member in zf.infolist():
                if member.is_dir():
                    continue
                rel = Path(member.filename).relative_to(top)
                out_path = dest / rel
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(out_path, "wb") as dst_f:
                    shutil.copyfileobj(src, dst_f)
        else:
            zf.extractall(dest)


def setup_python(app_dir: Path) -> Path:
    """Extract embedded Python, enable site-packages, return python.exe path."""
    print("=== Setting up embedded Python ===")
    py_dir = app_dir / "python"
    extract_zip(find_one(PYTHON_EMBED_GLOB), py_dir)

    # Embedded Python by default disables `site` (import site is commented out).
    # We need to enable it so pip / site-packages work.
    pth_file = next(py_dir.glob("python3*._pth"))
    text = pth_file.read_text()
    if "#import site" in text:
        text = text.replace("#import site", "import site")
        pth_file.write_text(text)
        print(f"  Enabled site-packages in {pth_file.name}")

    python_exe = py_dir / "python.exe"
    print(f"  Python ready: {python_exe}")
    return python_exe


def install_pip(python_exe: Path) -> None:
    """Bootstrap pip in embedded Python via get-pip.py."""
    print("=== Installing pip into embedded Python ===")
    get_pip = DOWNLOADS / "get-pip.py"
    if not get_pip.exists():
        print(f"ERROR: {get_pip} missing.", file=sys.stderr)
        print(f"       Download from https://bootstrap.pypa.io/get-pip.py", file=sys.stderr)
        sys.exit(1)
    subprocess.run([str(python_exe), str(get_pip), "--no-warn-script-location"], check=True)


def install_dependencies(python_exe: Path) -> None:
    """Install all project dependencies into embedded Python's site-packages."""
    print("=== Installing project dependencies ===")
    subprocess.run(
        [
            str(python_exe), "-m", "pip", "install",
            "--no-warn-script-location",
            "--index-url", "https://pypi.tuna.tsinghua.edu.cn/simple",
            "--no-cache-dir",
            "-e", str(PROJECT_ROOT),  # install from pyproject.toml
        ],
        check=True,
    )
    # Uninstall process-opt itself — we'll ship .pyc separately, not as installed pkg
    subprocess.run(
        [str(python_exe), "-m", "pip", "uninstall", "-y", "process-opt"],
        check=False,
    )


def compile_and_copy_source(app_dir: Path) -> None:
    """Compile project src to .pyc and place under app/process_opt/."""
    print("=== Compiling project source to .pyc ===")
    src = PROJECT_ROOT / "src" / "process_opt"
    dst = app_dir / "process_opt"
    subprocess.run(
        [
            sys.executable,
            str(WIN_BUILD / "build-scripts" / "compile-pyc.py"),
            str(src), str(dst),
        ],
        check=True,
    )


def copy_static_assets(app_dir: Path) -> None:
    """Copy web/dist, db/migrations, .env template, VERSION."""
    print("=== Copying static assets ===")

    # Frontend
    web_dist = PROJECT_ROOT / "web" / "dist"
    if not web_dist.is_dir():
        print(f"ERROR: {web_dist} not found. Run `cd web && npm run build` first.", file=sys.stderr)
        sys.exit(1)
    shutil.copytree(web_dist, app_dir / "web" / "dist")
    print(f"  Copied web/dist ({sum(1 for _ in web_dist.rglob('*') if _.is_file())} files)")

    # DB migrations
    migrations = PROJECT_ROOT / "db" / "migrations"
    shutil.copytree(migrations, app_dir / "db" / "migrations")
    print(f"  Copied db/migrations ({len(list(migrations.glob('*.sql')))} SQL files)")

    # .env template
    (app_dir / ".env").write_text(ENV_TEMPLATE, encoding="utf-8")
    (app_dir / "VERSION").write_text("0.1.0\n", encoding="utf-8")


ENV_TEMPLATE = """# 工艺参数在线分析与调优系统 — 环境变量
# 安装后可编辑此文件调整配置，需重启服务生效

# ── LLM / Agent 配置 ──
AGENT_MODEL=deepseek-chat
AGENT_API_BASE=https://api.deepseek.com/v1
AGENT_API_KEY=your-api-key-here
# AGENT_TEMPERATURE=0.0

# ── 服务端口 ──
PROCESS_OPT_API_PORT=8000
PROCESS_OPT_GATEWAY_PORT=8001

# ── 数据库/消息队列（本地） ──
PROCESS_OPT_POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/process_opt
PROCESS_OPT_NATS_URL=nats://localhost:4222
PROCESS_OPT_GATEWAY_URL=http://localhost:8001
PROCESS_OPT_GATEWAY_API_KEY=change-me
"""


def setup_postgres(root: Path) -> None:
    """Extract PostgreSQL binaries."""
    print("=== Setting up PostgreSQL ===")
    pg_dir = root / "postgresql"
    # PostgreSQL zip has a top-level 'pgsql/' dir — strip it
    extract_zip(find_one(POSTGRES_GLOB), pg_dir, strip_top=True)
    print(f"  PostgreSQL ready: {pg_dir}")


def setup_nats(root: Path) -> None:
    """Extract NATS server."""
    print("=== Setting up NATS ===")
    nats_dir = root / "nats"
    nats_dir.mkdir(parents=True, exist_ok=True)
    # NATS zip has a top-level 'nats-server-v2.10.x-windows-amd64/' dir — extract only .exe
    with zipfile.ZipFile(find_one(NATS_GLOB)) as zf:
        for member in zf.infolist():
            if member.filename.endswith("nats-server.exe"):
                with zf.open(member) as src, open(nats_dir / "nats-server.exe", "wb") as dst:
                    shutil.copyfileobj(src, dst)
    print(f"  NATS ready: {nats_dir / 'nats-server.exe'}")


def setup_nssm(root: Path) -> None:
    """Extract NSSM (Non-Sucking Service Manager)."""
    print("=== Setting up NSSM ===")
    nssm_dir = root / "nssm"
    nssm_dir.mkdir(parents=True, exist_ok=True)
    # NSSM zip has 'nssm-2.24/win64/nssm.exe'
    with zipfile.ZipFile(find_one(NSSM_GLOB)) as zf:
        for member in zf.infolist():
            if member.filename.endswith("win64/nssm.exe"):
                with zf.open(member) as src, open(nssm_dir / "nssm.exe", "wb") as dst:
                    shutil.copyfileobj(src, dst)
    print(f"  NSSM ready: {nssm_dir / 'nssm.exe'}")


def copy_scripts(root: Path) -> None:
    """Copy .bat scripts from installer-scripts/ into build."""
    print("=== Copying scripts ===")
    scripts_src = WIN_BUILD / "installer-scripts"
    scripts_dst = root / "scripts"
    scripts_dst.mkdir(parents=True, exist_ok=True)
    for bat in scripts_src.glob("*.bat"):
        shutil.copy(bat, scripts_dst / bat.name)
        print(f"  {bat.name}")
    for txt in scripts_src.glob("*.txt"):
        shutil.copy(txt, root / txt.name)


def main() -> None:
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Build output: {OUT_ROOT}")
    print()

    clean_build()
    OUT_ROOT.mkdir(parents=True)

    app_dir = OUT_ROOT / "app"
    app_dir.mkdir()

    python_exe = setup_python(app_dir)
    install_pip(python_exe)
    install_dependencies(python_exe)
    compile_and_copy_source(app_dir)
    copy_static_assets(app_dir)

    setup_postgres(OUT_ROOT)
    setup_nats(OUT_ROOT)
    setup_nssm(OUT_ROOT)

    copy_scripts(OUT_ROOT)

    print()
    print("=== Build complete ===")
    print(f"  Output: {OUT_ROOT}")
    print(f"  Next: run Inno Setup with installer-scripts\\installer.iss")


if __name__ == "__main__":
    main()
