import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import src.mcp_server as mcp_server


@pytest.fixture(autouse=True)
def clear_env_vars(monkeypatch):
    """Clear all relevant environment variables before each test."""
    monkeypatch.delenv("GEMINI_BRIDGE_TIMEOUT", raising=False)
    monkeypatch.delenv("GEMINI_BRIDGE_DEFAULT_TIMEOUT", raising=False)
    monkeypatch.delenv("GEMINI_BRIDGE_DEFAULT_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_BRIDGE_TRUST_WORKSPACE", raising=False)


def test_normalize_model_name_defaults():
    # Test default model (respects GEMINI_BRIDGE_DEFAULT_MODEL env var)
    assert mcp_server._normalize_model_name(None) == "gemini-2.5-flash"
    assert mcp_server._normalize_model_name("  flash  ") == "gemini-2.5-flash"


def test_normalize_model_name_with_custom_default(monkeypatch):
    """Test that GEMINI_BRIDGE_DEFAULT_MODEL environment variable is respected."""
    import importlib

    monkeypatch.setenv("GEMINI_BRIDGE_DEFAULT_MODEL", "pro")
    importlib.reload(mcp_server)
    assert mcp_server._normalize_model_name(None) == "gemini-2.5-pro"

    monkeypatch.setenv("GEMINI_BRIDGE_DEFAULT_MODEL", "auto")
    importlib.reload(mcp_server)
    assert mcp_server._normalize_model_name(None) == "auto"


def test_normalize_model_name_pro_alias():
    assert mcp_server._normalize_model_name("pro") == "gemini-2.5-pro"
    assert mcp_server._normalize_model_name("2.5-pro") == "gemini-2.5-pro"


def test_normalize_model_name_flash_lite():
    assert mcp_server._normalize_model_name("flash-lite") == "gemini-2.5-flash-lite"
    assert mcp_server._normalize_model_name("2.5-flash-lite") == "gemini-2.5-flash-lite"


def test_normalize_model_name_3_series():
    assert mcp_server._normalize_model_name("3-pro") == "gemini-3-pro-preview"
    assert mcp_server._normalize_model_name("3-flash") == "gemini-3-flash-preview"


def test_normalize_model_name_3_1_series():
    assert mcp_server._normalize_model_name("3.1-pro") == "gemini-3.1-pro-preview"
    assert mcp_server._normalize_model_name("gemini-3.1-pro") == "gemini-3.1-pro-preview"


def test_normalize_model_name_3_1_flash_lite():
    assert mcp_server._normalize_model_name("3.1-flash-lite") == "gemini-3.1-flash-lite-preview"
    assert mcp_server._normalize_model_name("gemini-3.1-flash-lite") == "gemini-3.1-flash-lite-preview"


def test_normalize_model_name_2_5_lite_aliases():
    assert mcp_server._normalize_model_name("2.5-lite") == "gemini-2.5-flash-lite"
    assert mcp_server._normalize_model_name("gemini-2.5-lite") == "gemini-2.5-flash-lite"


def test_normalize_model_name_auto_router():
    assert mcp_server._normalize_model_name("auto") == "auto"


def test_normalize_model_name_passthrough():
    assert mcp_server._normalize_model_name("gemini-exp-1201") == "gemini-exp-1201"


def test_get_timeout_defaults_to_120():
    """Test that default timeout is now 120 seconds instead of 60."""
    assert mcp_server._get_timeout() == 120


def test_get_timeout_with_custom_default(monkeypatch):
    """Test that GEMINI_BRIDGE_DEFAULT_TIMEOUT environment variable is respected."""
    import importlib

    monkeypatch.setenv("GEMINI_BRIDGE_DEFAULT_TIMEOUT", "180")
    importlib.reload(mcp_server)
    assert mcp_server._get_timeout() == 180


def test_get_timeout_returns_positive_integer(monkeypatch):
    monkeypatch.setenv("GEMINI_BRIDGE_TIMEOUT", "120")
    assert mcp_server._get_timeout() == 120


def test_get_timeout_handles_invalid_values(monkeypatch, caplog):
    """Test that invalid timeout values fall back to default (120 seconds)."""
    import importlib

    # Reset to default state first
    monkeypatch.delenv("GEMINI_BRIDGE_DEFAULT_TIMEOUT", raising=False)
    importlib.reload(mcp_server)

    caplog.set_level("WARNING")
    monkeypatch.setenv("GEMINI_BRIDGE_TIMEOUT", "-5")
    assert mcp_server._get_timeout() == 120  # Updated from 60 to 120
    assert "must be positive" in caplog.text

    caplog.clear()
    monkeypatch.setenv("GEMINI_BRIDGE_TIMEOUT", "abc")
    assert mcp_server._get_timeout() == 120  # Updated from 60 to 120
    assert "must be integer" in caplog.text


