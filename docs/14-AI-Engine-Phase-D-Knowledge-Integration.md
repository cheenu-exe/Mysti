# AI Engine Phase D: Knowledge Integration

## Phase Overview

Phase D wires the knowledge graph + entity extraction into memory + chat. Currently, the knowledge graph exists but is never used. This phase makes the AI entity-aware — it extracts entities from conversations, stores them in the knowledge graph, and uses graph relationships for context.

The Knowledge Integration transforms MYSTI from a memory system into a knowledge-aware AI that understands relationships between concepts, people, and projects.

---

## Goals and Success Criteria

### Primary Goals

1. **Extract entities from conversations** — Identify people, places, concepts, projects
2. **Store entities in knowledge graph** — Build relationships over time
3. **Query knowledge graph during chat** — Use graph data for context
4. **Use graph relationships for context** — Understand connections
5. **Add entity-aware memory search** — Find memories by entity relationships

### Success Criteria

You know Phase D is complete when:

- Entities are extracted from conversations
- Knowledge graph is populated with entities and relationships
- Graph data is used in chat context
- Entity-aware memory search works
- Graph queries are efficient
- All existing tests still pass

---

## Architecture

### Current State (Phase A+B+C)

```
User Input
    ↓
AgentCore.chat()
    ↓
┌─────────────────────────────┐
│  RAG Pipeline               │
│  - Memory retrieval         │
└─────────────────────────────┘
    ↓
┌─────────────────────────────┐
│  Tool Executor              │
│  - Tool calling             │
└─────────────────────────────┘
    ↓
Response
```

**Problem:** No entity awareness. The AI doesn't understand relationships.

### Phase D Target State

```
User Input
    ↓
AgentCore.chat()
    ↓
┌─────────────────────────────┐
│  Entity Extraction          │
│  - Extract entities         │
│  - Identify relationships   │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│  Knowledge Graph            │
│  - Store entities           │
│  - Store relationships      │
│  - Query for context        │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│  RAG Pipeline               │
│  - Memory retrieval         │
│  - Entity-aware search      │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│  Tool Executor              │
│  - Tool calling             │
└─────────────────────────────┘
               ↓
Response with knowledge context
```

### Knowledge Integration Flow

```
User: "How is my MYSTI project progressing?"
    │
    ↓
┌─────────────────────────────────────────────┐
│  Agent Loop                                  │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │ Step 1: Entity Extraction               │ │
│  │ - Entity: MYSTI (project)               │ │
│  │ - Relationship: user's project          │ │
│  └───────────────────┬────────────────────┘ │
│                      ↓                       │
│  ┌────────────────────────────────────────┐ │
│  │ Step 2: Graph Query                     │ │
│  │ - Find MYSTI entity                     │ │
│  │ - Get related entities                  │ │
│  │ - Get project status                    │ │
│  └───────────────────┬────────────────────┘ │
│                      ↓                       │
│  ┌────────────────────────────────────────┐ │
│  │ Step 3: Context Building                │ │
│  │ - Graph data: "MYSTI is in Phase D"    │ │
│  │ - Related: "User is working on AI"      │ │
│  │ - Memories: "MYSTI started Phase 0..."  │ │
│  └───────────────────┬────────────────────┘ │
│                      ↓                       │
│  ┌────────────────────────────────────────┐ │
│  │ Step 4: Response                        │ │
│  │ - "Your MYSTI project is in Phase D,   │ │
│  │    building knowledge integration..."   │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

---

## Data Models

### Entity

Represents a person, place, concept, or project.

```python
@dataclass
class Entity:
    id: str
    name: str
    entity_type: str  # "person", "project", "concept", "location", "organization"
    description: str
    properties: dict[str, Any]
    created_at: str
    updated_at: str
```

**Fields:**

- `id` — Unique identifier
- `name` — Entity name
- `entity_type` — Type of entity
- `description` — Brief description
- `properties` — Additional properties
- `created_at` — Creation timestamp
- `updated_at` — Last update timestamp

### Relationship

Represents a connection between entities.

```python
@dataclass
class Relationship:
    id: str
    source_id: str
    target_id: str
    relationship_type: str  # "works_on", "uses", "depends_on", "related_to"
    properties: dict[str, Any]
    created_at: str
```

**Fields:**

- `id` — Unique identifier
- `source_id` — Source entity ID
- `target_id` — Target entity ID
- `relationship_type` — Type of relationship
- `properties` — Additional properties
- `created_at` — Creation timestamp

### GraphContext

Relevant graph data for a query.

```python
@dataclass
class GraphContext:
    query: str
    entities: list[Entity]
    relationships: list[Relationship]
    paths: list[list[str]]  # Entity ID paths
    relevance_score: float
