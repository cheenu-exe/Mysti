from __future__ import annotations
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4
from ._persistence import JsonStore
@dataclass
class Goal:
    id: UUID = field(default_factory=uuid4); title: str = ""; description: str = ""; category: str = "personal"; deadline: datetime | None = None; progress: float = 0; status: str = "active"; milestones: list[dict] = field(default_factory=list); created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
class GoalSystem:
    def __init__(self,path="mysti/goals"): self.path=path; self.goals={}
    def _save(self,g):
        from dataclasses import asdict
        d=asdict(g); d['id']=str(g.id); d['created_at']=g.created_at.isoformat(); JsonStore(f"{self.path}/{g.id}.enc").save(d)
    async def create_goal(self,g): self.goals[g.id]=g; self._save(g); return str(g.id)
    async def update_goal(self,id,updates): g=self.goals[UUID(str(id))]; [setattr(g,k,v) for k,v in updates.items() if hasattr(g,k)]; self._save(g)
    async def get_goal(self,id): return self.goals[UUID(str(id))]
    async def list_goals(self,category=None): return [g for g in self.goals.values() if category is None or g.category==category]
    async def get_progress_report(self): return {"total":len(self.goals),"overall_progress":sum(g.progress for g in self.goals.values())/len(self.goals) if self.goals else 0,"active":sum(g.status=="active" for g in self.goals.values())}