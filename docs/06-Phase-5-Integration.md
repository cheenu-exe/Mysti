# Phase 5: Memory + Research Integration

## Phase Overview

Phase 5 connects MYSTI's isolated subsystems into a coherent knowledge system. Before Phase 5, memories, research, tools, and security operate independently. After Phase 5, they form an interconnected knowledge graph where your memories, research findings, projects, people, and goals are all linked together.

The core addition is the **Knowledge Graph** — a structure that maps relationships between entities in your knowledge base. When you discuss a project, the graph knows which technologies it uses, which people are involved, what research is relevant, and what goals it serves. This context makes MYSTI's responses dramatically more useful because it understands not just individual facts, but how they relate to each other.

Phase 5 also adds **context injection** — the ability to automatically load relevant memories, research, and project context into conversations. Instead of you manually recalling information, MYSTI proactively surfaces what's relevant to the current discussion.

Additionally, Phase 5 introduces **learning tracking** and **project management** capabilities that help MYSTI understand your development journey and ongoing work.

---

## Goals and Success Criteria

### Primary Goals

1. **Knowledge graph** — Map relationships between memories, research, people, projects, and goals.
2. **Entity extraction** — Automatically identify and link entities from conversations and research.
3. **Context injection** — Automatically load relevant context into conversations.
4. **Learning tracker** — Track skills, topics studied, time spent, and proficiency.
5. **Project tracker** — Manage project lifecycle, tasks, and progress.
6. **Goal system** — Define goals and check alignment with activities.
7. **Relationship mapping** — Track people and their connections to projects and topics.

### Success Criteria

You know Phase 5 is complete when:

- MYSTI can answer "what projects use Docker?" by querying the knowledge graph
- MYSTI automatically loads relevant context when you start a conversation about a topic
- MYSTI can tell you what you've learned recently and where gaps exist
- MYSTI can track project progress and remind you of deadlines
- MYSTI can check if an activity aligns with your stated goals
- The knowledge graph accurately reflects the relationships in your knowledge base

---

## Architecture

### What Phase 5 Adds

Phase 5 adds the integration layer that connects everything:

```
Existing Components:
├── Memory System (Phase 1)
├── Research System (Phase 2)
├── Security Layer (Phase 3)
├── Tool System (Phase 4)

Phase 5 Adds:
├── Knowledge Graph (entity-relationship store)
├── Entity Extractor (identifies entities in content)
├── Context Engine (loads relevant context)
├── Learning Tracker (skill development)
├── Project Manager (project lifecycle)
├── Goal System (alignment checking)
└── Relationship Mapper (people and connections)
```

### Knowledge Graph Architecture

The knowledge graph is a network of entities and relationships:

```
                    ┌─────────┐
         ┌─────────┤  Person ├─────────┐
         │         └────┬────┘         │
         │              │              │
    works_on        knows          collaborates
         │              │              │
    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
    │ Project │    │ Project │    │ Project │
    └────┬────┘    └────┬────┘    └────┬────┘
         │              │              │
     uses           uses           uses
         │              │              │
    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
    │  Tech   │    │  Tech   │    │  Tech   │
    └────┬────┘    └────┬────┘    └────┬────┘
         │              │              │
    related_to     related_to     related_to
         │              │              │
    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
    │Research │    │Research │    │Research │
    └─────────┘    └─────────┘    └─────────┘
```

### Data Flow for Context Injection

When you start a conversation:

```
You say: "How's the MYSTI project going?"
    ↓
Context Engine analyzes your message
    ↓
Identifies entity: "MYSTI" (project)
    ↓
Queries Knowledge Graph for MYSTI entity
    ↓
Retrieves:
    - Project status and recent changes
    - Related technologies (Python, FastAPI, Docker)
    - Related people (you, collaborators)
    - Related research (relevant papers, tools)
    - Active goals and milestones
    ↓
Injects context into LLM conversation
    ↓
MYSTI responds with full context awareness
```

---

## Data Models

### Entity Record

Represents a node in the knowledge graph.

**Fields:**

- `id` — Unique identifier (UUID).
- `type` — Entity type: person, project, technology, research, goal, skill, concept, file, conversation.
- `name` — Human-readable name.
- `encrypted_properties` — Type-specific properties (encrypted JSON).
- `created_at` — When the entity was created.
- `updated_at` — When the entity was last updated.

**Entity type properties:**