```

**Fields:**

- `query` — The original query
- `entities` — Relevant entities
- `relationships` — Relevant relationships
- `paths` — Paths between entities
- `relevance_score` — Overall relevance

---

## API Design

### GET /knowledge/entities

List all entities.

**Query Parameters:**

- `type` — Filter by entity type
- `limit` — Maximum results (default: 100)
- `offset` — Pagination offset

**Response:**

```json
{
  "entities": [
    {
      "id": "ent-001",
      "name": "MYSTI",
      "entity_type": "project",
      "description": "Personal AI operating layer",
      "properties": {"status": "active", "phase": "D"},
      "created_at": "2026-08-15T00:00:00Z",
      "updated_at": "2026-09-02T00:00:00Z"
    }
  ],
  "total": 15
}
```

### GET /knowledge/entity/{id}

Get entity details.

**Response:**

```json
{
  "id": "ent-001",
  "name": "MYSTI",
  "entity_type": "project",
  "description": "Personal AI operating layer",
  "properties": {"status": "active", "phase": "D"},
  "relationships": [
    {
      "id": "rel-001",
      "target_id": "ent-002",
      "relationship_type": "created_by",
      "target_name": "Srinivasan"
    }
  ],
  "created_at": "2026-08-15T00:00:00Z",
  "updated_at": "2026-09-02T00:00:00Z"
}
```

### GET /knowledge/relationships

List relationships.

**Query Parameters:**

- `source_id` — Filter by source entity
- `target_id` — Filter by target entity
- `type` — Filter by relationship type

**Response:**

```json
{
  "relationships": [
    {
      "id": "rel-001",
      "source_id": "ent-001",
      "target_id": "ent-002",
      "relationship_type": "created_by",
      "properties": {},
      "created_at": "2026-08-15T00:00:00Z"
    }
  ]
}
```

### POST /knowledge/extract

Extract entities from text.

**Request:**

```json
{
  "text": "I'm working on MYSTI with Python and FastAPI",
  "context": "conversation"
}
```

**Response:**

```json
{
  "entities": [
    {"name": "MYSTI", "type": "project"},
    {"name": "Python", "type": "concept"},
    {"name": "FastAPI", "type": "concept"}
  ],
  "relationships": [
    {"source": "MYSTI", "target": "Python", "type": "uses"},
    {"source": "MYSTI", "target": "FastAPI", "type": "uses"}
  ]
}
```

### GET /knowledge/graph-context/{query}

Get graph context for a query.

**Response:**

```json
{
  "query": "MYSTI project status",
  "entities": [
    {"id": "ent-001", "name": "MYSTI", "type": "project"}
  ],
  "relationships": [
    {"source": "MYSTI", "target": "Phase D", "type": "in_phase"}
  ],
  "paths": [["ent-001", "ent-003"]],
  "relevance_score": 0.85
}
```

---

## Implementation Details

### Step 1: Create Knowledge Module Structure

Create the following files:

```
src/mysti/engine/
├── entity_extractor.py
└── graph_query.py
```

### Step 2: Implement EntityExtractor (entity_extractor.py)

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol

class LLMClient(Protocol):
    async def complete(self, messages: list[dict], **kwargs: Any) -> str: ...

class KnowledgeGraph(Protocol):
    async def add_entity(self, name: str, entity_type: str, description: str, properties: dict) -> Any: ...
    async def add_relationship(self, source_id: str, target_id: str, relationship_type: str, properties: dict) -> Any: ...
    async def search_entities(self, query: str) -> list[Any]: ...

@dataclass
class ExtractedEntity:
    name: str
    entity_type: str
    description: str
    properties: dict[str, Any]

@dataclass
class ExtractedRelationship:
    source_name: str
    target_name: str
    relationship_type: str
    properties: dict[str, Any]

class EntityExtractor:
    def __init__(
        self,
        llm: LLMClient,
        knowledge_graph: KnowledgeGraph | None = None,
    ):
        self.llm = llm
        self.graph = knowledge_graph
        self._extraction_prompt = """Extract entities and relationships from the following text.

Text: {text}

Return a JSON object with:
- entities: list of {{name, entity_type, description, properties}}
- relationships: list of {{source_name, target_name, relationship_type, properties}}

Entity types: person, project, concept, location, organization, tool, technology
Relationship types: works_on, uses, depends_on, related_to, created_by, part_of, uses_technology

Only extract clearly stated entities and relationships. If none found, return empty lists."""

    async def extract_from_text(self, text: str) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
        prompt = self._extraction_prompt.format(text=text)
        response = await self.llm.complete([
            {"role": "user", "content": prompt}
        ])

        try:
            import json
            data = json.loads(response)

            entities = [
                ExtractedEntity(
                    name=e.get("name", ""),
                    entity_type=e.get("entity_type", "concept"),
                    description=e.get("description", ""),
                    properties=e.get("properties", {})
                )
                for e in data.get("entities", [])
            ]

            relationships = [
                ExtractedRelationship(
                    source_name=r.get("source_name", ""),
                    target_name=r.get("target_name", ""),
                    relationship_type=r.get("relationship_type", "related_to"),
                    properties=r.get("properties", {})
                )
                for r in data.get("relationships", [])
            ]

            return entities, relationships

        except (json.JSONDecodeError, KeyError):
            return [], []

    async def extract_and_store(self, text: str) -> dict[str, Any]:
        entities, relationships = await self.extract_from_text(text)

        if not self.graph:
            return {"entities": entities, "relationships": relationships}

        # Store entities
        stored_entities = []
        for entity in entities:
            result = await self.graph.add_entity(
                name=entity.name,
                entity_type=entity.entity_type,
                description=entity.description,
                properties=entity.properties,
            )
            stored_entities.append(result)

        # Store relationships (need to resolve entity IDs)
        stored_relationships = []
        for rel in relationships:
            # Find source and target entities
            source_entities = await self.graph.search_entities(rel.source_name)
            target_entities = await self.graph.search_entities(rel.target_name)

            if source_entities and target_entities:
                result = await self.graph.add_relationship(
                    source_id=source_entities[0].id,
                    target_id=target_entities[0].id,
                    relationship_type=rel.relationship_type,
                    properties=rel.properties,
                )
                stored_relationships.append(result)

        return {
            "entities": stored_entities,
            "relationships": stored_relationships,
        }

    async def extract_from_conversation(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        # Combine recent messages for extraction
        recent_messages = messages[-10:]  # Last 10 messages
        text = "\n".join([f"{m['role']}: {m['content']}" for m in recent_messages])

        return await self.extract_and_store(text)
```

