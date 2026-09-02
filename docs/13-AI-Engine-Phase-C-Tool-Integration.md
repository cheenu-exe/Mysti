# AI Engine Phase C: Tool Integration

## Phase Overview

Phase C wires the ToolGateway into the agent — enabling the AI to call tools (filesystem, browser, terminal, git, network) during conversations. Currently, tools exist but are never used in chat. This phase makes MYSTI actionable, not just conversational.

The Tool Integration transforms MYSTI from a chatbot that talks about doing things into an AI that actually does things.

---

## Goals and Success Criteria

### Primary Goals

1. **Create ToolExecutor class** — Execute tools during agent loop
2. **Implement FunctionCalling support** — LLM function calling format
3. **Add tool definitions to prompts** — Tell the LLM what tools are available
4. **Wire ToolGateway into AgentCore** — Use tools during conversation
5. **Add tool permission checking** — Respect trust levels
6. **Add tool execution logging** — Audit all tool calls

### Success Criteria

You know Phase C is complete when:

- AI can call tools during conversations
- Tool calls are properly formatted for the LLM
- Tool results are processed and used in responses
- Tool permissions are checked before execution
- All tool calls are logged in the audit log
- Tool failures are handled gracefully
- All existing tests still pass

---

## Architecture

### Current State (Phase A+B)

```
User Input
    ↓
AgentCore.chat()
    ↓
┌─────────────────────────────┐
│  RAG Pipeline               │
│  - Retrieve memories        │
│  - Inject into context      │
└─────────────────────────────┘
    ↓
LLM.complete(messages)
    ↓
Response
```

**Problem:** AI cannot take actions. It can only talk about doing things.

### Phase C Target State

```
User Input
    ↓
AgentCore.chat()
    ↓
┌─────────────────────────────┐
│  Decide Phase               │
│  - LLM decides what to do   │
│  - May call tools           │
└──────────────┬──────────────┘
               ↓
       ┌───────┴───────┐
       │ Tool Call?     │
       │                │
       ↓ Yes            ↓ No
┌──────────────┐  ┌──────────────┐
│ ToolExecutor │  │ Respond      │
│ - Permission │  │ - Generate   │
│ - Execute    │  │   response   │
│ - Log        │  └──────────────┘
└──────┬───────┘
       ↓
┌──────────────┐
│ Tool Result  │
│ - Process    │
│ - Add to     │
│   context    │
└──────┬───────┘
       ↓
┌──────────────┐
│ Respond      │
│ - Generate   │
│   with tool  │
│   results    │
└──────────────┘
    ↓
Response
```

### Tool Calling Flow

```
User: "List all Python files in my project"
    │
    ↓
┌─────────────────────────────────────────────┐
│  Agent Loop                                  │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │ Step 1: Understand                      │ │
│  │ - Intent: list_files                    │ │
│  │ - Entity: Python files                  │ │
│  │ - Location: project directory           │ │
│  └───────────────────┬────────────────────┘ │
│                      ↓                       │
│  ┌────────────────────────────────────────┐ │
│  │ Step 2: Decide                          │ │
│  │ - Tool: filesystem                      │ │
│  │ - Action: list                          │ │
│  │ - Args: {pattern: "*.py"}              │ │
│  └───────────────────┬────────────────────┘ │
│                      ↓                       │
│  ┌────────────────────────────────────────┐ │
│  │ Step 3: Execute Tool                    │ │
│  │ - Check permissions (T2 required)       │ │
│  │ - ToolGateway.execute("filesystem",...) │ │
│  │ - Get result: ["src/main.py", ...]      │ │
│  └───────────────────┬────────────────────┘ │
│                      ↓                       │
│  ┌────────────────────────────────────────┐ │
│  │ Step 4: Process Result                  │ │
│  │ - Format for context                    │ │
│  │ - Add to conversation                   │ │
│  └───────────────────┬────────────────────┘ │
│                      ↓                       │
│  ┌────────────────────────────────────────┐ │
│  │ Step 5: Respond                         │ │
│  │ - "I found 5 Python files: ..."         │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
    │
    ↓
Response with tool results
```

