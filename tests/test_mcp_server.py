import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import src.mcp_server as mcp_server


@pytest.fixture(autouse=True)
def clear_timeout_env(monkeypatch):
    monkeypatch.delenv("GEMINI_BRIDGE_TIMEOUT", raising=False)


def test_normalize_model_name_defaults():
    assert mcp_server._normalize_model_name(None) == "gemini-2.5-flash"
    assert mcp_server._normalize_model_name("  flash  ") == "gemini-2.5-flash"


def test_normalize_model_name_pro_alias():
    assert mcp_server._normalize_model_name("pro") == "gemini-2.5-pro"
    assert mcp_server._normalize_model_name("2.5-pro") == "gemini-2.5-pro"


def test_normalize_model_name_passthrough():
    assert mcp_server._normalize_model_name("gemini-exp-1201") == "gemini-exp-1201"


def test_get_timeout_defaults_to_60():
    assert mcp_server._get_timeout() == 60


def test_get_timeout_returns_positive_integer(monkeypatch):
    monkeypatch.setenv("GEMINI_BRIDGE_TIMEOUT", "120")
    assert mcp_server._get_timeout() == 120


def test_get_timeout_handles_invalid_values(monkeypatch, caplog):
    caplog.set_level("WARNING")
    monkeypatch.setenv("GEMINI_BRIDGE_TIMEOUT", "-5")
    assert mcp_server._get_timeout() == 60
    assert "must be positive" in caplog.text

    caplog.clear()
    monkeypatch.setenv("GEMINI_BRIDGE_TIMEOUT", "abc")
    assert mcp_server._get_timeout() == 60
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
        assert cmd == ["gemini", "-m", "gemini-2.5-flash"]
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
    assert response == "Gemini CLI Error: boom"


def test_execute_gemini_simple_handles_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs["timeout"])

    monkeypatch.setattr("src.mcp_server.subprocess.run", fake_run)
    response = mcp_server.execute_gemini_simple("Hello", str(tmp_path))
    assert "command timed out" in response


def test_execute_gemini_with_files_requires_files(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")
    result = mcp_server.execute_gemini_with_files("Hello", str(tmp_path), files=None)
    assert "No files provided" in result


def test_execute_gemini_with_files_reads_files(tmp_path, monkeypatch):
    monkeypatch.setattr("src.mcp_server.shutil.which", lambda _: "gemini")
    sample_file = tmp_path / "example.txt"
    sample_file.write_text("content", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        assert cmd == ["gemini", "-m", "gemini-2.5-flash"]
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