### Step 3: Implement GraphQuery (graph_query.py)

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol

class KnowledgeGraph(Protocol):
    async def get_entity(self, entity_id: str) -> Any: ...
    async def get_relationships(self, entity_id: str, direction: str = "both") -> list[Any]: ...
    async def find_path(self, source_id: str, target_id: str, max_depth: int = 3) -> list[list[str]]: ...
    async def search_entities(self, query: str) -> list[Any]: ...

@dataclass
class GraphContext:
    query: str
    entities: list[Any]
    relationships: list[Any]
    paths: list[list[str]]
    relevance_score: float

class GraphQuery:
    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.graph = knowledge_graph

    async def query_for_context(
        self,
        query: str,
        max_entities: int = 5,
        max_relationships: int = 10,
        max_depth: int = 2,
    ) -> GraphContext:
        # Search for relevant entities
        entities = await self.graph.search_entities(query)
        entities = entities[:max_entities]

        if not entities:
            return GraphContext(
                query=query,
                entities=[],
                relationships=[],
                paths=[],
                relevance_score=0.0
            )

        # Get relationships for each entity
        all_relationships = []
        for entity in entities:
            rels = await self.graph.get_relationships(entity.id)
            all_relationships.extend(rels)

        # Deduplicate relationships
        seen_ids = set()
        unique_relationships = []
        for rel in all_relationships:
            if rel.id not in seen_ids:
                seen_ids.add(rel.id)
                unique_relationships.append(rel)

        # Limit relationships
        unique_relationships = unique_relationships[:max_relationships]

        # Find paths between entities
        paths = []
        if len(entities) >= 2:
            for i in range(len(entities)):
                for j in range(i + 1, len(entities)):
                    path = await self.graph.find_path(
                        entities[i].id,
                        entities[j].id,
                        max_depth
                    )
                    if path:
                        paths.append(path)

        # Calculate relevance score
        relevance_score = min(1.0, len(entities) / max_entities)

        return GraphContext(
            query=query,
            entities=entities,
            relationships=unique_relationships,
            paths=paths,
            relevance_score=relevance_score
        )

    async def format_context_for_llm(self, context: GraphContext) -> str:
        if not context.entities:
            return ""

        lines = ["## Knowledge Graph Context\n"]

        # Entities
        lines.append("### Entities")
        for entity in context.entities:
            lines.append(f"- {entity.name} ({entity.entity_type}): {entity.description}")

        # Relationships
        if context.relationships:
            lines.append("\n### Relationships")
            for rel in context.relationships:
                lines.append(f"- {rel.relationship_type}: {rel.source_id} -> {rel.target_id}")

        # Paths
        if context.paths:
            lines.append("\n### Connections")
            for path in context.paths:
                if len(path) >= 2:
                    lines.append(f"- Connected: {' -> '.join(path)}")

        return "\n".join(lines)

    def get_entity_summary(self, context: GraphContext) -> str:
        if not context.entities:
            return "No entities found."

        summaries = []
        for entity in context.entities:
            summary = f"{entity.name} ({entity.entity_type})"
            if hasattr(entity, 'description') and entity.description:
                summary += f": {entity.description}"
            summaries.append(summary)

        return ", ".join(summaries)
