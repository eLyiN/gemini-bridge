#!/usr/bin/env python3
"""
Gemini MCP Server - Simple CLI Bridge
Version 1.3.0
A minimal MCP server to interface with Gemini AI via the gemini CLI.
Created by @shelakh/elyin
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("gemini-assistant")

# ============================================================================
# CONFIGURATION - Environment Variables with Sensible Defaults
# ============================================================================

# Timeout Configuration
DEFAULT_TIMEOUT = int(os.getenv("GEMINI_BRIDGE_DEFAULT_TIMEOUT", "120"))  # Increased from 60 to 120 seconds
TRUST_WORKSPACE = os.getenv("GEMINI_BRIDGE_TRUST_WORKSPACE", "true")  # Auto-trust workspaces for MCP usage

# Default Model Configuration
DEFAULT_MODEL = os.getenv("GEMINI_BRIDGE_DEFAULT_MODEL", "flash")  # Options: flash, pro, flash-lite, auto

# Inline attachment safeguards — tuned for quick, safe transfers.
MAX_INLINE_FILE_COUNT = int(os.getenv("GEMINI_BRIDGE_MAX_INLINE_FILE_COUNT", "30"))  # Increased from 10 to 30
MAX_INLINE_TOTAL_BYTES = int(os.getenv("GEMINI_BRIDGE_MAX_INLINE_TOTAL_BYTES", str(1024 * 1024)))  # 1MB instead of 512KB
MAX_INLINE_FILE_BYTES = int(os.getenv("GEMINI_BRIDGE_MAX_INLINE_FILE_BYTES", str(512 * 1024)))  # 512KB instead of 256KB
INLINE_CHUNK_HEAD_BYTES = int(os.getenv("GEMINI_BRIDGE_INLINE_HEAD_BYTES", str(64 * 1024)))
INLINE_CHUNK_TAIL_BYTES = int(os.getenv("GEMINI_BRIDGE_INLINE_TAIL_BYTES", str(32 * 1024)))


def _normalize_model_name(model: str | None) -> str:
    """
    Normalize user-provided model identifiers to canonical Gemini CLI model names.
    Defaults to DEFAULT_MODEL environment variable or gemini-2.5-flash when not provided or unrecognized.

    Accepted forms:
    - "flash", "2.5-flash", "gemini-2.5-flash" -> gemini-2.5-flash
    - "pro", "2.5-pro", "gemini-2.5-pro" -> gemini-2.5-pro
    - "flash-lite", "2.5-flash-lite", "2.5-lite", "gemini-2.5-flash-lite", "gemini-2.5-lite" -> gemini-2.5-flash-lite
    - "3-pro", "gemini-3-pro", "gemini-3-pro-preview" -> gemini-3-pro-preview
    - "3-flash", "gemini-3-flash", "gemini-3-flash-preview" -> gemini-3-flash-preview
    - "3.1-pro", "gemini-3.1-pro", "gemini-3.1-pro-preview" -> gemini-3.1-pro-preview
    - "3.1-flash-lite", "gemini-3.1-flash-lite", "gemini-3.1-flash-lite-preview" -> gemini-3.1-flash-lite-preview
    - "auto" -> auto (model router, lets CLI choose optimal model)
    """
    if not model:
        model = DEFAULT_MODEL

    value = model.strip().lower()

    # Gemini 2.5 aliases
    if value in {"flash", "2.5-flash", "gemini-2.5-flash"}:
        return "gemini-2.5-flash"
    if value in {"pro", "2.5-pro", "gemini-2.5-pro"}:
        return "gemini-2.5-pro"

    # Gemini 2.5 Lite
    if value in {"flash-lite", "2.5-flash-lite", "2.5-lite", "gemini-2.5-flash-lite", "gemini-2.5-lite"}:
        return "gemini-2.5-flash-lite"

    # Gemini 3 aliases (preview models)
    if value in {"3-pro", "gemini-3-pro", "gemini-3-pro-preview"}:
        return "gemini-3-pro-preview"
    if value in {"3-flash", "gemini-3-flash", "gemini-3-flash-preview"}:
        return "gemini-3-flash-preview"

    # Gemini 3.1 series
    if value in {"3.1-pro", "gemini-3.1-pro", "gemini-3.1-pro-preview"}:
        return "gemini-3.1-pro-preview"
    if value in {"3.1-flash-lite", "gemini-3.1-flash-lite", "gemini-3.1-flash-lite-preview"}:
        return "gemini-3.1-flash-lite-preview"

    # Model router (let CLI choose best model)
    if value == "auto":
        return "auto"

    # Pass through any other gemini-* model name
    if value.startswith("gemini-"):
        return value

    # Fallback to flash for anything else
    return "gemini-2.5-flash"


def _get_timeout() -> int:
    """
    Get the timeout value from environment variable GEMINI_BRIDGE_TIMEOUT.
    Defaults to DEFAULT_TIMEOUT (120 seconds) if not set or invalid.

    Returns:
        Timeout value in seconds (positive integer)
    """
    timeout_str = os.getenv("GEMINI_BRIDGE_TIMEOUT")
    if not timeout_str:
        return DEFAULT_TIMEOUT

    try:
        timeout = int(timeout_str)
        if timeout <= 0:
            logging.warning("Invalid GEMINI_BRIDGE_TIMEOUT value '%s' (must be positive). Using default %d seconds.", timeout_str, DEFAULT_TIMEOUT)
            return DEFAULT_TIMEOUT
        return timeout
    except ValueError:
        logging.warning("Invalid GEMINI_BRIDGE_TIMEOUT value '%s' (must be integer). Using default %d seconds.", timeout_str, DEFAULT_TIMEOUT)
        return DEFAULT_TIMEOUT


def _coerce_timeout(timeout_seconds: int | None) -> int:
    """Return a positive timeout, preferring explicit overrides."""
    if timeout_seconds is None:
        return _get_timeout()

    try:
        timeout = int(timeout_seconds)
    except (TypeError, ValueError):
        logging.warning(
            "Invalid timeout override '%s' (must be integer). Using default.",
            timeout_seconds,
        )
        return _get_timeout()

    if timeout <= 0:
        logging.warning(
            "Invalid timeout override '%s' (must be positive). Using default.",
            timeout_seconds,
        )
        return _get_timeout()

    return timeout


def _resolve_path(directory: str, candidate: str) -> tuple[str, str | None]:
    """Return absolute path and relative display path rooted at directory."""
    candidate_path = Path(candidate)
    abs_path = (
        str(candidate_path)
        if candidate_path.is_absolute()
        else str(Path(directory) / candidate)
    )
    try:
        rel_path = os.path.relpath(abs_path, directory)
    except ValueError:
        rel_path = None
    if rel_path and rel_path.startswith(".."):
        rel_path = None
    return abs_path, rel_path


def _read_file_for_inline(abs_path: str) -> tuple[str, bool, int]:
    """Read file with truncation safeguards.

    Returns tuple of (content, truncated flag, bytes_used).
    """
    abs_path_obj = Path(abs_path)
    size = abs_path_obj.stat().st_size
    truncated = False

    if size <= MAX_INLINE_FILE_BYTES:
        with abs_path_obj.open(encoding="utf-8", errors="ignore") as handle:
            content = handle.read()
        return content, truncated, min(size, MAX_INLINE_FILE_BYTES)

    truncated = True
    head_bytes = max(INLINE_CHUNK_HEAD_BYTES, 1)
    tail_bytes = max(INLINE_CHUNK_TAIL_BYTES, 0)

    with abs_path_obj.open("rb") as handle:
        head = handle.read(head_bytes)
        tail = b""
        if tail_bytes > 0 and size > head_bytes:
            handle.seek(max(size - tail_bytes, 0))
            tail = handle.read(tail_bytes)

    head_text = head.decode("utf-8", errors="ignore")
    tail_text = tail.decode("utf-8", errors="ignore") if tail else ""

    snippet = head_text
    if tail_text:
        snippet += "\n\n[... truncated ...]\n\n" + tail_text

    bytes_counted = min(size, MAX_INLINE_FILE_BYTES)
    return snippet, truncated, bytes_counted


def _prepare_inline_payload(directory: str, files: list[str]) -> tuple[str, list[str]]:
    """Return stdin payload for inline mode and any warnings."""
    warnings: list[str] = []
    file_blocks: list[str] = []
    total_bytes = 0
    processed = 0

    if MAX_INLINE_FILE_COUNT <= 0:
        warnings.append("Inline attachments disabled via MAX_INLINE_FILE_COUNT<=0")
        return "", warnings

    for original_path in files:
        abs_path, rel_path = _resolve_path(directory, original_path)
        display_name = rel_path or Path(abs_path).name

        if not Path(abs_path).exists():
            warnings.append(f"Skipped missing file: {display_name}")
            continue

        if processed >= MAX_INLINE_FILE_COUNT:
            warnings.append(
                f"Inline file limit reached ({MAX_INLINE_FILE_COUNT}); skipped remaining attachments",
            )
            break

        try:
            content, truncated, bytes_used = _read_file_for_inline(abs_path)
        except Exception as exc:  # IOError or decoding issues
            warnings.append(f"Error reading {display_name}: {exc}")
            continue

        if total_bytes + bytes_used > MAX_INLINE_TOTAL_BYTES:
            warnings.append(
                f"Inline payload exceeded {MAX_INLINE_TOTAL_BYTES} bytes; skipped {display_name} and remaining attachments",
            )
            break

        block_header = f"=== {display_name} ==="
        if truncated:
            block_header += "\n[gemini-bridge] Content truncated for inline transfer"
        file_blocks.append(f"{block_header}\n{content}")

        if truncated:
            warnings.append(
                f"Truncated {display_name}; only the first {INLINE_CHUNK_HEAD_BYTES}B and last {INLINE_CHUNK_TAIL_BYTES}B were sent",
            )

        total_bytes += bytes_used
        processed += 1

    payload = "\n\n".join(file_blocks)
    return payload, warnings


def _prepare_at_command_prompt(directory: str, files: list[str]) -> tuple[str, list[str]]:
    """Return prompt lines for @-command usage and warnings."""
    warnings: list[str] = []
    prompt_lines: list[str] = []

    for original_path in files:
        abs_path, rel_path = _resolve_path(directory, original_path)
        if not Path(abs_path).exists():
            warnings.append(f"Skipped missing file: {original_path}")
            continue
        if rel_path is None:
            warnings.append(
                f"Skipped file outside working directory: {original_path}",
            )
            continue
        prompt_lines.append(f"@{rel_path}")

    if not prompt_lines:
        warnings.append("No readable files resolved for @ command; prompt unchanged")

    prompt = "\n".join(prompt_lines)
    return prompt, warnings


def execute_gemini_simple(
    query: str,
    directory: str = ".",
    model: str | None = None,
    timeout_seconds: int | None = None,
) -> str:
    """
    Execute gemini CLI command for simple queries without file attachments.
    
    Args:
        query: The prompt to send to Gemini
        directory: Working directory for the command
        model: Optional model name (flash, pro, etc.)
        
    Returns:
        CLI output or error message
    """
    # Check if gemini CLI is available
    if not shutil.which("gemini"):
        return "Error: Gemini CLI not found. Install with: npm install -g @google/gemini-cli"

    # Validate directory
    if not Path(directory).is_dir():
        return f"Error: Directory does not exist: {directory}"
    
    # Build command - use stdin for input to avoid hanging
    selected_model = _normalize_model_name(model)
    cmd = ["gemini", "-m", selected_model]

    # Add trust flag for automated environments if enabled
    if TRUST_WORKSPACE.lower() == "true":
        cmd.append("--skip-trust")
    
    # Execute CLI command - simple timeout, no retries
    timeout = _coerce_timeout(timeout_seconds)
    try:
        result = subprocess.run(
            cmd,
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=query
        )
        
        if result.returncode == 0:
            return result.stdout.strip() if result.stdout.strip() else "No output from Gemini CLI"
        else:
            error_msg = result.stderr.strip()
            # Provide helpful suggestions for common errors
            if "not available" in error_msg.lower() or "unauthorized" in error_msg.lower():
                return f"Gemini CLI Error: Model '{selected_model}' may not be available for your account. Try: 'flash', 'flash-lite', or 'auto'. Details: {error_msg}"
            elif "authentication" in error_msg.lower() or "auth" in error_msg.lower():
                return f"Gemini CLI Error: Authentication required. Run: gemini auth login. Details: {error_msg}"
            else:
                return f"Gemini CLI Error: {error_msg}"

    except subprocess.TimeoutExpired:
        return f"Error: Gemini CLI command timed out after {timeout} seconds. Try increasing timeout or simplifying your query."
    except FileNotFoundError:
        return "Error: Gemini CLI not found. Install with: npm install -g @google/gemini-cli"
    except Exception as e:
        return f"Error executing Gemini CLI: {str(e)}"


def execute_gemini_with_files(
    query: str,
    directory: str = ".",
    files: list[str] | None = None,
    model: str | None = None,
    timeout_seconds: int | None = None,
    mode: str = "inline",
) -> str:
    """
    Execute gemini CLI command with file attachments.
    
    Args:
        query: The prompt to send to Gemini
        directory: Working directory for the command
        files: List of file paths to attach (relative to directory)
        model: Optional model name (flash, pro, etc.)
        
    Returns:
        CLI output or error message
    """
    # Check if gemini CLI is available
    if not shutil.which("gemini"):
        return "Error: Gemini CLI not found. Install with: npm install -g @google/gemini-cli"

    # Validate directory
    if not Path(directory).is_dir():
        return f"Error: Directory does not exist: {directory}"
    
    # Validate files parameter
    if not files:
        return "Error: No files provided for file attachment mode"
    
    # Build command - use stdin for input to avoid hanging
    selected_model = _normalize_model_name(model)
    cmd = ["gemini", "-m", selected_model]

    # Add trust flag for automated environments if enabled
    if TRUST_WORKSPACE.lower() == "true":
        cmd.append("--skip-trust")

    mode_normalized = mode.lower()
    warnings: list[str]

    if mode_normalized not in {"inline", "at_command"}:
        return f"Error: Unsupported files mode '{mode}'. Use 'inline' or 'at_command'."

    if mode_normalized == "inline":
        inline_payload, warnings = _prepare_inline_payload(directory, files)
        stdin_pieces = [piece for piece in [inline_payload, query] if piece]
        stdin_content = "\n\n".join(stdin_pieces)
    else:
        at_prompt, warnings = _prepare_at_command_prompt(directory, files)
        stdin_pieces = [piece for piece in [at_prompt, query] if piece]
        stdin_content = "\n\n".join(stdin_pieces)

    # Execute CLI command - simple timeout, no retries
    timeout = _coerce_timeout(timeout_seconds)
    try:
        result = subprocess.run(
            cmd,
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=stdin_content
        )

        if result.returncode == 0:
            output = result.stdout.strip() if result.stdout.strip() else "No output from Gemini CLI"
        else:
            error_msg = result.stderr.strip()
            # Provide helpful suggestions for common errors
            if "not available" in error_msg.lower() or "unauthorized" in error_msg.lower():
                output = f"Gemini CLI Error: Model '{selected_model}' may not be available for your account. Try: 'flash', 'flash-lite', or 'auto'. Details: {error_msg}"
            elif "authentication" in error_msg.lower() or "auth" in error_msg.lower():
                output = f"Gemini CLI Error: Authentication required. Run: gemini auth login. Details: {error_msg}"
            else:
                output = f"Gemini CLI Error: {error_msg}"

        if warnings:
            warning_block = "Warnings:\n" + "\n".join(f"- {w}" for w in warnings)
            return f"{warning_block}\n\n{output}"
        return output

    except subprocess.TimeoutExpired:
        return f"Error: Gemini CLI command timed out after {timeout} seconds. Try increasing timeout or simplifying your query."
    except FileNotFoundError:
        return "Error: Gemini CLI not found. Install with: npm install -g @google/gemini-cli"
    except Exception as e:
        return f"Error executing Gemini CLI: {str(e)}"


@mcp.tool()
def consult_gemini(
    query: str,
    directory: str,
    model: str | None = None,
    timeout_seconds: int | None = None,
) -> str:
    """Send a query directly to the Gemini CLI.

    Args:
        query: Prompt text forwarded verbatim to the CLI.
        directory: Working directory used for command execution.
        model: Optional model alias (``flash``, ``pro``) or full Gemini model id.
        timeout_seconds: Optional per-call timeout override in seconds.

    Returns:
        Gemini's response text or an explanatory error string.
    """
    return execute_gemini_simple(query, directory, model, timeout_seconds)


@mcp.tool()
def consult_gemini_with_files(
    query: str,
    directory: str,
    files: list[str] | None = None,
    model: str | None = None,
    timeout_seconds: int | None = None,
    mode: str = "inline",
) -> str:
    """Send a query to the Gemini CLI with file context.

    Args:
        query: Prompt text forwarded to the CLI.
        directory: Working directory used for resolving relative file paths.
        files: Relative or absolute file paths to include alongside the prompt.
        model: Optional model alias (``flash``, ``pro``) or full Gemini model id.
        timeout_seconds: Optional per-call timeout override in seconds.
        mode: ``"inline"`` streams truncated snippets; ``"at_command"`` emits
            ``@path`` directives so Gemini CLI resolves files itself.

    Returns:
        Gemini's response or an explanatory error string with any warnings.
    """
    if not files:
        return "Error: files parameter is required for consult_gemini_with_files"
    return execute_gemini_with_files(query, directory, files, model, timeout_seconds, mode)


@mcp.tool()
def web_search(
    query: str,
    directory: str = ".",
    model: str | None = None,
    timeout_seconds: int | None = None,
) -> str:
    """Ask Gemini queries with web search context.

    Note: This uses Gemini CLI's automatic web search capability.
    The model determines when to search based on query context.
    Best-effort web search - not guaranteed for every query.

    Args:
        query: Search query or question to look up on the web
        directory: Working directory for command execution
        model: Optional model alias (flash, pro, or custom)
        timeout_seconds: Optional per-call timeout override in seconds

    Returns:
        Gemini's response with potential web sources
    """
    search_prompt = f"Please use web search to find current information about: {query}"
    return execute_gemini_simple(search_prompt, directory, model, timeout_seconds)


def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
