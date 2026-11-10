import importlib.util
import json
import sys
import zipfile

from app.core.config import PROJECT_ROOT


def test_release_excludes_local_secrets_and_is_reproducible(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "package_release", PROJECT_ROOT / "scripts" / "package_release.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    contents = {
        "frontend/package.json": json.dumps({"version": "0.3.0"}),
        "frontend/src/app.ts": "export const app = 1;",
        "backend/app/main.py": "# source",
        "README.md": "Install from source",
        "backend/.env.example": "SECRET_NAME=",
        "backend/.env": "PRIVATE_SECRET=do-not-package",
        "backend/.venv/credentials.txt": "do-not-package",
        "data/user.db": "do-not-package",
        ".git/config": "do-not-package",
    }
    for name, raw in contents.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["package_release", "--skip-build"])
    module.main()
    target = tmp_path / "release" / "automation-platform-0.3.0.zip"
    first = target.read_bytes()
    with zipfile.ZipFile(target) as archive:
        names = archive.namelist()
        assert "backend/.env.example" in names
        assert "backend/.env" not in names
        assert not any(name.startswith(("data/", ".git/")) or ".venv" in name for name in names)
        assert all(b"do-not-package" not in archive.read(name) for name in names)
        assert "RELEASE-MANIFEST.json" in names
    module.main()
    assert target.read_bytes() == first
