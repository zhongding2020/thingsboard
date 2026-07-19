"""Compile all project .py files to .pyc, strip .py sources.

Usage:
    python compile-pyc.py <src_dir> <out_dir>

Example:
    python compile-pyc.py ../../src/process_opt ./build/app/process_opt

What it does:
  1. Copy src_dir → out_dir
  2. Recursively compile every .py to .pyc (using py_compile)
  3. Move .pyc files from __pycache__/*.cpython-311.pyc up one level
     and rename to the original name (foo.py → foo.pyc)
  4. Delete original .py files (except __init__.py — package marker)
  5. Delete __pycache__ dirs
  6. Preserve non-.py files (JSON, MD, etc.)
"""

from __future__ import annotations

import argparse
import py_compile
import shutil
import sys
from pathlib import Path


# __init__.py files are kept as .py so Python's package discovery works
# reliably across all embedding scenarios. They usually contain nothing
# sensitive (just imports).
KEEP_AS_PY = {"__init__.py"}


def compile_and_strip(src: Path, dst: Path) -> tuple[int, int]:
    """Compile all .py in src to .pyc in dst. Returns (compiled, kept_as_py)."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

    compiled = 0
    kept = 0

    for py_file in sorted(dst.rglob("*.py")):
        if py_file.name in KEEP_AS_PY:
            kept += 1
            continue

        # Compile to sibling .pyc
        pyc_file = py_file.with_suffix(".pyc")
        try:
            py_compile.compile(
                str(py_file),
                cfile=str(pyc_file),
                doraise=True,
                optimize=2,  # Strip docstrings + assertions
            )
        except py_compile.PyCompileError as e:
            print(f"  [ERROR] Failed to compile {py_file}: {e}", file=sys.stderr)
            raise

        # Delete original .py
        py_file.unlink()
        compiled += 1

    # Remove __pycache__ dirs (compile() with cfile= shouldn't create them,
    # but clean up any stragglers)
    for cache_dir in dst.rglob("__pycache__"):
        shutil.rmtree(cache_dir)

    return compiled, kept


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile .py → .pyc and strip sources")
    parser.add_argument("src", type=Path, help="Source directory (e.g. src/process_opt)")
    parser.add_argument("dst", type=Path, help="Output directory")
    args = parser.parse_args()

    if not args.src.is_dir():
        print(f"Error: source not found: {args.src}", file=sys.stderr)
        sys.exit(1)

    print(f"Compiling {args.src} → {args.dst}")
    compiled, kept = compile_and_strip(args.src, args.dst)
    print(f"  Compiled: {compiled} .py → .pyc")
    print(f"  Kept as .py: {kept} (package markers)")
    print(f"  Done: {args.dst}")


if __name__ == "__main__":
    main()
