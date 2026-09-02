import pytest
from mysti.backup.manager import BackupManager
from mysti.export.manager import ExportManager
from mysti.notifications.manager import NotificationManager
@pytest.mark.asyncio
async def test_backup_roundtrip(tmp_path):
 seen=[]; b=BackupManager(b"x"*32,tmp_path,data_provider=lambda:{"memories":[1]},restore_handler=lambda x:seen.append(x)); i=await b.create_backup("one"); assert await b.restore_backup(i); assert seen[0]["memories"]==[1]
@pytest.mark.asyncio
async def test_notifications_and_export(tmp_path):
 n=NotificationManager(tmp_path/"n.json"); await n.send("Hi","Message"); assert len(await n.get_history())==1
 e=ExportManager(memory_provider=lambda:[{"content":"hello"}]); assert "hello" in await e.export_memories("markdown")