"""Build and package a portable source release, excluding runtime data and secrets."""

import argparse
import hashlib
import json
import os
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    ".gitignore",
    ".env.example",
    "README.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
}
DIRECTORIES = {"backend", "frontend", "scripts", "docs", ".github"}
EXCLUDED = {
    ".git",
    ".venv",
    "node_modules",
    ".tools",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".tmp",
    "data",
    "release",
    ".mypy_cache",
}


def sources():
    for directory, subdirectories, filenames in os.walk(ROOT):
        subdirectories[:] = sorted(
            name
            for name in subdirectories
            if name not in EXCLUDED
            and not name.endswith(".egg-info")
            and (Path(directory) != ROOT or name in DIRECTORIES)
        )
        for name in sorted(filenames):
            path = Path(directory) / name
            relative = path.relative_to(ROOT)
            if Path(directory) == ROOT and name not in ROOT_FILES:
                continue
            if path.is_symlink() or not path.is_file():
                continue
            if name.startswith(".env") and not name.endswith(".example"):
                continue
            if path.suffix in {
                ".db",
                ".sqlite",
                ".sqlite3",
                ".log",
                ".pyc",
                ".tsbuildinfo",
            }:
                continue
            yield relative.as_posix(), path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    if not args.skip_build:
        subprocess.run(
            ["node", str(ROOT / "frontend/node_modules/typescript/bin/tsc"), "-b"],
            cwd=ROOT / "frontend",
            check=True,
        )
        subprocess.run(
            ["node", str(ROOT / "frontend/node_modules/vite/bin/vite.js"), "build"],
            cwd=ROOT / "frontend",
            check=True,
        )
    version = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))[
        "version"
    ]
    output = ROOT / "release"
    output.mkdir(exist_ok=True)
    target = output / f"automation-platform-{version}.zip"
    manifest = {}
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative, path in sources():
            raw = path.read_bytes()
            manifest[relative] = hashlib.sha256(raw).hexdigest()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
        manifest_info = zipfile.ZipInfo(
            "RELEASE-MANIFEST.json", date_time=(1980, 1, 1, 0, 0, 0)
        )
        manifest_info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(
            manifest_info,
            json.dumps(
                {"version": version, "sha256": manifest}, indent=2, sort_keys=True
            ),
        )
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(".zip.sha256").write_text(
        checksum + "  " + target.name + "\n", encoding="ascii"
    )
    print(f"Release: {target}")
    print(f"SHA256: {checksum}")


if __name__ == "__main__":
    main()
