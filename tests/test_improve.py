import pytest
from mysti.improve.registry import ModelEntry, ModelRegistry
from mysti.improve.benchmarks import BenchmarkRunner, BenchmarkTask
from mysti.improve.recommender import UpdateRecommender
from mysti.improve.sandbox_tester import SandboxTester
class Fake:
    async def complete(self,messages,model=None): return "expected response"
@pytest.mark.asyncio
async def test_registry_and_benchmark(tmp_path):
 r=ModelRegistry(tmp_path/"models.json"); await r.register_model(ModelEntry("local","local","x",strengths=["coding"],avg_quality_score=8)); assert (await r.get_recommendation("coding")).name=="local"
 b=BenchmarkRunner({"local":Fake()}); out=await b.run_benchmark("local",[BenchmarkTask(name="x",input="hi",expected_output="expected")]); assert out[0].quality_score==10
@pytest.mark.asyncio
async def test_recommender_and_tester(tmp_path):
 rec=UpdateRecommender({},tmp_path/"r.json"); assert await rec.get_recommendations(); assert (await SandboxTester().test_config_change({})).success