---

## Data Models

### ToolCall

Represents a request to call a tool.

```python
@dataclass
class ToolCall:
    tool_name: str
    tool_args: dict[str, Any]
    reasoning: str
    call_id: str
```

**Fields:**

- `tool_name` — Name of the tool to call
- `tool_args` — Arguments to pass to the tool
- `reasoning` — Why this tool was chosen
- `call_id` — Unique identifier for this call

### ToolResult

Result of a tool execution.

```python
@dataclass
class ToolResult:
    call_id: str
    tool_name: str
    success: bool
    output: Any
    error: str | None
    duration_ms: float
```

**Fields:**

- `call_id` — Matching call ID
- `tool_name` — Tool that was called
- `success` — Whether execution succeeded
- `output` — Tool output (if successful)
- `error` — Error message (if failed)
- `duration_ms` — Execution time

### ToolDefinition

Definition of a tool for the LLM.

```python
@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    required_permissions: list[str]
```

**Fields:**

- `name` — Tool name
- `description` — What the tool does
- `parameters` — JSON Schema for parameters
- `required_permissions` — Permissions needed to use this tool

---

## API Design

### POST /agent/chat (Updated)

Now includes tool calls.

**Request:**

```json
{
  "session_id": "session-123",
  "message": "List all Python files in my project",
  "context": {
    "trust_level": "T2",
    "available_tools": ["filesystem", "terminal", "browser"]
  }
}
```

**Response:**

```json
{
  "session_id": "session-123",
  "response": "I found 5 Python files in your project: src/main.py, src/utils.py, ...",
  "tools_used": ["filesystem"],
  "tool_calls": [
    {
      "call_id": "call-001",
      "tool_name": "filesystem",
      "tool_args": {"path": ".", "pattern": "*.py"},
      "success": true,
      "duration_ms": 150
    }
  ]
}
```

### GET /agent/tools

List available tools.

**Response:**

```json
{
  "tools": [
    {
      "name": "filesystem",
      "description": "Read and manage files",
      "parameters": {
        "type": "object",
        "properties": {
          "path": {"type": "string"},
          "action": {"type": "string", "enum": ["read", "write", "list", "search"]}
        }
      },
      "required_permissions": ["filesystem.read"]
    }
  ]
}
```

### GET /agent/tool-history/{session_id}

Get tool calls in a session.

**Response:**

```json
{
  "session_id": "session-123",
  "tool_calls": [
    {
      "call_id": "call-001",
      "tool_name": "filesystem",
      "tool_args": {"path": ".", "action": "list"},
      "success": true,
      "output": ["src/main.py", "src/utils.py"],
      "duration_ms": 150,
      "timestamp": "2026-09-02T10:30:00Z"
    }
  ]
}
```

---

## Implementation Details

### Step 1: Create Tool Module Structure

Create the following files:

```
src/mysti/engine/
├── tool_executor.py
└── function_calling.py
```

### Step 2: Implement FunctionCalling (function_calling.py)

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    required_permissions: list[str]

class FunctionCalling:
    def __init__(self):
        self.tools: dict[str, ToolDefinition] = {}

    def register_tool(self, tool: ToolDefinition) -> None:
        self.tools[tool.name] = tool

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
            }
            for tool in self.tools.values()
        ]

    def format_tools_for_prompt(self) -> str:
        if not self.tools:
            return ""

        lines = ["## Available Tools\n"]
        for tool in self.tools.values():
            lines.append(f"### {tool.name}")
            lines.append(f"Description: {tool.description}")
            lines.append(f"Permissions: {', '.join(tool.required_permissions)}")
            lines.append(f"Parameters: {tool.parameters}")
            lines.append("")

        return "\n".join(lines)

    def parse_tool_calls(self, llm_response: str) -> list[dict[str, Any]]:
        # Parse function calling format from LLM response
        # This is a simplified parser - real implementation would handle
        # the specific format of the LLM provider
        tool_calls = []

        # Look for tool call patterns
        import json
        import re

        # Pattern: ```tool_call\n{"name": "...", "args": {...}}\n```
        pattern = r"```tool_call\s*\n(.*?)\n```"
        matches = re.findall(pattern, llm_response, re.DOTALL)

        for match in matches:
            try:
                call = json.loads(match)
                if "name" in call and "args" in call:
                    tool_calls.append(call)
            except json.JSONDecodeError:
                continue

        return tool_calls

    def format_tool_result(self, result: Any, tool_name: str) -> str:
        if isinstance(result, dict):
            return json.dumps(result, indent=2)
        elif isinstance(result, list):
            return "\n".join(str(item) for item in result)
        else:
            return str(result)
