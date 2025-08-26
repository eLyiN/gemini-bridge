#!/usr/bin/env python3
"""
Gemini MCP Server - Simple CLI Bridge
Version 1.0.2
A minimal MCP server to interface with Gemini AI via the gemini CLI.
Created by @shelakh/elyin
"""

import logging
import os
import shutil
import subprocess
from typing import List, Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("gemini-assistant")


def _normalize_model_name(model: Optional[str]) -> str:
    """
    Normalize user-provided model identifiers to canonical Gemini CLI model names.
    Defaults to gemini-2.5-flash when not provided or unrecognized.

    Accepted forms:
    - "flash", "2.5-flash", "gemini-2.5-flash"
    - "pro", "2.5-pro", "gemini-2.5-pro"
    """
    if not model:
        return "gemini-2.5-flash"
    value = model.strip().lower()
    # Common short aliases
    if value in {"flash", "2.5-flash", "gemini-2.5-flash"}:
        return "gemini-2.5-flash"
    if value in {"pro", "2.5-pro", "gemini-2.5-pro"}:
        return "gemini-2.5-pro"
    # If the caller passed a full model name, keep it
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


def execute_gemini_simple(query: str, directory: str = ".", model: Optional[str] = None) -> str:
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
    timeout = _get_timeout()
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


def execute_gemini_with_files(query: str, directory: str = ".", files: Optional[List[str]] = None, model: Optional[str] = None) -> str:
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
    
    # Read and concatenate file contents
    file_contents = []
    for file_path in files:
        try:
            # Convert relative paths to absolute based on directory
            if not os.path.isabs(file_path):
                file_path = os.path.join(directory, file_path)
            
            if os.path.isfile(file_path):
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    file_contents.append(f"=== {os.path.basename(file_path)} ===\n{content}")
            else:
                file_contents.append(f"=== {os.path.basename(file_path)} ===\n[File not found]")
        except Exception as e:
            file_contents.append(f"=== {os.path.basename(file_path)} ===\n[Error reading file: {str(e)}]")
    
    # Combine file contents with query
    stdin_content = "\n\n".join(file_contents) + "\n\n" + query
    
    # Execute CLI command - simple timeout, no retries
    timeout = _get_timeout()
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
            return result.stdout.strip() if result.stdout.strip() else "No output from Gemini CLI"
        else:
            return f"Gemini CLI Error: {result.stderr.strip()}"
            
    except subprocess.TimeoutExpired:
        return f"Error: Gemini CLI command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error executing Gemini CLI: {str(e)}"


@mcp.tool()
def consult_gemini(
    query: str,
    directory: str,
    model: Optional[str] = None
) -> str:
    """
    Send a query directly to Gemini CLI.
    
    This is the core function - a direct bridge between Claude and Gemini.
    No caching, no sessions, no complexity. Just execute and return.
    
    Args:
        query: The question or prompt to send to Gemini
        directory: Working directory (required)
        model: Optional model name (flash, pro, etc.)
        
    Returns:
        Gemini's response
    """
    return execute_gemini_simple(query, directory, model)


@mcp.tool()
def consult_gemini_with_files(
    query: str,
    directory: str,
    files: Optional[List[str]] = None,
    model: Optional[str] = None
) -> str:
    """
    Send a query to Gemini CLI with file attachments.
    
    Files are read and concatenated into the prompt. Simple and direct.
    
    Args:
        query: The question or prompt to send to Gemini
        directory: Working directory (required)
        files: List of file paths to attach (relative to directory)
        model: Optional model name (flash, pro, etc.)
        
    Returns:
        Gemini's response with file context
    """
    if not files:
        return "Error: files parameter is required for consult_gemini_with_files"
    return execute_gemini_with_files(query, directory, files, model)


def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()