from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4
from ._persistence import JsonStore

def _now(): return datetime.now(UTC)
@dataclass
class Entity:
    id: UUID = field(default_factory=uuid4); name: str = ""; type: str = "concept"
    attributes: dict = field(default_factory=dict); created_at: datetime = field(default_factory=_now)
    last_accessed: datetime = field(default_factory=_now)
@dataclass
class Relationship:
    id: UUID = field(default_factory=uuid4); source_id: UUID = field(default_factory=uuid4)
    target_id: UUID = field(default_factory=uuid4); type: str = "mentioned_in"; weight: float = 1.0
    metadata: dict = field(default_factory=dict)

class KnowledgeGraph:
    def __init__(self, path: str | None = None):
        root = path or "mysti/graph"
        self._entities = JsonStore(f"{root}/entities.json.enc"); self._relationships = JsonStore(f"{root}/relationships.json.enc")
        self.entities = {UUID(x["id"]): self._entity(x) for x in self._entities.load([])}
        self.relationships = {UUID(x["id"]): self._relationship(x) for x in self._relationships.load([])}
    def _entity(self, x):
        x = dict(x); x["id"] = UUID(x["id"]); x["created_at"] = datetime.fromisoformat(x["created_at"]); x["last_accessed"] = datetime.fromisoformat(x["last_accessed"]); return Entity(**x)
    def _relationship(self, x):
        x = dict(x); x.update({k: UUID(x[k]) for k in ("id", "source_id", "target_id")}); return Relationship(**x)
    def _save(self):
        def enc(x):
            d = asdict(x)
            for k, v in d.items():
                if isinstance(v, (UUID, datetime)): d[k] = str(v)
            return d
        self._entities.save([enc(x) for x in self.entities.values()]); self._relationships.save([enc(x) for x in self.relationships.values()])
    async def add_entity(self, entity: Entity) -> str:
        existing = next((e for e in self.entities.values() if e.name.casefold() == entity.name.casefold() and e.type == entity.type), None)
        if existing: existing.attributes.update(entity.attributes); existing.last_accessed = _now(); result = existing
        else: self.entities[entity.id] = entity; result = entity
        self._save(); return str(result.id)
    async def add_relationship(self, rel: Relationship) -> str:
        rel.weight = max(0.0, min(1.0, rel.weight)); self.relationships[rel.id] = rel; self._save(); return str(rel.id)
    async def get_entity(self, entity_id: str) -> Entity:
        entity = self.entities[UUID(str(entity_id))]; entity.last_accessed = _now(); self._save(); return entity
    async def get_relationships(self, entity_id: str) -> list[Relationship]:
        uid = UUID(str(entity_id)); return [r for r in self.relationships.values() if r.source_id == uid or r.target_id == uid]
    async def find_path(self, source: str, target: str) -> list[str]:
        start, end = UUID(str(source)), UUID(str(target)); queue = [(start, [str(start)])]; seen = {start}
        while queue:
            node, path = queue.pop(0)
            if node == end: return path
            for r in await self.get_relationships(str(node)):
                nxt = r.target_id if r.source_id == node else r.source_id
                if nxt not in seen: seen.add(nxt); queue.append((nxt, path + [str(nxt)]))
        return []
    async def search(self, query: str) -> list[Entity]:
        terms = query.casefold().split(); return [e for e in self.entities.values() if all(t in (e.name + " " + str(e.attributes)).casefold() for t in terms)]
    async def get_context(self, entity_id: str) -> dict:
        e = await self.get_entity(entity_id); return {"entity": e, "relationships": await self.get_relationships(entity_id)}