- **person:** name, role, contact_info, notes, relationship_to_user
- **project:** name, description, status, start_date, deadline, repository_path, tech_stack
- **technology:** name, category, version, proficiency_level, documentation_url
- **research:** title, source, summary, relevance_score, key_findings
- **goal:** name, description, deadline, priority, progress, related_projects
- **skill:** name, category, proficiency_level, last_practiced, learning_resources
- **concept:** name, definition, related_concepts, context
- **file:** path, type, size, last_modified, related_project
- **conversation:** session_id, topic, participants, summary, key_decisions

### Relationship Record

Represents an edge in the knowledge graph.

**Fields:**

- `id` — Unique identifier (UUID).
- `source_entity_id` — The entity the relationship starts from.
- `target_entity_id` — The entity the relationship points to.
- `relationship_type` — The type of relationship (works_on, uses, related_to, collaborates, depends_on, learns, etc.).
- `encrypted_properties` — Relationship-specific properties (encrypted JSON).
- `weight` — Strength of the relationship (0.0-1.0).
- `created_at` — When the relationship was created.
- `updated_at` — When the relationship was last updated.

**Relationship types:**

- works_on: person → project
- uses: project → technology
- collaborates: person → person
- depends_on: project → technology
- related_to: research → technology
- learns: person → skill
- serves: project → goal
- references: conversation → project/technology
- generated_by: research → conversation
- stores: file → project

### Learning Record

Tracks your learning progress on a skill or topic.

**Fields:**

- `id` — Unique identifier (UUID).
- `skill_id` — Reference to the skill entity.
- `activity` — What you did (studied, practiced, built, read).
- `duration_minutes` — How long you spent.
- `proficiency_change` — How your proficiency changed (-1.0 to 1.0).
- `notes` — What you learned or observed.
- `source` — Where the learning came from (conversation, project, research).
- `created_at` — When the learning occurred.

### Project Record

Tracks a project's lifecycle and status.

**Fields:**

- `id` — Unique identifier (UUID).
- `entity_id` — Reference to the project entity in the knowledge graph.
- `status` — Current status: idea, planning, active, paused, completed, abandoned.
- `priority` — Priority level: low, medium, high, critical.
- `start_date` — When the project started.
- `deadline` — When the project is due (optional).
- `progress` — Completion percentage (0-100).
- `encrypted_description` — Detailed project description, encrypted.
- `encrypted_tasks` — List of tasks, encrypted.
- `encrypted_milestones` — Key milestones, encrypted.
- `repository_path` — Local git repository path (if applicable).
- `created_at` — When the project was created.
- `updated_at` — When the project was last updated.

### Goal Record

Tracks your goals and their alignment with activities.

**Fields:**

- `id` — Unique identifier (UUID).
- `entity_id` — Reference to the goal entity in the knowledge graph.
- `description` — What you want to achieve.
- `deadline` — When you want to achieve it by.
- `priority` — Priority level: low, medium, high, critical.
- `progress` — Completion percentage (0-100).
- `related_projects` — List of project IDs that serve this goal.
- `related_skills` — List of skill IDs needed for this goal.
- `encrypted_notes` — Additional notes, encrypted.
- `created_at` — When the goal was created.
- `updated_at` — When the goal was last updated.

---

## API Design

### Knowledge Graph Endpoints

**Query entities**

- Method: POST
- Path: /knowledge/query
- Request body: type (optional), name_contains (optional), properties (optional), limit (default 20)
- Response: list of matching entities

**Get entity details**

- Method: GET
- Path: /knowledge/entity/{entity_id}
- Response: full entity details with relationships

**Get entity relationships**

- Method: GET
- Path: /knowledge/entity/{entity_id}/relationships
- Query parameters: relationship_type (optional), direction (in, out, both), limit
- Response: list of related entities with relationship details

**Create entity**

- Method: POST
- Path: /knowledge/entity
- Request body: type, name, properties (optional)
- Response: created entity details

**Update entity**

- Method: PUT
- Path: /knowledge/entity/{entity_id}
- Request body: properties to update
- Response: updated entity details

**Delete entity**

- Method: DELETE
- Path: /knowledge/entity/{entity_id}
- Response: confirmation
- Behavior: Removes the entity and all its relationships.

**Create relationship**

- Method: POST
- Path: /knowledge/relationship
- Request body: source_entity_id, target_entity_id, relationship_type, properties (optional), weight (optional)
- Response: created relationship details

**Delete relationship**

- Method: DELETE
- Path: /knowledge/relationship/{relationship_id}
- Response: confirmation

