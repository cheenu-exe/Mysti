from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4
from ._persistence import JsonStore
@dataclass
class Task: id: UUID = field(default_factory=uuid4); title: str = ""; status: str = "todo"; priority: int = 3; due_date: datetime | None = None
@dataclass
class Milestone: title: str = ""; completed: bool = False
@dataclass
class Project:
    id: UUID = field(default_factory=uuid4); name: str = ""; description: str = ""; status: str = "active"; tasks: list[Task] = field(default_factory=list); milestones: list[Milestone] = field(default_factory=list); created_at: datetime = field(default_factory=lambda: datetime.now(UTC)); updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
class ProjectTracker:
    def __init__(self,path="mysti/projects"):
        self.path=path; self.projects={}
        import json
        for file in __import__('pathlib').Path(path).glob('*.enc'):
            try:
                x=json.loads(file.read_text()); x['id']=UUID(x['id']); x['created_at']=datetime.fromisoformat(x['created_at']); x['updated_at']=datetime.fromisoformat(x['updated_at']); x['tasks']=[Task(**t) for t in x.get('tasks',[])]; x['milestones']=[Milestone(**m) for m in x.get('milestones',[])]; self.projects[x['id']]=Project(**x)
            except (OSError, ValueError, TypeError): pass
    def _save(self,p): JsonStore(f"{self.path}/{p.id}.enc").save({**asdict(p),"id":str(p.id),"created_at":p.created_at.isoformat(),"updated_at":p.updated_at.isoformat()})
    async def create_project(self,p): self.projects[p.id]=p; self._save(p); return str(p.id)
    async def get_project(self,id): return self.projects[UUID(str(id))]
    async def update_project(self,id,updates): p=await self.get_project(id); [setattr(p,k,v) for k,v in updates.items() if hasattr(p,k)]; p.updated_at=datetime.now(UTC); self._save(p)
    async def add_task(self,id,task): p=await self.get_project(id); p.tasks.append(task); self._save(p); return str(task.id)
    async def update_task(self,id,task_id,updates):
        t=next(t for t in (await self.get_project(id)).tasks if t.id==UUID(str(task_id))); [setattr(t,k,v) for k,v in updates.items() if hasattr(t,k)]; self._save(await self.get_project(id))
    async def list_projects(self,status=None): return [p for p in self.projects.values() if status is None or p.status==status]