def test_execute_gemini_simple_requires_cli(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: None)
    response = mcp_server.execute_gemini_simple("Hello", str(tmp_path))
    assert "Gemini CLI not found" in response


def test_execute_gemini_simple_invalid_directory(monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")
    response = mcp_server.execute_gemini_simple("Hello", "non-existent-path")
    assert "Directory does not exist" in response


def test_execute_gemini_simple_success(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")

    def fake_run(cmd, cwd, capture_output, text, timeout, input):
        # Updated to expect --skip-trust flag
        assert cmd == ["gemini", "-m", "gemini-2.5-flash", "--skip-trust"]
        assert cwd == str(tmp_path)
        assert input == "Hello"
        return SimpleNamespace(returncode=0, stdout="Answer\n", stderr="")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    response = mcp_server.execute_gemini_simple("Hello", str(tmp_path))
    assert response == "Answer"


def test_execute_gemini_simple_timeout_override(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")

    def fake_run(cmd, cwd, capture_output, text, timeout, input):
        assert timeout == 5
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    response = mcp_server.execute_gemini_simple("Hello", str(tmp_path), timeout_seconds=5)
    assert response == "ok"


def test_execute_gemini_simple_handles_cli_error(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    response = mcp_server.execute_gemini_simple("Hello", str(tmp_path))
    assert "Gemini CLI Error: boom" in response


def test_execute_gemini_simple_handles_model_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="Model not available for free tier")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    response = mcp_server.execute_gemini_simple("Hello", str(tmp_path), model="pro")
    assert "not be available for your account" in response
    assert "Try: 'flash', 'flash-lite', or 'auto'" in response


def test_execute_gemini_simple_handles_auth_error(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="Authentication required")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    response = mcp_server.execute_gemini_simple("Hello", str(tmp_path))
    assert "Authentication required" in response
    assert "gemini auth login" in response


def test_execute_gemini_simple_handles_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs["timeout"])

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    response = mcp_server.execute_gemini_simple("Hello", str(tmp_path))
    assert "command timed out" in response
    assert "Try increasing timeout" in response


def test_execute_gemini_simple_handles_missing_cli(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: None)

    response = mcp_server.execute_gemini_simple("Hello", str(tmp_path))
    assert "Gemini CLI not found" in response
    assert "npm install -g @google/gemini-cli" in response


def test_execute_gemini_with_files_requires_files(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")
    result = mcp_server.execute_gemini_with_files("Hello", str(tmp_path), files=None)
    assert "No files provided" in result


def test_execute_gemini_with_files_reads_files(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")
    sample_file = tmp_path / "example.txt"
    sample_file.write_text("content", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        # Updated to expect --skip-trust flag
        assert cmd == ["gemini", "-m", "gemini-2.5-flash", "--skip-trust"]
        assert "=== example.txt ===" in kwargs["input"]
        assert "content" in kwargs["input"]
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    result = mcp_server.execute_gemini_with_files("Hello", str(tmp_path), files=["example.txt"])
    assert result == "ok"


def test_execute_gemini_with_files_marks_missing_files(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    result = mcp_server.execute_gemini_with_files("Hello", str(tmp_path), files=["missing.txt"])
    assert "Warnings" in result
    assert "Skipped missing file" in result


def test_execute_gemini_with_files_rejects_unknown_mode(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")
    sample_file = tmp_path / "example.txt"
    sample_file.write_text("content", encoding="utf-8")

    result = mcp_server.execute_gemini_with_files(
        "Hello",
        str(tmp_path),
        files=["example.txt"],
        mode="unsupported",
    )
    assert "Unsupported files mode" in result


def test_execute_gemini_with_files_timeout_override(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")
    sample_file = tmp_path / "example.txt"
    sample_file.write_text("content", encoding="utf-8")

    def fake_run(cmd, cwd, capture_output, text, timeout, input):
        assert timeout == 12
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    result = mcp_server.execute_gemini_with_files(
        "Hello",
        str(tmp_path),
        files=["example.txt"],
        timeout_seconds=12,
    )
    assert result == "ok"


def test_execute_gemini_with_files_truncates_large_file(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")
    monkeypatch.setattr("src.mcp_server.MAX_INLINE_FILE_BYTES", 10)
    monkeypatch.setattr("src.mcp_server.MAX_INLINE_TOTAL_BYTES", 100)
    monkeypatch.setattr("src.mcp_server.INLINE_CHUNK_HEAD_BYTES", 4)
    monkeypatch.setattr("src.mcp_server.INLINE_CHUNK_TAIL_BYTES", 4)

    sample_file = tmp_path / "big.txt"
    sample_file.write_text("0123456789abcdefghij", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        assert "Content truncated" in kwargs["input"]
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    result = mcp_server.execute_gemini_with_files("Hello", str(tmp_path), files=["big.txt"])
    assert "Truncated big.txt" in result


def test_execute_gemini_with_files_at_command(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")
    sample_file = tmp_path / "context" / "info.txt"
    sample_file.parent.mkdir()
    sample_file.write_text("data", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        provided_input = kwargs["input"]
        assert "@context/info.txt" in provided_input
        assert "Hello" in provided_input
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    result = mcp_server.execute_gemini_with_files(
        "Hello",
        str(tmp_path),
        files=["context/info.txt"],
        mode="at_command",
    )
    assert result == "ok"


def test_execute_gemini_with_files_at_command_warns_on_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")

    def fake_run(cmd, **kwargs):
        # No @ lines should be present when files missing
        assert "@" not in kwargs["input"]
        return SimpleNamespace(returncode=0, stdout="done", stderr="")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    result = mcp_server.execute_gemini_with_files(
        "Hello",
        str(tmp_path),
        files=["missing.txt"],
        mode="at_command",
    )
    assert "No readable files" in result


def test_consult_gemini_with_files_requires_list(tmp_path):
    result = mcp_server.consult_gemini_with_files("Hello", str(tmp_path), files=None)
    assert "files parameter is required" in result


def test_web_search_prepends_search_instruction(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")

    def fake_run(cmd, **kwargs):
        # Updated to expect --skip-trust flag
        assert cmd == ["gemini", "-m", "gemini-2.5-flash", "--skip-trust"]
        assert "Please use web search to find current information about" in kwargs["input"]
        assert "Python version" in kwargs["input"]
        return SimpleNamespace(returncode=0, stdout="Search results", stderr="")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    result = mcp_server.web_search("Python version", str(tmp_path))
    assert "Search results" in result


def test_web_search_passes_model_and_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")

    def fake_run(cmd, cwd, capture_output, text, timeout, input):
        # Updated to expect --skip-trust flag
        assert cmd == ["gemini", "-m", "gemini-2.5-pro", "--skip-trust"]
        assert timeout == 30
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    result = mcp_server.web_search("test", str(tmp_path), model="pro", timeout_seconds=30)
    assert result == "ok"


def test_web_search_with_3_1_flash_lite_model(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")

    def fake_run(cmd, cwd, capture_output, text, timeout, input):
        # Updated to expect --skip-trust flag
        assert cmd == ["gemini", "-m", "gemini-3.1-flash-lite-preview", "--skip-trust"]
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    result = mcp_server.web_search("test", str(tmp_path), model="3.1-flash-lite")
    assert result == "ok"


def test_web_search_with_2_5_lite_alias(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")

    def fake_run(cmd, cwd, capture_output, text, timeout, input):
        # Updated to expect --skip-trust flag
        assert cmd == ["gemini", "-m", "gemini-2.5-flash-lite", "--skip-trust"]
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    result = mcp_server.web_search("test", str(tmp_path), model="2.5-lite")
    assert result == "ok"


# ============================================================================
# NEW TESTS: Enhanced Configuration and Trust Functionality
# ============================================================================

def test_trust_workspace_enabled_by_default(tmp_path, monkeypatch):
    """Test that trust workspace is enabled by default for MCP usage."""
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")

    def fake_run(cmd, **kwargs):
        # Should include --skip-trust flag by default
        assert "--skip-trust" in cmd
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    result = mcp_server.execute_gemini_simple("Hello", str(tmp_path))
    assert result == "ok"


def test_trust_workspace_can_be_disabled(tmp_path, monkeypatch):
    """Test that trust workspace can be disabled via environment variable."""
    import importlib

    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")
    monkeypatch.setenv("GEMINI_BRIDGE_TRUST_WORKSPACE", "false")
    importlib.reload(mcp_server)  # Reload to pick up environment variable

    def fake_run(cmd, **kwargs):
        # Should NOT include --skip-trust flag when disabled
        assert "--skip-trust" not in cmd
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    result = mcp_server.execute_gemini_simple("Hello", str(tmp_path))
    assert result == "ok"


def test_trust_workspace_with_files(tmp_path, monkeypatch):
    """Test that trust flag is added for file operations too."""
    import importlib

    # Ensure we have clean environment state
    monkeypatch.delenv("GEMINI_BRIDGE_TRUST_WORKSPACE", raising=False)
    importlib.reload(mcp_server)

    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")
    sample_file = tmp_path / "test.txt"
    sample_file.write_text("content")

    # Track the actual command that was passed
    actual_cmd = []

    def fake_run(cmd, **kwargs):
        # Capture the command for verification
        actual_cmd.append(cmd)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    result = mcp_server.execute_gemini_with_files("Analyze", str(tmp_path), files=["test.txt"])

    # Verify the command includes --skip-trust
    assert len(actual_cmd) > 0, "fake_run was not called"
    assert "--skip-trust" in actual_cmd[0], f"Expected --skip-trust in command: {actual_cmd[0]}"
    assert "ok" in result


def test_increased_default_file_limits(monkeypatch):
    """Test that default file limits have been increased."""
    # Test new defaults
    assert mcp_server.MAX_INLINE_FILE_COUNT == 30  # Increased from 10
    assert mcp_server.MAX_INLINE_TOTAL_BYTES == 1024 * 1024  # 1MB instead of 512KB
    assert mcp_server.MAX_INLINE_FILE_BYTES == 512 * 1024  # 512KB instead of 256KB


def test_file_limits_can_be_customized(monkeypatch):
    """Test that file limits can be customized via environment variables."""
    monkeypatch.setenv("GEMINI_BRIDGE_MAX_INLINE_FILE_COUNT", "50")
    monkeypatch.setenv("GEMINI_BRIDGE_MAX_INLINE_TOTAL_BYTES", str(2 * 1024 * 1024))
    monkeypatch.setenv("GEMINI_BRIDGE_MAX_INLINE_FILE_BYTES", str(1024 * 1024))

    # Need to reload the module to pick up new environment variables
    import importlib
    importlib.reload(mcp_server)

    assert mcp_server.MAX_INLINE_FILE_COUNT == 50
    assert mcp_server.MAX_INLINE_TOTAL_BYTES == 2 * 1024 * 1024
    assert mcp_server.MAX_INLINE_FILE_BYTES == 1024 * 1024


def test_timeout_uses_per_call_override(tmp_path, monkeypatch):
    """Test that per-call timeout override works correctly."""
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")

    def fake_run(cmd, cwd, capture_output, text, timeout, input):
        # Per-call timeout should override default
        assert timeout == 45
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    result = mcp_server.execute_gemini_simple("Hello", str(tmp_path), timeout_seconds=45)
    assert result == "ok"


def test_default_timeout_env_var_priority(monkeypatch):
    """Test that GEMINI_BRIDGE_TIMEOUT takes priority over DEFAULT_TIMEOUT."""
    # Set default timeout to 180
    monkeypatch.setenv("GEMINI_BRIDGE_DEFAULT_TIMEOUT", "180")

    # Need to reload module to pick up environment variable
    import importlib
    importlib.reload(mcp_server)

    # Without GEMINI_BRIDGE_TIMEOUT, should use DEFAULT_TIMEOUT (180)
    assert mcp_server._get_timeout() == 180

    # With GEMINI_BRIDGE_TIMEOUT set, it should take priority
    monkeypatch.setenv("GEMINI_BRIDGE_TIMEOUT", "90")
    assert mcp_server._get_timeout() == 90


def test_execute_gemini_simple_with_custom_default_model(tmp_path, monkeypatch):
    """Test that custom default model is used when no model is specified."""
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")
    monkeypatch.setenv("GEMINI_BRIDGE_DEFAULT_MODEL", "pro")

    # Reload to pick up environment variable
    import importlib
    importlib.reload(mcp_server)

    def fake_run(cmd, **kwargs):
        # Should use custom default model (pro -> gemini-2.5-pro)
        assert cmd == ["gemini", "-m", "gemini-2.5-pro", "--skip-trust"]
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    result = mcp_server.execute_gemini_simple("Hello", str(tmp_path))
    assert result == "ok"


def test_web_search_with_custom_default_model(tmp_path, monkeypatch):
    """Test that web search respects custom default model."""
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")
    monkeypatch.setenv("GEMINI_BRIDGE_DEFAULT_MODEL", "flash-lite")

    # Reload to pick up environment variable
    import importlib
    importlib.reload(mcp_server)

    def fake_run(cmd, **kwargs):
        # Should use custom default model (flash-lite -> gemini-2.5-flash-lite)
        assert cmd == ["gemini", "-m", "gemini-2.5-flash-lite", "--skip-trust"]
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    result = mcp_server.web_search("test query", str(tmp_path))
    assert result == "ok"
