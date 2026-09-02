from __future__ import annotations
import json
from pathlib import Path
from typing import Any

class JsonStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
    def load(self, default: Any) -> Any:
        try: return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError): return default
    def save(self, value: Any) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.path)