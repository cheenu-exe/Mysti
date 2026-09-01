"""CLI tests via Typer's test runner (hermetic env, memory keystore)."""

import pytest
from typer.testing import CliRunner

from mysti.cli.main import app

runner = CliRunner()


@pytest.fixture
def persistent_keystore(tmp_path, monkeypatch):
    """Shared in-memory keystore so successive CLI invocations see the same master key."""
    from mysti.security.keystore import InMemorySecretStore

    store = InMemorySecretStore()
    monkeypatch.setattr("mysti.core.context.create_secret_store", lambda settings: store)
    return store


@pytest.fixture
def cli_env(tmp_path, monkeypatch, persistent_keystore):
    monkeypatch.setenv("MYSTI_STORAGE_PROVIDER", "local")
    monkeypatch.setenv("MYSTI_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("MYSTI_SECRET_BACKEND", "memory")
    monkeypatch.setenv("MYSTI_LLM_PROVIDER", "none")
    monkeypatch.setenv("MYSTI_STORAGE_BUCKET", "")
    monkeypatch.delenv("MYSTI_STORAGE_ENDPOINT", raising=False)
    monkeypatch.delenv("MYSTI_STORAGE_ACCESS_KEY", raising=False)
    monkeypatch.delenv("MYSTI_STORAGE_SECRET_KEY", raising=False)
    monkeypatch.delenv("MYSTI_API_TOKEN", raising=False)
    monkeypatch.delenv("MYSTI_LLM_API_KEY", raising=False)
    monkeypatch.delenv("MYSTI_KEY_FILE_PASSPHRASE", raising=False)
    return tmp_path


def test_store_and_recall(cli_env):
    stored = runner.invoke(app, ["store", "personal", "my favourite editor is vim"])
    assert stored.exit_code == 0, stored.output
    assert "stored" in stored.output
    recalled = runner.invoke(app, ["recall", "vim"])
    assert recalled.exit_code == 0, recalled.output
    assert "favourite editor" in recalled.output


def test_recall_no_hits(cli_env):
    runner.invoke(app, ["store", "ideas", "something unrelated"])
    result = runner.invoke(app, ["recall", "quantum"])
    assert result.exit_code == 0
    assert "no matching memories" in result.output


def test_store_rejects_unknown_category(cli_env):
    result = runner.invoke(app, ["store", "bogus", "x"])
    assert result.exit_code == 1
    assert "unknown memory category" in result.output


def test_status_command(cli_env):
    runner.invoke(app, ["store", "personal", "status test entry"])
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0, result.output
    assert "records:" in result.output
    assert "storage:     local" in result.output


def test_history_command(cli_env):
    result = runner.invoke(app, ["history"])
    assert result.exit_code == 0


def test_config_masks_secrets(cli_env, monkeypatch):
    monkeypatch.setenv("MYSTI_LLM_PROVIDER", "openai")
    monkeypatch.setenv("MYSTI_LLM_API_KEY", "super-secret-key")
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "super-secret-key" not in result.output
    assert "***" in result.output


def test_help_lists_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("init", "start", "store", "recall", "history", "status", "config", "serve"):
        assert command in result.output
