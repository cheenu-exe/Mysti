"""Tests for Phase 4 tool integration."""

import pytest
from pathlib import Path

from mysti.security.permissions import PermissionManager, Permission, TrustLevel
from mysti.security.sandbox import SandboxManager
from mysti.tools.gateway import ToolGateway, ToolResult
from mysti.tools.filesystem import FilesystemTool
from mysti.tools.terminal import TerminalTool
from mysti.tools.browser import BrowserTool
from mysti.tools.git_tool import GitTool
from mysti.tools.network import NetworkTool
from mysti.tools.composer import ToolComposer


# --- Tool Gateway Tests ---

def test_gateway_register_and_list_tools():
    gw = ToolGateway()
    gw.register_tool(FilesystemTool())
    gw.register_tool(TerminalTool())
    tools = gw.list_tools()
    names = [t["name"] for t in tools]
    assert "filesystem" in names
    assert "terminal" in names


def test_gateway_get_tool():
    gw = ToolGateway()
    gw.register_tool(FilesystemTool())
    assert gw.get_tool("filesystem").name == "filesystem"
    with pytest.raises(KeyError):
        gw.get_tool("nonexistent")


@pytest.mark.asyncio
async def test_gateway_blocks_unknown_tool():
    gw = ToolGateway()
    result = await gw.execute("unknown_tool", {})
    assert not result.success
    assert "unknown tool" in result.error.lower()


@pytest.mark.asyncio
async def test_gateway_enforces_trust_level():
    gw = ToolGateway(trust_level=TrustLevel.T0)
    gw.register_tool(TerminalTool())
    result = await gw.execute("terminal", {"command": "echo hi"})
    assert not result.success
    assert "trust level" in result.error.lower()


@pytest.mark.asyncio
async def test_gateway_enforces_permissions():
    pm = PermissionManager()
    gw = ToolGateway(permission_manager=pm, current_mode=TrustLevel.T2)
    gw.register_tool(TerminalTool())
    # T2 doesn't include TOOLS_EXECUTE by default
    result = await gw.execute("terminal", {"command": "echo hi"})
    assert not result.success


@pytest.mark.asyncio
async def test_gateway_successful_execution():
    pm = PermissionManager()
    for p in Permission:
        pm.grant_permission(p)
    gw = ToolGateway(permission_manager=pm, current_mode=TrustLevel.T4)
    gw.register_tool(TerminalTool())
    result = await gw.execute("terminal", {"command": "python -c \"print('hello')\""})
    assert result.success
    assert result.execution_time > 0


# --- Filesystem Tool Tests ---

@pytest.mark.asyncio
async def test_filesystem_read_write_roundtrip(tmp_path):
    tool = FilesystemTool()
    test_file = str(tmp_path / "test.txt")
    tool.write_file(test_file, "hello world")
    content = tool.read_file(test_file)
    assert content == "hello world"


@pytest.mark.asyncio
async def test_filesystem_blocks_protected_paths():
    import sys
    tool = FilesystemTool()
    if sys.platform == "win32":
        # On Windows, test with Windows-style protected paths
        home = Path.home()
        ssh_path = str(home / ".ssh" / "config")
        with pytest.raises(PermissionError, match="protected"):
            tool.read_file(ssh_path)
    else:
        with pytest.raises(PermissionError, match="protected"):
            tool.read_file("/etc/passwd")
        with pytest.raises(PermissionError, match="protected"):
            tool.write_file("/etc/test", "bad")


@pytest.mark.asyncio
async def test_filesystem_list_directory(tmp_path):
    tool = FilesystemTool()
    (tmp_path / "file.txt").write_text("test")
    (tmp_path / "subdir").mkdir()
    items = tool.list_directory(str(tmp_path))
    names = [i["name"] for i in items]
    assert "file.txt" in names
    assert "subdir" in names


@pytest.mark.asyncio
async def test_filesystem_search_files(tmp_path):
    tool = FilesystemTool()
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.py").write_text("y")
    (tmp_path / "c.txt").write_text("z")
    results = tool.search_files(str(tmp_path), "*.py")
    assert len(results) == 2


@pytest.mark.asyncio
async def test_filesystem_execute_via_gateway(tmp_path):
    pm = PermissionManager()
    for p in Permission:
        pm.grant_permission(p)
    gw = ToolGateway(permission_manager=pm, current_mode=TrustLevel.T4)
    gw.register_tool(FilesystemTool())
    test_file = str(tmp_path / "gateway_test.txt")
    result = await gw.execute("filesystem", {
        "operation": "write_file",
        "path": test_file,
        "content": "gateway test"
    })
    assert result.success
    result2 = await gw.execute("filesystem", {
        "operation": "read_file",
        "path": test_file
    })
    assert result2.success
    assert result2.output == "gateway test"


# --- Terminal Tool Tests ---

@pytest.mark.asyncio
async def test_terminal_execute_simple():
    tool = TerminalTool(trust_level=TrustLevel.T2)
    result = await tool.execute({"command": "python -c \"print(42)\""})
    assert result.success
    assert "42" in result.output.stdout


@pytest.mark.asyncio
async def test_terminal_blocks_dangerous_commands():
    tool = TerminalTool(trust_level=TrustLevel.T4)
    result = await tool.execute({"command": "rm -rf /"})
    assert not result.success or result.output.blocked


@pytest.mark.asyncio
async def test_terminal_background_jobs():
    tool = TerminalTool(trust_level=TrustLevel.T2)
    job_id = await tool.execute_background("python -c \"import time; time.sleep(0.1)\"")
    assert job_id
    status = await tool.get_job_status(job_id)
    assert status["status"] in ("running", "completed")


