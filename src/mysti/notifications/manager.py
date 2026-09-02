from __future__ import annotations
import json
from datetime import UTC,datetime
from pathlib import Path
class NotificationManager:
    def __init__(self,path="mysti/notifications.json"): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.prefs=self._load().get("preferences",{}); self.history=self._load().get("history",[])
    def _load(self):
        try:return json.loads(self.path.read_text())
        except (OSError,ValueError):return {}
    def _save(self):self.path.write_text(json.dumps({"preferences":self.prefs,"history":self.history},indent=2))
    async def send(self,title,message,channel="all"):
        event={"title":title,"message":message,"channel":channel,"timestamp":datetime.now(UTC).isoformat()}; self.history.append(event); self._save(); return event
    async def get_preferences(self):return dict(self.prefs)
    async def update_preferences(self,prefs):self.prefs.update(prefs);self._save()
    async def get_history(self,limit=50):return self.history[-limit:]