**Search knowledge graph**

- Method: POST
- Path: /knowledge/search
- Request body: query (string), entity_types (optional), max_depth (optional, default 2)
- Response: list of matching entities with their relationships
- Behavior: Performs a graph search starting from entities that match the query, expanding relationships up to max_depth hops.

### Context Engine Endpoints

**Get context for conversation**

- Method: POST
- Path: /knowledge/context
- Request body: message (string), conversation_history (optional), max_tokens (optional)
- Response: context summary, relevant entities, relevant memories, relevant research
- Behavior: Analyzes the message, identifies relevant entities, retrieves related information, and prepares context for the LLM.

**Update context preferences**

- Method: PUT
- Path: /knowledge/context/preferences
- Request body: max_memories (optional), max_research (optional), include_projects (optional), include_goals (optional)
- Response: updated preferences
- Behavior: Configures how much context to load and what types of information to include.

### Learning Tracker Endpoints

**Log a learning activity**

- Method: POST
- Path: /knowledge/learning
- Request body: skill_name, activity, duration_minutes, notes (optional), source (optional)
- Response: learning record details, updated proficiency
- Behavior: Logs the activity, updates skill proficiency, creates/updates relationships in the knowledge graph.

**Get learning history**

- Method: GET
- Path: /knowledge/learning
- Query parameters: skill_name (optional), start_date (optional), end_date (optional), limit
- Response: list of learning activities

**Get skill proficiency**

- Method: GET
- Path: /knowledge/learning/skills
- Response: list of skills with proficiency levels and last practiced dates

**Get learning statistics**

- Method: GET
- Path: /knowledge/learning/stats
- Response: total_time, skills_practiced, proficiency_changes, learning_streak

### Project Tracker Endpoints

**List projects**

- Method: GET
- Path: /knowledge/projects
- Query parameters: status (optional), priority (optional), sort_by (optional)
- Response: list of projects with status, progress, and deadlines

**Get project details**

- Method: GET
- Path: /knowledge/projects/{project_id}
- Response: full project details including tasks and milestones

**Create a project**

- Method: POST
- Path: /knowledge/projects
- Request body: name, description, status, priority, start_date, deadline (optional)
- Response: created project details
- Behavior: Creates project entity in knowledge graph and project record.

**Update project**

- Method: PUT
- Path: /knowledge/projects/{project_id}
- Request body: fields to update
- Response: updated project details

**Add task to project**

- Method: POST
- Path: /knowledge/projects/{project_id}/tasks
- Request body: title, description, status, priority, due_date (optional)
- Response: updated task list

**Update task status**

- Method: PUT
- Path: /knowledge/projects/{project_id}/tasks/{task_id}
- Request body: status, notes (optional)
- Response: updated task details

**Get project context**

- Method: GET
- Path: /knowledge/projects/{project_id}/context
- Response: project details, related entities, recent activity, relevant research
- Behavior: Gathers all context related to a project for injection into conversations.

### Goal System Endpoints

**List goals**

- Method: GET
- Path: /knowledge/goals
- Query parameters: status (optional), priority (optional)
- Response: list of goals with progress and deadlines

**Create a goal**

- Method: POST
- Path: /knowledge/goals
- Request body: description, deadline, priority, related_projects (optional), related_skills (optional)
- Response: created goal details

**Update goal progress**

- Method: PUT
- Path: /knowledge/goals/{goal_id}
- Request body: progress, notes (optional)
- Response: updated goal details

**Check goal alignment**

- Method: POST
- Path: /knowledge/goals/{goal_id}/align
- Request body: activity_description (string)
- Response: alignment_score (0.0-1.0), explanation, suggestions
- Behavior: Evaluates whether a proposed activity aligns with the goal.

**Get goal recommendations**

- Method: GET
- Path: /knowledge/goals/recommendations
- Response: suggested activities based on current goals and progress
- Behavior: Analyzes your goals and suggests what to work on next.

### Relationship Mapper Endpoints

**Get people**

- Method: GET
- Path: /knowledge/people
- Query parameters: name_contains (optional), project_id (optional)
- Response: list of people with their relationships

**Get project collaborators**

- Method: GET
- Path: /knowledge/projects/{project_id}/people
- Response: list of people involved in the project

**Map relationship**

- Method: POST
- Path: /knowledge/people/{person_id}/relationship
- Request body: target_person_id, relationship_type, notes (optional)
- Response: created relationship details

---

## Implementation Details

