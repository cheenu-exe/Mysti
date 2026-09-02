"""Comprehensive tests for Phase 5: Knowledge Integration."""

import pytest
from uuid import uuid4

from mysti.integration.knowledge_graph import Entity, KnowledgeGraph, Relationship
from mysti.integration.extraction import EntityExtractor
from mysti.integration.context import ContextBuilder
from mysti.integration.learning import LearningItem, LearningTracker
from mysti.integration.projects import Project, ProjectTracker, Task, Milestone
from mysti.integration.goals import Goal, GoalSystem


# --- Knowledge Graph Tests ---

@pytest.mark.asyncio
async def test_knowledge_graph_add_and_get_entity(tmp_path):
    graph = KnowledgeGraph(str(tmp_path / "graph"))
    entity = Entity(name="Python", type="concept", attributes={"lang": "programming"})
    entity_id = await graph.add_entity(entity)
    retrieved = await graph.get_entity(entity_id)
    assert retrieved.name == "Python"
    assert retrieved.type == "concept"
    assert retrieved.attributes["lang"] == "programming"


@pytest.mark.asyncio
async def test_knowledge_graph_deduplication(tmp_path):
    graph = KnowledgeGraph(str(tmp_path / "graph"))
    await graph.add_entity(Entity(name="Alice", type="person"))
    await graph.add_entity(Entity(name="Alice", type="person", attributes={"updated": True}))
    assert len(graph.entities) == 1
    alice = next(e for e in graph.entities.values() if e.name == "Alice")
    assert alice.attributes.get("updated") is True


@pytest.mark.asyncio
async def test_knowledge_graph_relationships(tmp_path):
    graph = KnowledgeGraph(str(tmp_path / "graph"))
    alice = Entity(name="Alice", type="person")
    bob = Entity(name="Bob", type="person")
    await graph.add_entity(alice)
    await graph.add_entity(bob)
    rel = Relationship(source_id=alice.id, target_id=bob.id, type="knows", weight=0.8)
    await graph.add_relationship(rel)
    rels = await graph.get_relationships(str(alice.id))
    assert len(rels) == 1
    assert rels[0].type == "knows"
    assert rels[0].weight == 0.8


@pytest.mark.asyncio
async def test_knowledge_graph_find_path(tmp_path):
    graph = KnowledgeGraph(str(tmp_path / "graph"))
    a = Entity(name="A", type="concept")
    b = Entity(name="B", type="concept")
    c = Entity(name="C", type="concept")
    await graph.add_entity(a)
    await graph.add_entity(b)
    await graph.add_entity(c)
    await graph.add_relationship(Relationship(source_id=a.id, target_id=b.id, type="related"))
    await graph.add_relationship(Relationship(source_id=b.id, target_id=c.id, type="related"))
    path = await graph.find_path(str(a.id), str(c.id))
    assert len(path) == 3
    assert path[0] == str(a.id)
    assert path[-1] == str(c.id)


@pytest.mark.asyncio
async def test_knowledge_graph_search(tmp_path):
    graph = KnowledgeGraph(str(tmp_path / "graph"))
    await graph.add_entity(Entity(name="Machine Learning", type="concept"))
    await graph.add_entity(Entity(name="Deep Learning", type="concept"))
    await graph.add_entity(Entity(name="Python", type="tool"))
    results = await graph.search("learning")
    assert len(results) == 2


@pytest.mark.asyncio
async def test_knowledge_graph_get_context(tmp_path):
    graph = KnowledgeGraph(str(tmp_path / "graph"))
    entity = Entity(name="MYSTI", type="project")
    await graph.add_entity(entity)
    context = await graph.get_context(str(entity.id))
    assert "entity" in context
    assert "relationships" in context
    assert context["entity"].name == "MYSTI"


# --- Entity Extraction Tests ---

@pytest.mark.asyncio
async def test_entity_extractor_no_llm():
    extractor = EntityExtractor(llm=None)
    result = await extractor.extract_from_text("Alice works on MYSTI")
    assert result == {"entities": [], "relationships": []}


@pytest.mark.asyncio
async def test_entity_extractor_with_mock_llm(tmp_path):
    class MockLLM:
        async def complete(self, messages):
            return '{"entities": [{"name": "Alice", "type": "person"}], "relationships": []}'
    
    graph = KnowledgeGraph(str(tmp_path / "graph"))
    extractor = EntityExtractor(llm=MockLLM(), graph=graph)
    result = await extractor.extract_from_text("Alice works on MYSTI")
    assert len(result["entities"]) == 1
    assert result["entities"][0]["name"] == "Alice"
    # Note: extract_from_text doesn't store in graph, only extract_and_store does
    assert len(graph.entities) == 0


