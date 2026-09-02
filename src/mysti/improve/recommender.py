from __future__ import annotations
from dataclasses import asdict, dataclass, field
from uuid import UUID, uuid4
from ._store import JsonFile
@dataclass
class Recommendation:
    id: UUID=field(default_factory=uuid4); type: str="config"; priority: str="low"; title: str=""; description: str=""; current_value: object=None; recommended_value: object=None; reason: str=""
class UpdateRecommender:
    def __init__(self,config=None,path="mysti/improve/recommendations.json.enc"): self.config=config or {}; self.file=JsonFile(path); self.items={}
    async def analyze_config(self):
        if not self.config: self.items["llm"] = Recommendation(type="config",priority="medium",title="Configure an LLM",description="No LLM provider is configured",reason="Enable model-backed features")
        return list(self.items.values())
    async def analyze_performance(self): return []
    async def get_recommendations(self): return (await self.analyze_config()) + (await self.analyze_performance())
    async def apply_recommendation(self,rec_id):
        rec=next((r for r in self.items.values() if str(r.id)==str(rec_id)),None)
        if not rec:return False
        if isinstance(self.config,dict):self.config[rec.title]=rec.recommended_value
        self.file.save([asdict(r) for r in self.items.values()]); return True