```

### Step 3: Implement ToolExecutor (tool_executor.py)

```python
from __future__ import annotations
import asyncio
import json
from dataclasses import dataclass
from typing import Any, Protocol

class ToolGateway(Protocol):
    async def execute(self, tool_name: str, args: dict[str, Any]) -> Any: ...

class PermissionManager(Protocol):
    def check_permission(self, permission: str, trust_level: str) -> bool: ...

class AuditLog(Protocol):
    def log(self, event_type: str, details: dict[str, Any]) -> None: ...

@dataclass
class ToolCall:
    call_id: str
    tool_name: str
    tool_args: dict[str, Any]
    reasoning: str

@dataclass
class ToolResult:
    call_id: str
    tool_name: str
    success: bool
    output: Any
    error: str | None
    duration_ms: float

class ToolExecutor:
    def __init__(
        self,
        tool_gateway: ToolGateway,
        permission_manager: PermissionManager | None = None,
        audit_log: AuditLog | None = None,
        function_calling: FunctionCalling | None = None,
    ):
        self.gateway = tool_gateway
        self.permissions = permission_manager
        self.audit = audit_log
        self.function_calling = function_calling or FunctionCalling()
        self._execution_history: dict[str, list[ToolResult]] = {}

    async def execute_tool(
        self,
        tool_call: ToolCall,
        trust_level: str = "T0",
    ) -> ToolResult:
        # Check permissions
        if self.permissions:
            tool_def = self.function_calling.tools.get(tool_call.tool_name)
            if tool_def:
                for perm in tool_def.required_permissions:
                    if not self.permissions.check_permission(perm, trust_level):
                        return ToolResult(
                            call_id=tool_call.call_id,
                            tool_name=tool_call.tool_name,
                            success=False,
                            output=None,
                            error=f"Permission denied: {perm} required",
                            duration_ms=0
                        )

        # Execute tool
        start_time = asyncio.get_event_loop().time()
        try:
            output = await self.gateway.execute(tool_call.tool_name, tool_call.tool_args)
            duration = (asyncio.get_event_loop().time() - start_time) * 1000

            result = ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                success=True,
                output=output,
                error=None,
                duration_ms=duration
            )
        except Exception as e:
            duration = (asyncio.get_event_loop().time() - start_time) * 1000
            result = ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                success=False,
                output=None,
                error=str(e),
                duration_ms=duration
            )

        # Log to audit
        if self.audit:
            self.audit.log("tool.execute", {
                "call_id": tool_call.call_id,
                "tool_name": tool_call.tool_name,
                "args": tool_call.tool_args,
                "success": result.success,
                "duration_ms": result.duration_ms,
                "error": result.error,
            })

        # Store in history
        if tool_call.call_id not in self._execution_history:
            self._execution_history[tool_call.call_id] = []
        self._execution_history[tool_call.call_id].append(result)

        return result

    async def execute_tools(
        self,
        tool_calls: list[ToolCall],
        trust_level: str = "T0",
        parallel: bool = False,
    ) -> list[ToolResult]:
        if parallel:
            tasks = [self.execute_tool(call, trust_level) for call in tool_calls]
            return await asyncio.gather(*tasks)
        else:
            results = []
            for call in tool_calls:
                result = await self.execute_tool(call, trust_level)
                results.append(result)
            return results

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return self.function_calling.get_tool_definitions()

    def format_tools_for_prompt(self) -> str:
        return self.function_calling.format_tools_for_prompt()