@pytest.mark.asyncio
async def test_entity_extractor_store_and_link(tmp_path):
    class MockLLM:
        async def complete(self, messages):
            return '{"entities": [{"name": "Alice", "type": "person"}, {"name": "MYSTI", "type": "project"}], "relationships": [{"source": "Alice", "target": "MYSTI", "type": "works_on"}]}'
    
    graph = KnowledgeGraph(str(tmp_path / "graph"))
    extractor = EntityExtractor(llm=MockLLM(), graph=graph)
    result = await extractor.extract_and_store("Alice works on MYSTI", "source-123")
    assert len(graph.entities) == 2
    assert len(graph.relationships) == 1


@pytest.mark.asyncio
async def test_entity_extractor_invalid_json(tmp_path):
    class MockLLM:
        async def complete(self, messages):
            return 'not valid json'
    
    extractor = EntityExtractor(llm=MockLLM())
    result = await extractor.extract_from_text("Some text")
    assert result == {"entities": [], "relationships": []}


# --- Context Builder Tests ---

@pytest.mark.asyncio
async def test_context_builder_system_prompt():
    builder = ContextBuilder()
    prompt = await builder.build_system_prompt()
    assert "MYSTI" in prompt
    assert "assistant" in prompt.lower()


@pytest.mark.asyncio
async def test_context_builder_build_context():
    builder = ContextBuilder(memory=None, graph=None)
    conversation = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"}
    ]
    context = await builder.build_context("greeting", conversation)
    assert "[Relevant Memories]" in context
    assert "[Related Entities]" in context
    assert "[Recent Conversation]" in context
    assert "User: Hello" in context
    assert "Assistant: Hi there!" in context


@pytest.mark.asyncio
async def test_context_builder_max_chars():
    builder = ContextBuilder(max_chars=100)
    conversation = [{"role": "user", "content": "x" * 200}]
    context = await builder.build_context("test", conversation)
    assert len(context) <= 100


# --- Learning Tracker Tests ---

@pytest.mark.asyncio
async def test_learning_tracker_add_and_get(tmp_path):
    tracker = LearningTracker(str(tmp_path / "learning.json"))
    item = LearningItem(topic="Python", skill_level=7, resources=["docs.python.org"])
    await tracker.add_learning_item(item)
    items = await tracker.get_learning_items()
    assert len(items) == 1
    assert items[0].topic == "Python"
    assert items[0].skill_level == 7


@pytest.mark.asyncio
async def test_learning_tracker_update_progress(tmp_path):
    tracker = LearningTracker(str(tmp_path / "learning.json"))
    await tracker.add_learning_item(LearningItem(topic="Python", skill_level=3))
    await tracker.update_progress("Python", 7, "Finished tutorial")
    items = await tracker.get_learning_items()
    assert items[0].skill_level == 7
    assert "Finished tutorial" in items[0].notes


@pytest.mark.asyncio
async def test_learning_tracker_gaps(tmp_path):
    tracker = LearningTracker(str(tmp_path / "learning.json"))
    await tracker.add_learning_item(LearningItem(topic="Python", skill_level=8))
    await tracker.add_learning_item(LearningItem(topic="Rust", skill_level=3))
    gaps = await tracker.get_gaps()
    assert len(gaps) == 1
    assert gaps[0]["topic"] == "Rust"


@pytest.mark.asyncio
async def test_learning_tracker_suggest_resources(tmp_path):
    tracker = LearningTracker(str(tmp_path / "learning.json"))
    suggestions = await tracker.suggest_resources("Python")
    assert len(suggestions) == 2
    assert suggestions[0]["type"] == "tutorial"
    assert suggestions[1]["type"] == "project"


# --- Project Tracker Tests ---

@pytest.mark.asyncio
async def test_project_tracker_create_and_get(tmp_path):
    tracker = ProjectTracker(str(tmp_path / "projects"))
    project = Project(name="MYSTI", description="Personal AI assistant")
    project_id = await tracker.create_project(project)
    retrieved = await tracker.get_project(project_id)
    assert retrieved.name == "MYSTI"
    assert retrieved.description == "Personal AI assistant"


@pytest.mark.asyncio
async def test_project_tracker_add_task(tmp_path):
    tracker = ProjectTracker(str(tmp_path / "projects"))
    project = Project(name="MYSTI")
    project_id = await tracker.create_project(project)
    task = Task(title="Implement encryption", priority=1)
    await tracker.add_task(project_id, task)
    retrieved = await tracker.get_project(project_id)
    assert len(retrieved.tasks) == 1
    assert retrieved.tasks[0].title == "Implement encryption"


