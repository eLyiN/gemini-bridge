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

# Configure logging for debugging timeout issues
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    logger.debug(f"Reading timeout from environment: GEMINI_BRIDGE_TIMEOUT={timeout_str}")
    
    if not timeout_str:
        logger.info("GEMINI_BRIDGE_TIMEOUT not set, using default 60 seconds")
        return 60
    
    try:
        timeout = int(timeout_str)
        if timeout <= 0:
            logger.warning(f"Invalid GEMINI_BRIDGE_TIMEOUT value '{timeout_str}' (must be positive). Using default 60 seconds.")
            return 60
        
        logger.info(f"Using configured timeout: {timeout} seconds")
        if timeout > 300:
            logger.warning(f"Large timeout configured ({timeout}s). This may cause long waits for failed operations.")
        return timeout
    except ValueError:
        logger.warning(f"Invalid GEMINI_BRIDGE_TIMEOUT value '{timeout_str}' (must be integer). Using default 60 seconds.")
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
    logger.info(f"Executing Gemini CLI with timeout: {timeout}s, model: {selected_model}, directory: {directory}")
    logger.debug(f"Query length: {len(query)} characters")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=query
        )
        
        logger.debug(f"Gemini CLI completed with return code: {result.returncode}")
        
        if result.returncode == 0:
            output = result.stdout.strip() if result.stdout.strip() else "No output from Gemini CLI"
            logger.info(f"Gemini CLI successful, output length: {len(output)} characters")
            return output
        else:
            error_msg = f"Gemini CLI Error: {result.stderr.strip()}"
            logger.error(error_msg)
            return error_msg
            
    except subprocess.TimeoutExpired:
        timeout_msg = f"Error: Gemini CLI command timed out after {timeout} seconds. Try increasing GEMINI_BRIDGE_TIMEOUT environment variable for large operations."
        logger.error(timeout_msg)
        return timeout_msg
    except Exception as e:
        error_msg = f"Error executing Gemini CLI: {str(e)}"
        logger.error(error_msg)
        return error_msg


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
    total_content_size = len(stdin_content)
    logger.info(f"Executing Gemini CLI with files, timeout: {timeout}s, model: {selected_model}, directory: {directory}")
    logger.info(f"File count: {len(files)}, total content size: {total_content_size} characters")
    
    # Warn about large content that might timeout
    if total_content_size > 100000:  # 100KB threshold
        logger.warning(f"Large content size ({total_content_size} chars). Consider increasing timeout if you experience timeouts.")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=stdin_content
        )
        
        logger.debug(f"Gemini CLI completed with return code: {result.returncode}")
        
        if result.returncode == 0:
            output = result.stdout.strip() if result.stdout.strip() else "No output from Gemini CLI"
            logger.info(f"Gemini CLI successful, output length: {len(output)} characters")
            return output
        else:
            error_msg = f"Gemini CLI Error: {result.stderr.strip()}"
            logger.error(error_msg)
            return error_msg
            
    except subprocess.TimeoutExpired:
        timeout_msg = f"Error: Gemini CLI command timed out after {timeout} seconds with {len(files)} files ({total_content_size} chars). Try increasing GEMINI_BRIDGE_TIMEOUT environment variable (current: {os.getenv('GEMINI_BRIDGE_TIMEOUT', 'not set')})."
        logger.error(timeout_msg)
        return timeout_msg
    except Exception as e:
        error_msg = f"Error executing Gemini CLI: {str(e)}"
        logger.error(error_msg)
        return error_msg


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


@mcp.tool()
def get_debug_info() -> str:
    """
    Get diagnostic information about the Gemini Bridge configuration.
    
    Useful for troubleshooting timeout issues and verifying setup.
    
    Returns:
        Formatted debug information including timeout configuration,
        environment variables, and system status
    """
    debug_info = []
    debug_info.append("=== Gemini Bridge Debug Information ===\n")
    
    # Timeout configuration
    timeout_env = os.getenv("GEMINI_BRIDGE_TIMEOUT")
    actual_timeout = _get_timeout()
    debug_info.append(f"Timeout Configuration:")
    debug_info.append(f"  GEMINI_BRIDGE_TIMEOUT env var: {timeout_env or 'not set'}")
    debug_info.append(f"  Actual timeout used: {actual_timeout} seconds")
    
    if actual_timeout == 60 and not timeout_env:
        debug_info.append(f"  ⚠️  Using default timeout. Set GEMINI_BRIDGE_TIMEOUT=240 for large operations.")
    elif actual_timeout < 120:
        debug_info.append(f"  ⚠️  Timeout may be too low for large files or complex queries.")
    elif actual_timeout > 300:
        debug_info.append(f"  ⚠️  Very high timeout configured. Failed operations will wait {actual_timeout}s.")
    else:
        debug_info.append(f"  ✓ Timeout looks reasonable for most operations.")
    
    debug_info.append("")
    
    # Gemini CLI status
    gemini_path = shutil.which("gemini")
    debug_info.append(f"Gemini CLI Status:")
    debug_info.append(f"  CLI available: {'✓ Yes' if gemini_path else '✗ No'}")
    if gemini_path:
        debug_info.append(f"  CLI path: {gemini_path}")
        try:
            # Try to get version
            result = subprocess.run(
                ["gemini", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                debug_info.append(f"  CLI version: {version}")
            else:
                debug_info.append(f"  CLI version check failed: {result.stderr.strip()}")
        except Exception as e:
            debug_info.append(f"  CLI version check error: {str(e)}")
    else:
        debug_info.append(f"  ✗ Install with: npm install -g @google/gemini-cli")
    
    debug_info.append("")
    
    # Environment information
    debug_info.append(f"Environment:")
    debug_info.append(f"  Python version: {subprocess.sys.version.split()[0]}")
    debug_info.append(f"  Current working directory: {os.getcwd()}")
    debug_info.append(f"  PORT: {os.getenv('PORT', '8080')}")
    
    # Check authentication status
    try:
        result = subprocess.run(
            ["gemini", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd="."
        )
        if result.returncode == 0:
            debug_info.append(f"  Authentication: ✓ Logged in")
        else:
            debug_info.append(f"  Authentication: ✗ Not logged in - run 'gemini auth login'")
    except Exception as e:
        debug_info.append(f"  Authentication status check failed: {str(e)}")
    
    debug_info.append("")
    
    # Recent environment variables that might affect operation
    relevant_env_vars = [
        "GEMINI_BRIDGE_TIMEOUT", "NODE_PATH", "PATH", "HOME", 
        "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT"
    ]
    
    debug_info.append(f"Relevant Environment Variables:")
    for var in relevant_env_vars:
        value = os.getenv(var)
        if value:
            # Truncate very long values
            display_value = value[:100] + "..." if len(value) > 100 else value
            debug_info.append(f"  {var}: {display_value}")
        else:
            debug_info.append(f"  {var}: not set")
    
    debug_info.append("")
    debug_info.append("=== End Debug Information ===")
    
    return "\n".join(debug_info)


def main():
    """Entry point for the MCP server."""
    port = int(os.getenv("PORT", "8080"))
    timeout = _get_timeout()  # Log timeout configuration at startup
    
    logger.info(f"Starting Gemini Bridge MCP Server on port {port}")
    logger.info(f"Configured timeout: {timeout} seconds")
    logger.info(f"Gemini CLI available: {shutil.which('gemini') is not None}")
    
    # Run the MCP server with HTTP transport
    mcp.run(transport="http", port=port)


if __name__ == "__main__":
    main()