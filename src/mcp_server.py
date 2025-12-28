#!/usr/bin/env python3
"""
Gemini MCP Server - Simple CLI Bridge
Version 1.2.0
A minimal MCP server to interface with Gemini AI via the gemini CLI.
Created by @shelakh/elyin
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import List, Optional, Tuple

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("gemini-assistant")

# Inline attachment safeguards — tuned for quick, safe transfers.
MAX_INLINE_FILE_COUNT = int(os.getenv("GEMINI_BRIDGE_MAX_INLINE_FILE_COUNT", "10"))
MAX_INLINE_TOTAL_BYTES = int(os.getenv("GEMINI_BRIDGE_MAX_INLINE_TOTAL_BYTES", str(512 * 1024)))
MAX_INLINE_FILE_BYTES = int(os.getenv("GEMINI_BRIDGE_MAX_INLINE_FILE_BYTES", str(256 * 1024)))
INLINE_CHUNK_HEAD_BYTES = int(os.getenv("GEMINI_BRIDGE_INLINE_HEAD_BYTES", str(64 * 1024)))
INLINE_CHUNK_TAIL_BYTES = int(os.getenv("GEMINI_BRIDGE_INLINE_TAIL_BYTES", str(32 * 1024)))


def _normalize_model_name(model: Optional[str]) -> str:
    """
    Normalize user-provided model identifiers to canonical Gemini CLI model names.
    Defaults to gemini-2.5-flash when not provided or unrecognized.

    Accepted forms:
    - "flash", "2.5-flash", "gemini-2.5-flash" -> gemini-2.5-flash
    - "pro", "2.5-pro", "gemini-2.5-pro" -> gemini-2.5-pro
    - "3-pro", "gemini-3-pro", "gemini-3-pro-preview" -> gemini-3-pro-preview
    - "3-flash", "gemini-3-flash", "gemini-3-flash-preview" -> gemini-3-flash-preview
    - "auto" -> auto (model router, lets CLI choose optimal model)
    """
    if not model:
        return "gemini-2.5-flash"
    value = model.strip().lower()

    # Gemini 2.5 aliases
    if value in {"flash", "2.5-flash", "gemini-2.5-flash"}:
        return "gemini-2.5-flash"
    if value in {"pro", "2.5-pro", "gemini-2.5-pro"}:
        return "gemini-2.5-pro"

    # Gemini 3 aliases (preview models)
    if value in {"3-pro", "gemini-3-pro", "gemini-3-pro-preview"}:
        return "gemini-3-pro-preview"
    if value in {"3-flash", "gemini-3-flash", "gemini-3-flash-preview"}:
        return "gemini-3-flash-preview"

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
    Defaults to 60 seconds if not set or invalid.
    
    Returns:
        Timeout value in seconds (positive integer)
    """
    timeout_str = os.getenv("GEMINI_BRIDGE_TIMEOUT")
    if not timeout_str:
        return 60

    try:
        timeout = int(timeout_str)
        if timeout <= 0:
            logging.warning("Invalid GEMINI_BRIDGE_TIMEOUT value '%s' (must be positive). Using default 60 seconds.", timeout_str)
            return 60
        return timeout
    except ValueError:
        logging.warning("Invalid GEMINI_BRIDGE_TIMEOUT value '%s' (must be integer). Using default 60 seconds.", timeout_str)
        return 60


def _coerce_timeout(timeout_seconds: Optional[int]) -> int:
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


def _resolve_path(directory: str, candidate: str) -> Tuple[str, Optional[str]]:
    """Return absolute path and relative display path rooted at directory."""
    abs_path = candidate if os.path.isabs(candidate) else os.path.join(directory, candidate)
    try:
        rel_path = os.path.relpath(abs_path, directory)
    except ValueError:
        rel_path = None
    if rel_path and rel_path.startswith(".."):
        rel_path = None
    return abs_path, rel_path


def _read_file_for_inline(abs_path: str) -> Tuple[str, bool, int]:
    """Read file with truncation safeguards.

    Returns tuple of (content, truncated flag, bytes_used).
    """
    size = os.path.getsize(abs_path)
    truncated = False

    if size <= MAX_INLINE_FILE_BYTES:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as handle:
            content = handle.read()
        return content, truncated, min(size, MAX_INLINE_FILE_BYTES)

    truncated = True
    head_bytes = max(INLINE_CHUNK_HEAD_BYTES, 1)
    tail_bytes = max(INLINE_CHUNK_TAIL_BYTES, 0)

    with open(abs_path, "rb") as handle:
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


def _prepare_inline_payload(directory: str, files: List[str]) -> Tuple[str, List[str]]:
    """Return stdin payload for inline mode and any warnings."""
    warnings: List[str] = []
    file_blocks: List[str] = []
    total_bytes = 0
    processed = 0

    if MAX_INLINE_FILE_COUNT <= 0:
        warnings.append("Inline attachments disabled via MAX_INLINE_FILE_COUNT<=0")
        return "", warnings

    for original_path in files:
        abs_path, rel_path = _resolve_path(directory, original_path)
        display_name = rel_path or os.path.basename(abs_path)

        if not os.path.exists(abs_path):
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


def _prepare_at_command_prompt(directory: str, files: List[str]) -> Tuple[str, List[str]]:
    """Return prompt lines for @-command usage and warnings."""
    warnings: List[str] = []
    prompt_lines: List[str] = []

    for original_path in files:
        abs_path, rel_path = _resolve_path(directory, original_path)
        if not os.path.exists(abs_path):
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
    model: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
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
    if not os.path.isdir(directory):
        return f"Error: Directory does not exist: {directory}"
    
    # Build command - use stdin for input to avoid hanging
    selected_model = _normalize_model_name(model)
    cmd = ["gemini", "-m", selected_model]
    
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
            return f"Gemini CLI Error: {result.stderr.strip()}"
            
    except subprocess.TimeoutExpired:
        return f"Error: Gemini CLI command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error executing Gemini CLI: {str(e)}"


def execute_gemini_with_files(
    query: str,
    directory: str = ".",
    files: Optional[List[str]] = None,
    model: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
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
    if not os.path.isdir(directory):
        return f"Error: Directory does not exist: {directory}"
    
    # Validate files parameter
    if not files:
        return "Error: No files provided for file attachment mode"
    
    # Build command - use stdin for input to avoid hanging
    selected_model = _normalize_model_name(model)
    cmd = ["gemini", "-m", selected_model]

    mode_normalized = mode.lower()
    warnings: List[str]

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
            output = f"Gemini CLI Error: {result.stderr.strip()}"

        if warnings:
            warning_block = "Warnings:\n" + "\n".join(f"- {w}" for w in warnings)
            return f"{warning_block}\n\n{output}"
        return output

    except subprocess.TimeoutExpired:
        return f"Error: Gemini CLI command timed out after {timeout} seconds"
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


def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
