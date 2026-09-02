"""Comprehensive tests for Phase 6: Self-Improvement."""

import pytest
from uuid import uuid4

from mysti.improve.registry import ModelEntry, ModelRegistry
from mysti.improve.benchmarks import BenchmarkRunner, BenchmarkTask, BenchmarkResult
from mysti.improve.recommender import UpdateRecommender, Recommendation
from mysti.improve.sandbox_tester import SandboxTester, TestResult


# --- Model Registry Tests ---

@pytest.mark.asyncio
async def test_registry_register_and_get(tmp_path):
    registry = ModelRegistry(tmp_path / "models.json")
    model = ModelEntry(
        name="deepseek-v4",
        provider="deepseek",
        model_id="deepseek-v4-flash",
        cost_per_1k_tokens=0.0,
        context_window=8192,
        strengths=["coding", "analysis"],
        avg_quality_score=8.5
    )
    await registry.register_model(model)
    retrieved = await registry.get_model("deepseek-v4")
    assert retrieved.name == "deepseek-v4"
    assert retrieved.provider == "deepseek"
    assert retrieved.cost_per_1k_tokens == 0.0


@pytest.mark.asyncio
async def test_registry_list_models(tmp_path):
    registry = ModelRegistry(tmp_path / "models.json")
    await registry.register_model(ModelEntry("model-a", "openai", "gpt-4"))
    await registry.register_model(ModelEntry("model-b", "anthropic", "claude-3"))
    models = await registry.list_models()
    assert len(models) == 2
    names = [m.name for m in models]
    assert "model-a" in names
    assert "model-b" in names


@pytest.mark.asyncio
async def test_registry_compare_models(tmp_path):
    registry = ModelRegistry(tmp_path / "models.json")
    await registry.register_model(ModelEntry("fast", "local", "f", avg_response_time=0.1))
    await registry.register_model(ModelEntry("slow", "local", "s", avg_response_time=2.0))
    comparison = await registry.compare_models(["fast", "slow"])
    assert "fast" in comparison
    assert "slow" in comparison
    assert comparison["fast"]["avg_response_time"] == 0.1


@pytest.mark.asyncio
async def test_registry_get_recommendation(tmp_path):
    registry = ModelRegistry(tmp_path / "models.json")
    await registry.register_model(ModelEntry(
        "coding-model", "local", "m1",
        strengths=["coding"], avg_quality_score=9.0, cost_per_1k_tokens=0.0
    ))
    await registry.register_model(ModelEntry(
        "general-model", "local", "m2",
        strengths=["conversation"], avg_quality_score=7.0, cost_per_1k_tokens=0.0
    ))
    best = await registry.get_recommendation("coding")
    assert best.name == "coding-model"


@pytest.mark.asyncio
async def test_registry_recommendation_empty_raises(tmp_path):
    registry = ModelRegistry(tmp_path / "models.json")
    with pytest.raises(LookupError, match="no models"):
        await registry.get_recommendation("coding")


@pytest.mark.asyncio
async def test_registry_persistence(tmp_path):
    path = tmp_path / "models.json"
    registry1 = ModelRegistry(path)
    await registry1.register_model(ModelEntry("persistent", "local", "p"))
    registry2 = ModelRegistry(path)
    retrieved = await registry2.get_model("persistent")
    assert retrieved.name == "persistent"


# --- Benchmark Runner Tests ---

class MockLLM:
    def __init__(self, response="test response"):
        self.response = response
    async def complete(self, messages, model=None):
        return self.response


@pytest.mark.asyncio
async def test_benchmark_run_single_task():
    llm = MockLLM("The answer is 42")
    runner = BenchmarkRunner(models={"test-model": llm})
    task = BenchmarkTask(name="math", input="What is 6*7?", expected_output="42")
    results = await runner.run_benchmark("test-model", [task])
    assert len(results) == 1
    assert results[0].model == "test-model"
    assert results[0].quality_score == 10.0  # expected output found


@pytest.mark.asyncio
async def test_benchmark_quality_scoring():
    llm = MockLLM("Hello world")
    runner = BenchmarkRunner(models={"model": llm})
    task_match = BenchmarkTask(name="t1", input="hi", expected_output="hello")
    task_no_match = BenchmarkTask(name="t2", input="hi", expected_output="goodbye")
    results = await runner.run_benchmark("model", [task_match, task_no_match])
    assert results[0].quality_score == 10.0
    assert results[1].quality_score == 5.0


@pytest.mark.asyncio
async def test_benchmark_run_all_models():
    models = {
        "fast": MockLLM("fast response"),
        "slow": MockLLM("slow response"),
    }
    runner = BenchmarkRunner(models=models)
    task = BenchmarkTask(name="t", input="test")
    all_results = await runner.run_all_models([task])
    assert "fast" in all_results
    assert "slow" in all_results
    assert len(all_results["fast"]) == 1


@pytest.mark.asyncio
async def test_benchmark_leaderboard():
    llm = MockLLM("response")
    runner = BenchmarkRunner(models={"model-a": llm, "model-b": llm})
    await runner.run_benchmark("model-a", [BenchmarkTask(name="t1", input="hi")])
    await runner.run_benchmark("model-b", [BenchmarkTask(name="t2", input="hi")])
    leaderboard = await runner.get_leaderboard()
    assert len(leaderboard) == 2
    assert all("model" in entry for entry in leaderboard)
    assert all("quality_score" in entry for entry in leaderboard)


