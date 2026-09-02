from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from ._persistence import JsonStore
@dataclass
class LearningItem:
    topic: str; skill_level: int = 1; last_studied: datetime = field(default_factory=lambda: datetime.now(UTC)); resources: list[str] = field(default_factory=list); notes: list[str] = field(default_factory=list)
class LearningTracker:
    def __init__(self, path="mysti/learning/items.json.enc"):
        self.store=JsonStore(path); self.items={}
        for x in self.store.load([]):
            x["last_studied"] = datetime.fromisoformat(x["last_studied"])
            self.items[x["topic"]] = LearningItem(**x)
    def _save(self): self.store.save([{**asdict(x), "last_studied": x.last_studied.isoformat()} for x in self.items.values()])
    async def add_learning_item(self,item): self.items[item.topic]=item; self._save(); return item.topic
    async def update_progress(self,topic,level,notes=None):
        item=self.items[topic]; item.skill_level=max(1,min(10,level)); item.last_studied=datetime.now(UTC); notes and item.notes.append(notes); self._save()
    async def get_learning_items(self): return list(self.items.values())
    async def get_gaps(self): return [{"topic":x.topic,"skill_level":x.skill_level} for x in self.items.values() if x.skill_level < 5]
    async def suggest_resources(self,topic): return [{"topic":topic,"type":"tutorial"},{"topic":topic,"type":"project"}]