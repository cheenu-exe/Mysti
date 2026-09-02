import pytest
from mysti.integration.knowledge_graph import Entity, KnowledgeGraph, Relationship
from mysti.integration.learning import LearningItem, LearningTracker
from mysti.integration.projects import Project, ProjectTracker, Task
from mysti.integration.goals import Goal, GoalSystem
from mysti.integration.context import ContextBuilder

@pytest.mark.asyncio
async def test_graph_entities_paths_and_dedup(tmp_path):
    graph = KnowledgeGraph(str(tmp_path / "graph")); a=Entity(name="Alice",type="person"); b=Entity(name="MYSTI",type="project")
    await graph.add_entity(a); await graph.add_entity(b); await graph.add_relationship(Relationship(source_id=a.id,target_id=b.id,type="works_on"))
    assert len(await graph.search("alice")) == 1 and await graph.find_path(str(a.id),str(b.id)) == [str(a.id),str(b.id)]

@pytest.mark.asyncio
async def test_context_learning_projects_goals(tmp_path):
    learning=LearningTracker(tmp_path/"learning.json"); await learning.add_learning_item(LearningItem("Python")); assert await learning.get_gaps()
    projects=ProjectTracker(tmp_path/"projects"); p=Project(name="Demo"); pid=await projects.create_project(p); await projects.add_task(pid,Task(title="Build")); assert len((await projects.get_project(pid)).tasks)==1
    goals=GoalSystem(tmp_path/"goals"); gid=await goals.create_goal(Goal(title="Learn",progress=50)); assert (await goals.get_progress_report())["overall_progress"]==50
    assert "MYSTI" in await ContextBuilder().build_system_prompt()