@pytest.mark.asyncio
async def test_benchmark_generate_report():
    llm = MockLLM("response")
    runner = BenchmarkRunner(models={"model": llm})
    await runner.run_benchmark("model", [BenchmarkTask(name="t", input="test")])
    report = await runner.generate_report()
    assert "leaderboard" in report
    assert "tasks" in report
    assert report["tasks"] == 1


# --- Update Recommender Tests ---

@pytest.mark.asyncio
async def test_recommender_analyze_empty_config(tmp_path):
    recommender = UpdateRecommender(config={}, path=str(tmp_path / "rec.json"))
    recs = await recommender.get_recommendations()
    assert len(recs) >= 1
    assert any("LLM" in r.title or "llm" in r.title.lower() for r in recs)


@pytest.mark.asyncio
async def test_recommender_analyze_configured(tmp_path):
    recommender = UpdateRecommender(config={"llm_provider": "deepseek"}, path=str(tmp_path / "rec.json"))
    recs = await recommender.get_recommendations()
    # No LLM warning should not appear
    llm_recs = [r for r in recs if "LLM" in r.title]
    assert len(llm_recs) == 0


@pytest.mark.asyncio
async def test_recommender_apply(tmp_path):
    config = {}
    recommender = UpdateRecommender(config=config, path=str(tmp_path / "rec.json"))
    recs = await recommender.get_recommendations()
    rec = recs[0]
    result = await recommender.apply_recommendation(str(rec.id))
    assert result is True


@pytest.mark.asyncio
async def test_recommender_apply_nonexistent(tmp_path):
    recommender = UpdateRecommender(config={}, path=str(tmp_path / "rec.json"))
    result = await recommender.apply_recommendation(str(uuid4()))
    assert result is False


@pytest.mark.asyncio
async def test_recommendation_dataclass():
    rec = Recommendation(
        type="config",
        priority="high",
        title="Test",
        description="Test recommendation",
        reason="Testing"
    )
    assert rec.type == "config"
    assert rec.priority == "high"
    assert rec.id is not None


# --- Sandbox Tester Tests ---

@pytest.mark.asyncio
async def test_sandbox_tester_config_change():
    tester = SandboxTester()
    result = await tester.test_config_change({"llm_provider": "deepseek"})
    assert result.success is True
    assert result.tests_passed == 1


@pytest.mark.asyncio
async def test_sandbox_tester_config_change_invalid():
    tester = SandboxTester()
    result = await tester.test_config_change("not a dict")
    assert result.success is False
    assert result.tests_failed == 1


@pytest.mark.asyncio
async def test_sandbox_tester_model_update():
    tester = SandboxTester()
    result = await tester.test_model_update("gpt-4")
    assert result.success is True


@pytest.mark.asyncio
async def test_sandbox_tester_model_update_empty():
    tester = SandboxTester()
    result = await tester.test_model_update("")
    assert result.success is False


@pytest.mark.asyncio
async def test_sandbox_tester_tool_addition():
    tester = SandboxTester()
    result = await tester.test_tool_addition({"name": "filesystem", "description": "File ops"})
    assert result.success is True


@pytest.mark.asyncio
async def test_sandbox_tester_tool_addition_no_name():
    tester = SandboxTester()
    result = await tester.test_tool_addition({"description": "Missing name"})
    assert result.success is False


@pytest.mark.asyncio
async def test_test_result_dataclass():
    result = TestResult(
        success=True,
        tests_passed=5,
        tests_failed=0,
        performance_impact={"cpu": "low"},
        errors=[]
    )
    assert result.success is True
    assert result.tests_passed == 5
    assert result.performance_impact["cpu"] == "low"


# --- Integration Tests ---

@pytest.mark.asyncio
async def test_full_improvement_workflow(tmp_path):
    """Test complete self-improvement workflow."""
    # 1. Register models
    registry = ModelRegistry(tmp_path / "models.json")
    await registry.register_model(ModelEntry(
        name="deepseek-v4",
        provider="deepseek",
        model_id="deepseek-v4-flash",
        strengths=["coding", "analysis"],
        avg_quality_score=8.5,
        cost_per_1k_tokens=0.0
    ))
    await registry.register_model(ModelEntry(
        name="local-llama",
        provider="ollama",
        model_id="llama3.1",
        strengths=["conversation"],
        avg_quality_score=7.0,
        cost_per_1k_tokens=0.0
    ))

    # 2. Run benchmarks
    models = {
        "deepseek-v4": MockLLM("deepseek response"),
        "local-llama": MockLLM("llama response"),
    }
    runner = BenchmarkRunner(models=models, registry=registry)
    tasks = [
        BenchmarkTask(name="coding", input="Write a function", expected_output="def"),
        BenchmarkTask(name="analysis", input="Analyze this data", expected_output="insight"),
    ]
    all_results = await runner.run_all_models(tasks)
    assert len(all_results) == 2

    # 3. Get recommendations
    recommender = UpdateRecommender(config={}, path=str(tmp_path / "rec.json"))
    recs = await recommender.get_recommendations()
    assert len(recs) >= 1

    # 4. Test sandbox
    tester = SandboxTester()
    config_result = await tester.test_config_change({"new_setting": "value"})
    assert config_result.success

    # 5. Generate report (use fresh runner to avoid accumulated results)
    fresh_runner = BenchmarkRunner(models=models)
    await fresh_runner.run_benchmark("deepseek-v4", [BenchmarkTask(name="t", input="test")])
    report = await fresh_runner.generate_report()
    assert report["tasks"] == 1
    assert len(report["leaderboard"]) == 1