```

### Step 4: Wire into AgentCore

Update `src/mysti/engine/core.py`:

```python
class AgentCore:
    def __init__(
        self,
        llm: LLMClient,
        tools: ToolGateway | None = None,
        memory: MemoryService | None = None,
        rag: RAGPipeline | None = None,
        knowledge_graph: KnowledgeGraph | None = None,
        permission_manager: PermissionManager | None = None,
        audit_log: AuditLog | None = None,
        max_steps: int = 10,
    ):
        # ... existing initialization ...

        # Initialize knowledge components
        if knowledge_graph:
            self.entity_extractor = EntityExtractor(llm=llm, knowledge_graph=knowledge_graph)
            self.graph_query = GraphQuery(knowledge_graph=knowledge_graph)
        else:
            self.entity_extractor = None
            self.graph_query = None

    async def chat(self, session_id: str, message: str) -> AgentResult:
        state = self.get_state(session_id)
        state.add_message("user", message)

        steps = []
        total_tokens = 0
        tools_used = []

        # Extract entities from user message
        if self.entity_extractor:
            await self.entity_extractor.extract_and_store(message)

        # Get knowledge graph context
        graph_context_str = ""
        if self.graph_query:
            graph_context = await self.graph_query.query_for_context(message)
            graph_context_str = await self.graph_query.format_context_for_llm(graph_context)

        # Retrieve relevant memories
        memories_used = []
        if self.rag:
            enhanced_messages, memories = await self.rag.enhance_context(
                state.to_context_messages(),
                message
            )
            memories_used = [m.memory_id for m in memories]
            state.memories_used.extend(memories_used)
        else:
            enhanced_messages = state.to_context_messages()

        # Build system prompt with all context
        prompt_builder = DynamicPromptBuilder()

        # Add knowledge graph context
        if graph_context_str:
            prompt_builder.add_section(graph_context_str)

        # Add tool definitions
        if self.tool_executor:
            tool_definitions = self.tool_executor.format_tools_for_prompt()
            if tool_definitions:
                prompt_builder.add_section(tool_definitions)

        system_prompt = prompt_builder.build()
        messages = [{"role": "system", "content": system_prompt}] + enhanced_messages

        # ... rest of the agent loop ...
```

### Step 5: Update DynamicPromptBuilder

Update `src/mysti/engine/prompt.py`:

```python
class DynamicPromptBuilder:
    def __init__(self, base_system_prompt: str | None = None):
        self.base_prompt = base_system_prompt or self._default_system_prompt()
        self.sections: list[str] = []

    def add_section(self, content: str) -> None:
        if content:
            self.sections.append(content)

    def add_knowledge_context(self, graph_context: str) -> None:
        if graph_context:
            self.sections.append(graph_context)

    def build(self) -> str:
        prompt = self.base_prompt
        if self.sections:
            prompt += "\n\n" + "\n".join(self.sections)
        return prompt
```

---

## Dependencies

### New Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| None | - | Uses existing `integration/knowledge_graph.py` |

### Existing Dependencies Used

| Dependency | Purpose |
|------------|---------|
| `integration/knowledge_graph.py` | KnowledgeGraph storage |
| `integration/extraction.py` | EntityExtractor (existing) |
| `core/llm.py` | LLM for extraction |
| `memory/service.py` | Memory search |

---

## Testing

### Unit Tests

**test_entity_extractor.py:**

```python
import pytest
from unittest.mock import AsyncMock
from mysti.engine.entity_extractor import EntityExtractor, ExtractedEntity

@pytest.mark.asyncio
async def test_extract_from_text():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = '''
    {
        "entities": [
            {"name": "MYSTI", "entity_type": "project", "description": "AI operating layer", "properties": {}}
        ],
        "relationships": []
    }
    '''

    extractor = EntityExtractor(llm=mock_llm)
    entities, relationships = await extractor.extract_from_text("I'm working on MYSTI")

    assert len(entities) == 1
    assert entities[0].name == "MYSTI"
    assert entities[0].entity_type == "project"

