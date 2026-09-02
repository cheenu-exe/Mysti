from __future__ import annotations
from collections import defaultdict
from datetime import UTC, datetime
class ModelRouter:
    def __init__(self,registry,clients=None,audit=None,daily_limit:float|None=None): self.registry=registry; self.clients=clients or {}; self.audit=audit; self.daily_limit=daily_limit; self.costs=defaultdict(float); self.failures=defaultdict(list)
    async def route(self,task_type,input): return await self.registry.get_recommendation(task_type)
    async def fallback_chain(self,task_type):
        models=await self.registry.list_models(); return sorted(models,key=lambda m:(task_type not in m.strengths,-m.avg_quality_score,m.cost_per_1k_tokens,m.avg_response_time))
    async def handle_failure(self,model,error): self.failures[model].append({"error":error,"timestamp":datetime.now(UTC).isoformat()}); self.audit and self.audit.log("llm.failure",model,reason=error)
    async def complete(self,task_type,input):
        for model in await self.fallback_chain(task_type):
            try: return await self.clients[model.name].complete([{"role":"user","content":input}],model=model.model_id)
            except Exception as exc: await self.handle_failure(model.name,str(exc))
        raise RuntimeError("all models failed")