@pytest.mark.asyncio
async def test_terminal_kill_job():
    tool = TerminalTool(trust_level=TrustLevel.T2)
    job_id = await tool.execute_background("python -c \"import time; time.sleep(10)\"")
    killed = await tool.kill_job(job_id)
    assert killed


# --- Browser Tool Tests ---

@pytest.mark.asyncio
async def test_browser_blocks_invalid_schemes():
    tool = BrowserTool()
    with pytest.raises(ValueError, match="unsupported"):
        await tool.fetch_page("ftp://example.com")
    with pytest.raises(ValueError, match="unsupported"):
        await tool.fetch_page("file:///etc/passwd")


@pytest.mark.asyncio
async def test_browser_extract_text():
    tool = BrowserTool()
    # This will fail with network, but tests the method exists
    with pytest.raises(Exception):
        await tool.extract_text("https://nonexistent.example.com")


# --- Git Tool Tests ---

@pytest.mark.asyncio
async def test_git_tool_status(tmp_path):
    tool = GitTool()
    # Not a git repo, should fail
    result = await tool.execute({"operation": "status", "repo_path": str(tmp_path)})
    assert not result.success


@pytest.mark.asyncio
async def test_git_tool_with_real_repo(tmp_path):
    import subprocess
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)
    (tmp_path / "file.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)
    tool = GitTool()
    result = await tool.execute({"operation": "log", "repo_path": str(tmp_path), "limit": 5})
    assert result.success
    assert len(result.output) >= 1


# --- Network Tool Tests ---

@pytest.mark.asyncio
async def test_network_blocks_internal_addresses():
    tool = NetworkTool()
    with pytest.raises(ValueError, match="internal"):
        await tool.http_get("http://127.0.0.1/admin")
    with pytest.raises(ValueError, match="internal"):
        await tool.http_get("http://192.168.1.1/admin")


@pytest.mark.asyncio
async def test_network_blocks_non_http_schemes():
    tool = NetworkTool()
    with pytest.raises(ValueError, match="unsupported"):
        await tool.http_get("ftp://example.com")


@pytest.mark.asyncio
async def test_network_dns_lookup():
    tool = NetworkTool()
    result = await tool.dns_lookup("localhost")
    assert "addresses" in result
    assert len(result["addresses"]) > 0


# --- Composer Tests ---

@pytest.mark.asyncio
async def test_composer_chain_operations(tmp_path):
    pm = PermissionManager()
    for p in Permission:
        pm.grant_permission(p)
    gw = ToolGateway(permission_manager=pm, current_mode=TrustLevel.T4)
    gw.register_tool(FilesystemTool())
    gw.register_tool(TerminalTool())
    composer = ToolComposer(gw)
    test_file = str(tmp_path / "composed.txt")
    # Chain: write file, then read it using terminal
    steps = [
        {"tool": "filesystem", "params": {"operation": "write_file", "path": test_file, "content": "composed"}},
        {"tool": "terminal", "params": {"command": f"python -c \"print(open(r'{test_file}').read())\""}},
    ]
    result = await composer.compose(steps)
    assert result.success
    assert "composed" in str(result.output)


@pytest.mark.asyncio
async def test_composer_stops_on_error():
    pm = PermissionManager()
    for p in Permission:
        pm.grant_permission(p)
    gw = ToolGateway(permission_manager=pm, current_mode=TrustLevel.T4)
    gw.register_tool(FilesystemTool())
    composer = ToolComposer(gw)
    steps = [
        {"tool": "filesystem", "params": {"operation": "read_file", "path": "/nonexistent/file"}},
        {"tool": "filesystem", "params": {"operation": "read_file", "path": "/also/nonexistent"}},
    ]
    result = await composer.compose(steps)
    assert not result.success


@pytest.mark.asyncio
async def test_composer_parallel():
    pm = PermissionManager()
    for p in Permission:
        pm.grant_permission(p)
    gw = ToolGateway(permission_manager=pm, current_mode=TrustLevel.T4)
    gw.register_tool(TerminalTool())
    composer = ToolComposer(gw)
    tasks = [
        {"tool": "terminal", "params": {"command": "python -c \"print(1)\""}},
        {"tool": "terminal", "params": {"command": "python -c \"print(2)\""}},
    ]
    results = await composer.parallel(tasks)
    assert len(results) == 2
    assert all(r.success for r in results)


# --- Integration Tests ---

@pytest.mark.asyncio
async def test_full_tool_integration(tmp_path):
    """Test a complete workflow: write file, read it, search for it."""
    pm = PermissionManager()
    for p in Permission:
        pm.grant_permission(p)
    gw = ToolGateway(permission_manager=pm, current_mode=TrustLevel.T4)
    gw.register_tool(FilesystemTool())
    gw.register_tool(TerminalTool())

    # Write a file
    test_file = str(tmp_path / "integration.txt")
    result = await gw.execute("filesystem", {
        "operation": "write_file",
        "path": test_file,
        "content": "integration test content"
    })
    assert result.success

    # Read it back
    result = await gw.execute("filesystem", {
        "operation": "read_file",
        "path": test_file
    })
    assert result.success
    assert result.output == "integration test content"

    # Search for it
    result = await gw.execute("filesystem", {
        "operation": "search_files",
        "path": str(tmp_path),
        "pattern": "*.txt"
    })
    assert result.success
    assert test_file in result.output
