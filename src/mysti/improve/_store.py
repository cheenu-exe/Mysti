from __future__ import annotations
import json
from pathlib import Path
class JsonFile:
    def __init__(self,path): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
    def load(self,default):
        try:return json.loads(self.path.read_text())
        except (OSError,ValueError):return default
    def save(self,value): self.path.write_text(json.dumps(value,indent=2,default=str))