```

### Step 4: Update AgentCore with Tool Support

Update `src/mysti/engine/core.py`:

```python
class AgentCore:
    def __init__(
        self,
        llm: LLMClient,
        tools: ToolGateway | None = None,
        memory: MemoryService | None = None,
        rag: RAGPipeline | None = None,
        permission_manager: PermissionManager | None = None,
        audit_log: AuditLog | None = None,
        max_steps: int = 10,
    ):
        self.llm = llm
        self.tools = tools
        self.memory = memory
        self.rag = rag
        self.max_steps = max_steps
        self._states: dict[str, AgentState] = {}

        # Initialize tool executor if tools provided
        if tools:
            self.tool_executor = ToolExecutor(
                tool_gateway=tools,
                permission_manager=permission_manager,
                audit_log=audit_log,
            )
        else:
            self.tool_executor = None

    async def chat(self, session_id: str, message: str) -> AgentResult:
        state = self.get_state(session_id)
        state.add_message("user", message)

        steps = []
        total_tokens = 0
        tools_used = []

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

        # Build system prompt with tool definitions
        prompt_builder = DynamicPromptBuilder()
        if self.tool_executor:
            tool_definitions = self.tool_executor.format_tools_for_prompt()
            if tool_definitions:
                prompt_builder.add_tool_definitions(tool_definitions)

        system_prompt = prompt_builder.build()
        messages = [{"role": "system", "content": system_prompt}] + enhanced_messages

        # Agent loop
        while state.increment_step():
            step_start = asyncio.get_event_loop().time()

            # Call LLM
            response = await self.llm.complete(messages)
            total_tokens += len(response.split())

            # Parse tool calls
            if self.tool_executor:
                tool_calls = self.tool_executor.function_calling.parse_tool_calls(response)

                if tool_calls:
                    # Execute tools
                    calls = [
                        ToolCall(
                            call_id=f"call-{state.current_step}-{i}",
                            tool_name=call["name"],
                            tool_args=call["args"],
                            reasoning="LLM decided to call this tool"
                        )
                        for i, call in enumerate(tool_calls)
                    ]

                    results = await self.tool_executor.execute_tools(calls)
                    tools_used.extend([r.tool_name for r in results if r.success])

                    # Add tool results to context
                    tool_results_text = "\n".join([
                        f"Tool {r.tool_name}: {r.output if r.success else r.error}"
                        for r in results
                    ])
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": f"Tool results:\n{tool_results_text}"})

                    # Continue loop to process tool results
                    continue

            # No tool calls - generate final response
            step_duration = (asyncio.get_event_loop().time() - step_start) * 1000

            state.add_message("assistant", response)

            steps.append(AgentStep(
                step_number=state.current_step,
                input_text=message,
                action=AgentAction(action_type="respond", reasoning="LLM response"),
                output_text=response,
                tool_results=[],
                memories_retrieved=memories_used,
                duration_ms=step_duration,
                tokens_used=len(response.split())
            ))

            break

        return AgentResult(
            response=steps[-1].output_text if steps else "",
            steps=steps,
            total_tokens=total_tokens,
            total_duration_ms=sum(s.duration_ms for s in steps),
            tools_used=tools_used,
            memories_used=memories_used,
            loop_terminated="normal"
        )
```

### Step 5: Register Tools

Create `src/mysti/engine/tool_registry.py`:

```python
from mysti.engine.function_calling import ToolDefinition