### Step 1: Knowledge Graph Store

**Graph storage approach**

Phase 5 uses an adjacency list approach in the existing database rather than a dedicated graph database. This keeps the technology stack simpler while still supporting graph queries.

For each entity:
- Store the entity record in an `entities` table
- Store relationships in a `relationships` table
- Use foreign keys to link entities and relationships

**Graph queries**

Implement common graph queries using SQL:
- Find all entities of a type
- Find all relationships from/to an entity
- Find entities within N hops of a starting entity
- Find paths between two entities
- Find communities or clusters of related entities

**Performance considerations**

For small to medium knowledge bases (under 100,000 entities), SQL-based graph queries are sufficient. For larger graphs, consider:
- Caching frequently accessed subgraphs
- Pre-computing common traversals
- Migrating to a dedicated graph database (Neo4j, ArangoDB)

### Step 2: Entity Extractor

**Automatic entity extraction**

When content is stored (memories, research, conversations), automatically extract entities:

1. Use LLM to identify entities in the content
2. For each entity found:
   - Check if it already exists in the knowledge graph
   - If not, create a new entity
   - Create relationships between the new entity and the source content
3. Update entity properties if new information is available

**Entity types extraction**

- Person names → person entities
- Project names → project entities
- Technology names → technology entities
- Skill mentions → skill entities
- Goal statements → goal entities
- File paths → file entities

**Relationship extraction**

Identify relationships between entities:
- "I'm working on MYSTI" → person works_on project
- "MYSTI uses Docker" → project uses technology
- "I'm learning cybersecurity" → person learns skill
- "This research is about PQC" → research related_to technology

**Manual entity management**

In addition to automatic extraction, allow manual entity creation:
- "Remember that Alice is working on Project X"
- "Add Python as a technology I know"
- "Create a goal to learn Rust by December"

### Step 3: Context Engine

**Context loading**

When a conversation starts, the Context Engine:

1. Analyzes the initial message for entity mentions
2. Query the knowledge graph for those entities
3. Retrieve related memories (from Phase 1)
4. Retrieve related research (from Phase 2)
5. Retrieve related projects and goals (from Phase 5)
6. Compile all context into a structured format
7. Inject into the LLM conversation

**Context prioritization**

Not all context is equally relevant. Prioritize by:
- Direct relevance to the conversation topic
- Recency (more recent information is more relevant)
- Importance (high-priority projects and goals first)
- Type (memories about the topic > general project info > related research)

**Context size management**

LLMs have limited context windows. The Context Engine must:
- Estimate token count for each context item
- Fit as much relevant context as possible
- Prioritize high-relevance items when space is limited
- Summarize lower-priority items to save space

**Context caching**

Cache frequently used context to avoid repeated queries:
- Project context (changes infrequently)
- Person information (changes rarely)
- Skill levels (change slowly)
- Cache invalidation when entities are updated

### Step 4: Learning Tracker

**Proficiency model**

Track skill proficiency on a scale from 0 to 10:
- 0: No knowledge
- 1-3: Beginner (basic understanding)
- 4-6: Intermediate (can apply knowledge)
- 7-8: Advanced (can teach others)
- 9-10: Expert (can innovate)

**Proficiency updates**

When you log a learning activity:
1. Identify the skill involved
2. Determine the proficiency change based on:
   - Activity type (reading: +0.1, practicing: +0.2, building: +0.3, teaching: +0.4)
   - Duration (longer sessions have more impact)
   - Difficulty (challenging activities improve more)
3. Update the skill's proficiency level
4. Record the learning activity

**Skill decay**

Skills degrade over time without practice:
- Apply exponential decay to proficiency levels
- Decay rate depends on skill type (motor skills decay faster than conceptual knowledge)
- Revisiting a skill resets the decay timer
- Track last practiced date

**Learning recommendations**

Based on your goals and current proficiency:
- Identify skills needed for your goals
- Compare against current proficiency levels
- Recommend which skills to practice next
- Suggest learning resources (from research)

### Step 5: Project Tracker

**Project lifecycle**

Track projects through their lifecycle:
1. **Idea** — Initial concept, not yet started
2. **Planning** — Defining scope, tasks, and timeline
3. **Active** — Currently working on
4. **Paused** — Temporarily suspended
5. **Completed** — Finished
6. **Abandoned** — No longer pursuing

**Task management**

Each project has a list of tasks:
- Task title and description
- Task status: todo, in_progress, done
- Task priority: low, medium, high
- Task due date (optional)
- Task dependencies (optional)

