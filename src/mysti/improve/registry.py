from __future__ import annotations
from dataclasses import asdict, dataclass, field
from pathlib import Path
from ._store import JsonFile

@dataclass
class ModelEntry:
    name: str; provider: str; model_id: str; cost_per_1k_tokens: float = 0.0; context_window: int = 4096
    strengths: list[str] = field(default_factory=list); weaknesses: list[str] = field(default_factory=list)
    avg_response_time: float = 0.0; avg_quality_score: float = 0.0

class ModelRegistry:
    def __init__(self, path: str | Path | None = None):
        self.file=JsonFile(path or Path.home()/".config"/"mysti"/"models.json")
        self.models={x["name"]:ModelEntry(**x) for x in self.file.load([])}
    async def register_model(self, model): self.models[model.name]=model; self.file.save([asdict(x) for x in self.models.values()]); return model.name
    async def get_model(self,name): return self.models[name]
    async def list_models(self): return list(self.models.values())
    async def compare_models(self,names): return {n:asdict(self.models[n]) for n in names if n in self.models}
    async def get_recommendation(self,task_type):
        def score(m): return m.avg_quality_score - m.cost_per_1k_tokens * .1 - m.avg_response_time * .01 + (1 if task_type in m.strengths else 0)
        if not self.models: raise LookupError("no models registered")
        return max(self.models.values(),key=score)