def get_default_tool_definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="filesystem",
            description="Read and manage files on the local filesystem",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File or directory path"},
                    "action": {"type": "string", "enum": ["read", "write", "list", "search"]},
                    "content": {"type": "string", "description": "Content to write (for write action)"},
                    "pattern": {"type": "string", "description": "Search pattern (for search action)"},
                },
                "required": ["path", "action"],
            },
            required_permissions=["filesystem.read", "filesystem.write"],
        ),
        ToolDefinition(
            name="terminal",
            description="Execute shell commands",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds"},
                },
                "required": ["command"],
            },
            required_permissions=["terminal.execute"],
        ),
        ToolDefinition(
            name="browser",
            description="Fetch and extract content from web pages",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                    "extract": {"type": "string", "enum": ["text", "links", "html"]},
                },
                "required": ["url"],
            },
            required_permissions=["web.fetch"],
        ),
        ToolDefinition(
            name="git",
            description="Execute git commands",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Git command (status, log, diff, etc.)"},
                    "args": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["command"],
            },
            required_permissions=["git.read"],
        ),
        ToolDefinition(
            name="network",
            description="Make HTTP requests",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to request"},
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                    "data": {"type": "object", "description": "Request body"},
                },
                "required": ["url", "method"],
            },
            required_permissions=["network.fetch"],
        ),
    ]
```

---

## Dependencies

### New Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `tiktoken` | >=0.7 | Token counting for tool definitions |

### Existing Dependencies Used

| Dependency | Purpose |
|------------|---------|
| `tools/gateway.py` | ToolGateway for execution |
| `security/permissions.py` | PermissionManager for tool gating |
| `security/audit.py` | AuditLog for logging |

---

## Testing

### Unit Tests

**test_function_calling.py:**

```python
import pytest
from mysti.engine.function_calling import FunctionCalling, ToolDefinition

def test_register_tool():
    fc = FunctionCalling()
    tool = ToolDefinition(
        name="test_tool",
        description="A test tool",
        parameters={"type": "object", "properties": {}},
        required_permissions=["test.read"],
    )
    fc.register_tool(tool)
    assert "test_tool" in fc.tools

def test_get_tool_definitions():
    fc = FunctionCalling()
    tool = ToolDefinition(
        name="test_tool",
        description="A test tool",
        parameters={"type": "object", "properties": {}},
        required_permissions=[],
    )
    fc.register_tool(tool)
    defs = fc.get_tool_definitions()
    assert len(defs) == 1
    assert defs[0]["function"]["name"] == "test_tool"

def test_format_tools_for_prompt():
    fc = FunctionCalling()
    tool = ToolDefinition(
        name="filesystem",
        description="Read files",
        parameters={},
        required_permissions=["filesystem.read"],
    )
    fc.register_tool(tool)
    formatted = fc.format_tools_for_prompt()
    assert "filesystem" in formatted
    assert "Read files" in formatted
```

**test_tool_executor.py:**

```python
import pytest
from unittest.mock import AsyncMock
from mysti.engine.tool_executor import ToolExecutor, ToolCall, ToolResult

@pytest.mark.asyncio
async def test_execute_tool_success():
    mock_gateway = AsyncMock()
    mock_gateway.execute.return_value = ["file1.py", "file2.py"]

    executor = ToolExecutor(tool_gateway=mock_gateway)
    call = ToolCall(
        call_id="call-1",
        tool_name="filesystem",
        tool_args={"path": ".", "action": "list"},
        reasoning="List files"
    )

    result = await executor.execute_tool(call)
    assert result.success is True
    assert result.output == ["file1.py", "file2.py"]

@pytest.mark.asyncio
async def test_execute_tool_failure():
    mock_gateway = AsyncMock()
    mock_gateway.execute.side_effect = Exception("Permission denied")

    executor = ToolExecutor(tool_gateway=mock_gateway)
    call = ToolCall(
        call_id="call-1",
        tool_name="filesystem",
        tool_args={"path": ".", "action": "read"},
        reasoning="Read file"
    )

    result = await executor.execute_tool(call)
    assert result.success is False
    assert "Permission denied" in result.error
```

**test_agent_core_tools.py:**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from mysti.engine.core import AgentCore

@pytest.mark.asyncio
async def test_agent_with_tool_calls():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = '```tool_call\n{"name": "filesystem", "args": {"path": ".", "action": "list"}}\n```\n\nHere are the files:'

    mock_gateway = AsyncMock()
    mock_gateway.execute.return_value = ["main.py", "utils.py"]

    agent = AgentCore(llm=mock_llm, tools=mock_gateway)
    result = await agent.chat("session-1", "List files")

    assert "main.py" in result.response
    assert "filesystem" in result.tools_used
```