**Progress tracking**

Calculate project progress based on:
- Percentage of tasks completed
- Weighted by task priority
- Updated automatically when task statuses change

**Milestone tracking**

Track key milestones:
- Milestone name and description
- Target date
- Completion status
- Related tasks

**Project context**

When discussing a project, automatically load:
- Project status and progress
- Recent tasks and changes
- Related technologies
- Related research findings
- Related people
- Active goals

### Step 6: Goal System

**Goal definition**

Goals are defined with:
- Clear description of what you want to achieve
- Deadline (optional but recommended)
- Priority level
- Related projects (what work serves this goal)
- Related skills (what you need to learn)
- Progress tracking

**Alignment checking**

When you propose an activity, the Goal System can evaluate alignment:
1. Analyze the proposed activity
2. Compare against active goals
3. Calculate alignment score (0.0-1.0)
4. Explain why the activity does or doesn't serve your goals
5. Suggest alternatives if alignment is low

**Goal recommendations**

Based on your current goals and progress:
- Identify which goals are behind schedule
- Suggest activities that advance multiple goals
- Prioritize high-impact activities
- Warn about approaching deadlines

**Goal review**

Periodically review goals:
- Are you making progress?
- Are goals still relevant?
- Should priorities change?
- Are new goals needed?

---

## Dependencies

### New Dependencies for Phase 5

No major new dependencies. Phase 5 uses existing infrastructure:
- SQLAlchemy — New models for entities, relationships, learning, projects, goals
- Alembic — New migrations

### Existing Dependencies Used

- sentence-transformers — For embedding entities for search
- FAISS — For semantic search on entities
- FastAPI — New endpoints

---

## Testing

### Unit Tests

**Knowledge graph tests**
- Test entity creation and retrieval
- Test relationship creation and traversal
- Test graph queries (find all X related to Y)
- Test entity deduplication

**Entity extraction tests**
- Test automatic entity identification
- Test relationship extraction
- Test entity type classification

**Context engine tests**
- Test context loading for conversations
- Test context prioritization
- Test context size management

**Learning tracker tests**
- Test proficiency calculation
- Test skill decay
- Test learning recommendations

**Project tracker tests**
- Test project lifecycle management
- Test task management
- Test progress calculation

**Goal system tests**
- Test alignment checking
- Test goal recommendations

### Integration Tests

**End-to-end knowledge flow**
- Store a memory about a project → extract entities → query knowledge graph → verify relationships
- Start a conversation → load context → verify relevant information is included
- Log a learning activity → update proficiency → verify skill level changed

### Manual Testing

After Phase 5 is complete:
- Create entities manually and verify the knowledge graph
- Have conversations and check if context is loaded correctly
- Track learning progress and verify proficiency updates
- Create a project and track its progress
- Define goals and check alignment recommendations

---

## Edge Cases

### Entity Ambiguity

If the same name refers to different entities:
- Use context to disambiguate
- Allow manual merging of duplicate entities
- Track entity confidence scores

### Context Overflow

If the knowledge graph is too large to load all relevant context:
- Prioritize by relevance and recency
- Summarize lower-priority items
- Cache frequently used context

### Circular Relationships

If the knowledge graph contains cycles:
- Detect and handle cycles in graph traversal
- Set maximum depth for graph queries
- Warn about potential cycles

### Stale Data

If entities become outdated:
- Track last updated timestamps
- Periodically refresh entity information
- Flag entities that haven't been updated recently

---

## Deliverables

When Phase 5 is complete, you will have:

1. **Knowledge graph** — Entity-relationship store connecting all your information.

2. **Entity extraction** — Automatic identification of entities from content.

3. **Context engine** — Automatic loading of relevant context into conversations.

4. **Learning tracker** — Skill proficiency tracking with recommendations.

5. **Project tracker** — Project lifecycle management with tasks and milestones.

6. **Goal system** — Goal definition with alignment checking and recommendations.

7. **Relationship mapper** — People and their connections to projects and topics.

---

## What Comes Next

After Phase 5, you will move to **Phase 6: Self-Improvement Loop**, which adds:
- Model registry and benchmarking
- Update recommendations
- Sandbox testing for new models
- Deployment workflow
- Configuration optimization

Phase 5's knowledge graph will be useful in Phase 6 — the learning tracker and project context can inform which models are best for your specific use cases.

---

*Phase 5 transforms MYSTI from a collection of tools into an intelligent knowledge system.*
