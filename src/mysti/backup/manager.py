from __future__ import annotations
import inspect,json,uuid
from datetime import UTC,datetime
from pathlib import Path
from mysti.memory.envelope import encrypt,decrypt
class BackupManager:
    def __init__(self,key:bytes,path="mysti/backups",data_provider=None,restore_handler=None): self.key=key; self.path=Path(path); self.path.mkdir(parents=True,exist_ok=True); self.data_provider=data_provider; self.restore_handler=restore_handler
    async def create_backup(self,name=None):
        bid=name or str(uuid.uuid4()); data=self.data_provider() if self.data_provider else {"memories":[],"graph":{},"settings":{}}; data=await data if inspect.isawaitable(data) else data; payload={"version":"1.0","created_at":datetime.now(UTC).isoformat(),**data}; (self.path/f"{bid}.enc").write_bytes(encrypt(self.key,json.dumps(payload).encode(),f"mysti:backup:{bid}".encode())); return bid
    async def restore_backup(self,backup_id):
        data=json.loads(decrypt(self.key,(self.path/f"{backup_id}.enc").read_bytes(),f"mysti:backup:{backup_id}".encode()));
        if self.restore_handler:
            result = self.restore_handler(data)
            if inspect.isawaitable(result): await result
        return True
    async def list_backups(self): return [{"id":p.stem,"size":p.stat().st_size} for p in self.path.glob("*.enc")]
    async def delete_backup(self,backup_id): (self.path/f"{backup_id}.enc").unlink(missing_ok=True)