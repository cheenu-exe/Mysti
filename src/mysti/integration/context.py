from __future__ import annotations
class ContextBuilder:
    def __init__(self, memory=None, graph=None, max_chars: int = 12000): self.memory, self.graph, self.max_chars = memory, graph, max_chars
    async def build_context(self, query: str, conversation: list[dict]) -> str:
        sections = ["[Relevant Memories]"]
        if self.memory:
            for hit in await self.memory.search(query, limit=10): sections.append(f"- Memory (relevance: {hit.score:.2f}): {hit.preview}")
        sections.append("\n[Related Entities]")
        if self.graph:
            for entity in await self.graph.search(query): sections.append(f"- {entity.type.title()}: {entity.name}")
        sections.append("\n[Recent Conversation]")
        sections.extend(f"- {m.get('role', 'user').title()}: {m.get('content', '')}" for m in conversation)
        return "\n".join(sections)[:self.max_chars]
    async def build_system_prompt(self) -> str: return "You are MYSTI, a private personal AI assistant. Use the supplied context carefully."