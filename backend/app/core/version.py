import hashlib
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
_digest = hashlib.sha256()
for _path in sorted(_root.rglob("*.py")):
    _digest.update(_path.relative_to(_root).as_posix().encode())
    _digest.update(_path.read_bytes())
BUILD_ID = _digest.hexdigest()[:12]