@pytest.mark.asyncio
async def test_project_tracker_update_task(tmp_path):
    tracker = ProjectTracker(str(tmp_path / "projects"))
    project = Project(name="MYSTI")
    project_id = await tracker.create_project(project)
    task = Task(title="Implement encryption")
    await tracker.add_task(project_id, task)
    await tracker.update_task(project_id, str(task.id), {"status": "done"})
    retrieved = await tracker.get_project(project_id)
    assert retrieved.tasks[0].status == "done"


@pytest.mark.asyncio
async def test_project_tracker_update_project(tmp_path):
    tracker = ProjectTracker(str(tmp_path / "projects"))
    project = Project(name="MYSTI")
    project_id = await tracker.create_project(project)
    await tracker.update_project(project_id, {"description": "Updated description"})
    retrieved = await tracker.get_project(project_id)
    assert retrieved.description == "Updated description"


@pytest.mark.asyncio
async def test_project_tracker_list_projects(tmp_path):
    tracker = ProjectTracker(str(tmp_path / "projects"))
    await tracker.create_project(Project(name="Project A", status="active"))
    await tracker.create_project(Project(name="Project B", status="completed"))
    active = await tracker.list_projects(status="active")
    assert len(active) == 1
    assert active[0].name == "Project A"


# --- Goal System Tests ---

@pytest.mark.asyncio
async def test_goal_system_create_and_get(tmp_path):
    system = GoalSystem(str(tmp_path / "goals"))
    goal = Goal(title="Learn Rust", category="learning", progress=25)
    goal_id = await system.create_goal(goal)
    retrieved = await system.get_goal(goal_id)
    assert retrieved.title == "Learn Rust"
    assert retrieved.progress == 25


@pytest.mark.asyncio
async def test_goal_system_update_goal(tmp_path):
    system = GoalSystem(str(tmp_path / "goals"))
    goal = Goal(title="Learn Rust")
    goal_id = await system.create_goal(goal)
    await system.update_goal(goal_id, {"progress": 75, "status": "active"})
    retrieved = await system.get_goal(goal_id)
    assert retrieved.progress == 75


@pytest.mark.asyncio
async def test_goal_system_list_goals(tmp_path):
    system = GoalSystem(str(tmp_path / "goals"))
    await system.create_goal(Goal(title="Learn Rust", category="learning"))
    await system.create_goal(Goal(title="Build MYSTI", category="project"))
    learning_goals = await system.list_goals(category="learning")
    assert len(learning_goals) == 1
    assert learning_goals[0].category == "learning"


@pytest.mark.asyncio
async def test_goal_system_progress_report(tmp_path):
    system = GoalSystem(str(tmp_path / "goals"))
    await system.create_goal(Goal(title="Goal 1", progress=50))
    await system.create_goal(Goal(title="Goal 2", progress=100))
    report = await system.get_progress_report()
    assert report["total"] == 2
    assert report["overall_progress"] == 75


# --- Integration Tests ---

@pytest.mark.asyncio
async def test_full_knowledge_integration(tmp_path):
    """Test complete knowledge integration workflow."""
    # Setup
    graph = KnowledgeGraph(str(tmp_path / "graph"))
    learning = LearningTracker(str(tmp_path / "learning.json"))
    projects = ProjectTracker(str(tmp_path / "projects"))
    goals = GoalSystem(str(tmp_path / "goals"))
    context_builder = ContextBuilder(graph=graph)
    
    # Add entities to graph
    alice = Entity(name="Alice", type="person", attributes={"role": "developer"})
    mysti = Entity(name="MYSTI", type="project", attributes={"status": "active"})
    await graph.add_entity(alice)
    await graph.add_entity(mysti)
    await graph.add_relationship(Relationship(source_id=alice.id, target_id=mysti.id, type="works_on"))
    
    # Track learning
    await learning.add_learning_item(LearningItem(topic="Python", skill_level=8))
    await learning.add_learning_item(LearningItem(topic="Cryptography", skill_level=5))
    
    # Track project
    project = Project(name="MYSTI", description="Personal AI assistant")
    project_id = await projects.create_project(project)
    await projects.add_task(project_id, Task(title="Implement encryption", status="done"))
    await projects.add_task(project_id, Task(title="Add research agent", status="in_progress"))
    
    # Track goals
    await goals.create_goal(Goal(title="Complete MYSTI", category="project", progress=40))
    
    # Build context
    context = await context_builder.build_context("MYSTI project", [{"role": "user", "content": "Tell me about MYSTI"}])
    # Context should contain conversation and system info
    assert "MYSTI" in context or "User" in context
    
    # Verify all data persisted
    assert len(graph.entities) == 2
    assert len(await learning.get_learning_items()) == 2
    assert len((await projects.get_project(project_id)).tasks) == 2
    assert (await goals.get_progress_report())["total"] == 1
