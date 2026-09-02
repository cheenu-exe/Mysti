from __future__ import annotations
import json
from uuid import UUID
from .knowledge_graph import Entity, KnowledgeGraph, Relationship

class EntityExtractor:
    def __init__(self, llm=None, graph: KnowledgeGraph | None = None): self.llm, self.graph = llm, graph or KnowledgeGraph()
    async def extract_from_text(self, text: str) -> dict:
        if self.llm is None: return {"entities": [], "relationships": []}
        prompt = "Extract entities and relationships as JSON with entities and relationships keys:\n" + text
        raw = await self.llm.complete([{"role": "user", "content": prompt}])
        try: return json.loads(raw)
        except (ValueError, TypeError): return {"entities": [], "relationships": []}
    async def extract_and_store(self, text: str, source_id: str) -> dict:
        data = await self.extract_from_text(text); ids = {}
        for item in data.get("entities", []): ids[item["name"]] = await self.graph.add_entity(Entity(name=item["name"], type=item.get("type", "concept"), attributes=item.get("attributes", {})))
        for item in data.get("relationships", []):
            if item.get("source") in ids and item.get("target") in ids: await self.graph.add_relationship(Relationship(source_id=UUID(ids[item["source"]]), target_id=UUID(ids[item["target"]]), type=item.get("type", "mentioned_in"), metadata={"source_id": source_id}))
        return data
    async def extract_from_conversation(self, messages: list[dict]) -> dict: return await self.extract_from_text("\n".join(str(m.get("content", "")) for m in messages))