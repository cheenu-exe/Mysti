from __future__ import annotations
import time
from dataclasses import dataclass, field
from uuid import UUID, uuid4
@dataclass
class BenchmarkTask:
    id: UUID=field(default_factory=uuid4); name: str=""; type: str="analysis"; input: str=""; expected_output: str|None=None; difficulty: int=1
@dataclass
class BenchmarkResult:
    task_id: UUID; model: str; output: str; quality_score: float; response_time: float; tokens_used: int; cost: float
class BenchmarkRunner:
    def __init__(self,models=None,registry=None): self.models=models or {}; self.registry=registry; self.results=[]
    async def run_benchmark(self,model,tasks):
        client=self.models[model] if isinstance(self.models,dict) else self.models
        results=[]
        for task in tasks:
            start=time.monotonic(); output=await client.complete([{"role":"user","content":task.input}],model=model); elapsed=time.monotonic()-start
            quality=10.0 if task.expected_output and task.expected_output.casefold() in output.casefold() else 5.0
            results.append(BenchmarkResult(task.id,model,output,quality,len(output.split()) and elapsed or elapsed,len(output.split()),0.0))
        self.results.extend(results); return results
    async def run_all_models(self,tasks): return {name:await self.run_benchmark(name,tasks) for name in self.models}
    async def get_leaderboard(self):
        scores={}
        for r in self.results: scores.setdefault(r.model,[]).append(r)
        return [{"model":m,"quality_score":sum(x.quality_score for x in rs)/len(rs),"response_time":sum(x.response_time for x in rs)/len(rs)} for m,rs in scores.items()]
    async def generate_report(self): return {"leaderboard":await self.get_leaderboard(),"tasks":len(self.results)}