@pytest.mark.asyncio
async def test_extract_empty():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = '{"entities": [], "relationships": []}'

    extractor = EntityExtractor(llm=mock_llm)
    entities, relationships = await extractor.extract_from_text("Hello world")

    assert len(entities) == 0
    assert len(relationships) == 0
```

**test_graph_query.py:**

```python
import pytest
from unittest.mock import AsyncMock
from mysti.engine.graph_query import GraphQuery, GraphContext

@pytest.mark.asyncio
async def test_query_for_context():
    mock_graph = AsyncMock()
    mock_entity = AsyncMock()
    mock_entity.id = "ent-001"
    mock_entity.name = "MYSTI"
    mock_entity.entity_type = "project"
    mock_entity.description = "AI operating layer"

    mock_graph.search_entities.return_value = [mock_entity]
    mock_graph.get_relationships.return_value = []

    query = GraphQuery(mock_graph)
    context = await query.query_for_context("MYSTI project")

    assert len(context.entities) == 1
    assert context.entities[0].name == "MYSTI"

@pytest.mark.asyncio
async def test_query_no_results():
    mock_graph = AsyncMock()
    mock_graph.search_entities.return_value = []

    query = GraphQuery(mock_graph)
    context = await query.query_for_context("nonexistent thing")

    assert len(context.entities) == 0
    assert context.relevance_score == 0.0
```

### Integration Tests

**test_knowledge_integration.py:**

```python
import pytest
from mysti.engine.entity_extractor import EntityExtractor
from mysti.integration.knowledge_graph import KnowledgeGraph

@pytest.mark.asyncio
async def test_full_extraction_flow():
    # This would use real services in integration tests
    # For now, test the flow with mocks
    pass
```

---

## Edge Cases

### No Entities Found

```python
async def extract_from_text(self, text):
    entities, relationships = await self.extract_from_text(text)
    if not entities:
        return {"entities": [], "relationships": []}
    # Continue with storage...
```

### Entity Already Exists

```python
async def add_entity(self, name, entity_type, description, properties):
    # Check if entity already exists
    existing = await self.search_entities(name)
    if existing:
        # Update existing entity
        return await self.update_entity(existing[0].id, {
            "description": description,
            "properties": properties,
        })
    # Create new entity
    return await self._create_entity(name, entity_type, description, properties)
```

### Graph Query Fails

```python
async def query_for_context(self, query, ...):
    try:
        entities = await self.graph.search_entities(query)
    except Exception:
        # Fallback to empty context
        return GraphContext(
            query=query,
            entities=[],
            relationships=[],
            paths=[],
            relevance_score=0.0
        )
    # Continue with query...
```

### Circular Relationships

```python
async def find_path(self, source_id, target_id, max_depth=3):
    # BFS with cycle detection
    visited = set()
    queue = [[source_id]]

    while queue:
        path = queue.pop(0)
        current = path[-1]

        if current == target_id:
            return path

        if len(path) > max_depth:
            continue

        if current in visited:
            continue

        visited.add(current)

        # Get neighbors
        rels = await self.get_relationships(current)
        for rel in rels:
            neighbor = rel.target_id if rel.source_id == current else rel.source_id
            if neighbor not in visited:
                queue.append(path + [neighbor])

    return []  # No path found
```

### Memory Pressure from Graph

```python
async def query_for_context(self, query, max_entities=5, ...):
    # Limit entities to prevent memory issues
    entities = await self.graph.search_entities(query)
    entities = entities[:max_entities]

    # Use pagination for large result sets
    if len(entities) == max_entities:
        # There might be more, but we're limiting
        pass
    # Continue with limited results...
```

---

## Deliverables

When Phase D is complete, you will have:

1. **`src/mysti/engine/entity_extractor.py`** — EntityExtractor class
2. **`src/mysti/engine/graph_query.py`** — GraphQuery class
3. **Updated AgentCore** — Uses knowledge graph
4. **Updated DynamicPromptBuilder** — Adds knowledge context
5. **API endpoints** — Knowledge graph queries
6. **Tests** — 6+ unit tests, 2+ integration tests

---

## What Comes Next

After Phase D, you will move to **Phase E: Intelligence Layer**, which adds:
- Model routing (select best model per task)
- Proactive behavior (surface relevant information)
- Streaming responses (SSE)
- Auto-memory extraction (learn from conversations)

Phase D's knowledge integration provides the foundation for intelligent routing and proactive behavior, with entity-aware context available for decision-making.

---

*Phase D makes MYSTI entity-aware — the AI understands relationships between concepts, people, and projects.*