### Integration Tests

**test_tool_integration.py:**

```python
import pytest
from mysti.engine.core import AgentCore
from mysti.tools.gateway import ToolGateway
from mysti.tools.filesystem import FilesystemTool

@pytest.mark.asyncio
async def test_full_tool_flow():
    # This would use real tools in integration tests
    # For now, test the flow with mocks
    pass
```

---

## Edge Cases

### Tool Not Found

```python
async def execute_tool(self, tool_call, trust_level="T0"):
    if tool_call.tool_name not in self.function_calling.tools:
        return ToolResult(
            call_id=tool_call.call_id,
            tool_name=tool_call.tool_name,
            success=False,
            output=None,
            error=f"Tool not found: {tool_call.tool_name}",
            duration_ms=0
        )
    # Continue with execution...
```

### Tool Permission Denied

```python
async def execute_tool(self, tool_call, trust_level="T0"):
    if self.permissions:
        tool_def = self.function_calling.tools.get(tool_call.tool_name)
        if tool_def:
            for perm in tool_def.required_permissions:
                if not self.permissions.check_permission(perm, trust_level):
                    # Log permission denial
                    if self.audit:
                        self.audit.log("tool.permission_denied", {
                            "tool": tool_call.tool_name,
                            "permission": perm,
                            "trust_level": trust_level,
                        })
                    return ToolResult(
                        call_id=tool_call.call_id,
                        tool_name=tool_call.tool_name,
                        success=False,
                        output=None,
                        error=f"Permission denied: {perm} required (trust level: {trust_level})",
                        duration_ms=0
                    )
    # Continue with execution...
```

### Tool Execution Timeout

```python
async def execute_tool(self, tool_call, trust_level="T0", timeout: float = 30.0):
    try:
        result = await asyncio.wait_for(
            self.gateway.execute(tool_call.tool_name, tool_call.tool_args),
            timeout=timeout
        )
        # Process result...
    except asyncio.TimeoutError:
        return ToolResult(
            call_id=tool_call.call_id,
            tool_name=tool_call.tool_name,
            success=False,
            output=None,
            error=f"Tool execution timed out after {timeout}s",
            duration_ms=timeout * 1000
        )
```

### Invalid Tool Arguments

```python
def parse_tool_calls(self, llm_response):
    tool_calls = []
    # ... parsing logic ...

    # Validate tool calls
    valid_calls = []
    for call in tool_calls:
        if "name" not in call or "args" not in call:
            continue
        if call["name"] not in self.tools:
            continue
        valid_calls.append(call)

    return valid_calls
```

### Tool Returns Unexpected Format

```python
def format_tool_result(self, result, tool_name):
    try:
        if isinstance(result, dict):
            return json.dumps(result, indent=2)
        elif isinstance(result, list):
            return "\n".join(str(item) for item in result)
        else:
            return str(result)
    except Exception:
        return f"[Tool {tool_name}] Unable to format result"
```

---

## Deliverables

When Phase C is complete, you will have:

1. **`src/mysti/engine/tool_executor.py`** — ToolExecutor class
2. **`src/mysti/engine/function_calling.py`** — FunctionCalling class
3. **`src/mysti/engine/tool_registry.py`** — Default tool definitions
4. **Updated AgentCore** — Uses tool executor
5. **Updated API** — Tool history endpoint
6. **Tests** — 8+ unit tests, 2+ integration tests

---

## What Comes Next

After Phase C, you will move to **Phase D: Knowledge Integration**, which adds:
- Entity extraction from conversations
- Knowledge graph storage
- Graph queries during chat
- Entity-aware memory search

Phase C's tool integration provides the foundation for knowledge-aware tool calling, with the AI able to use tools while considering relevant knowledge graph data.

---

*Phase C makes MYSTI actionable — the AI can now call tools and take real actions during conversations.*
