from __future__ import annotations
from dataclasses import dataclass, field
@dataclass
class TestResult:
    success: bool; tests_passed: int=0; tests_failed: int=0; performance_impact: dict=field(default_factory=dict); errors: list[str]=field(default_factory=list)
class SandboxTester:
    async def test_config_change(self,config): return TestResult(bool(isinstance(config,dict)),1 if isinstance(config,dict) else 0,0 if isinstance(config,dict) else 1,errors=[] if isinstance(config,dict) else ["config must be a mapping"])
    async def test_model_update(self,model): return TestResult(bool(model),1 if model else 0,0 if model else 1,errors=[] if model else ["model is required"])
    async def test_tool_addition(self,tool_config): return TestResult(bool(isinstance(tool_config,dict) and tool_config.get("name")),1 if isinstance(tool_config,dict) and tool_config.get("name") else 0,0 if isinstance(tool_config,dict) and tool_config.get("name") else 1,errors=[] if isinstance(tool_config,dict) and tool_config.get("name") else ["tool name is required"])