# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Gemini Bridge** is a lightweight MCP (Model Context Protocol) server that enables Claude Code to interact with Google's Gemini AI through the official CLI. The project follows extreme simplicity principles from Carmack and Torvalds - doing ONE thing well: bridging Claude to Gemini CLI.

**Key Characteristics:**
- Zero API costs (uses free Gemini CLI)
- Stateless architecture with no session management
- Direct subprocess integration for optimal performance
- Production-ready with professional CI/CD automation

## Development Commands

### Prerequisites
- **Gemini CLI**: `npm install -g @google/gemini-cli`
- **Authentication**: `gemini auth login`
- **Verify**: `gemini --version`

### Installation & Setup

**Development Mode:**
```bash
# Clone and install in development mode
git clone https://github.com/shelakh/gemini-bridge.git
cd gemini-bridge
pip install -e .

# Run directly from source
python -m src
```

**Production Installation:**
```bash
# Install from PyPI
pip install gemini-bridge

# Or use uvx (recommended)
uvx gemini-bridge
```

**Claude Code Integration:**
```bash
# Production installation (recommended)
claude mcp add gemini-bridge -s user -- uvx gemini-bridge

# Development mode (from local source)
claude mcp add gemini-bridge -s user -- python -m src
```

### Testing & Verification
```bash
# Test CLI availability
gemini --version

# Test basic functionality
python -c "from src.mcp_server import execute_gemini_simple; print(execute_gemini_simple('Hello', '.'))"

# Test package installation
python -c "import src; print(f'Gemini Bridge v{src.__version__}')"
```

### Build & Distribution
```bash
# Clean build
rm -rf dist/ build/ *.egg-info

# Build package
uvx --from build pyproject-build

# Verify build
pip install dist/*.whl
python -c "import src; print('Package works!')"
```

## Architecture

### Core Design Principles
- **CLI-First**: Direct subprocess calls to `gemini` command
- **Stateless**: Each tool call is independent with no session state
- **Configurable Timeout**: Default 60-second execution time (configurable via GEMINI_BRIDGE_TIMEOUT)
- **Fail-Fast**: Clear error messages with simple error handling
- **Zero Dependencies**: Only `mcp>=1.0.0` and external Gemini CLI

### Key Components

**`src/mcp_server.py`** - Main server implementation
- `consult_gemini(query, directory, model)` - Simple CLI bridge
- `consult_gemini_with_files(query, directory, files, model)` - File-attachment support
- `_normalize_model_name()` - Model name normalization (flash/pro)
- `execute_gemini_simple()` - Core CLI execution
- `execute_gemini_with_files()` - File-aware CLI execution

**Model Support:**
- Default: `gemini-2.5-flash` (optimal performance/cost)
- Available: `flash`, `pro` (auto-normalized to full names)
- Custom models accepted if prefixed with `gemini-`

### File Structure
```
gemini-bridge/
├── src/
│   ├── __init__.py              # Package entry point and version
│   ├── __main__.py              # Module execution entry point  
│   └── mcp_server.py            # Main MCP server implementation
├── .github/                     # GitHub templates and workflows
├── pyproject.toml               # Python package configuration
├── README.md                    # Main documentation
├── CONTRIBUTING.md              # Development guidelines
├── SECURITY.md                  # Security policy
├── CHANGELOG.md                 # Release history
└── LICENSE                      # MIT license
```

## MCP Tools Available

### `consult_gemini`
- **Purpose**: Direct CLI bridge for simple queries
- **Parameters**: 
  - `query` (required): The question or prompt to send to Gemini
  - `directory` (required): Working directory for the query
  - `model` (optional): Model name (flash, pro, or custom)
- **Use Case**: General questions, code analysis without file attachments
- **Example**: General programming questions, code explanations

### `consult_gemini_with_files` 
- **Purpose**: CLI bridge with file attachments for detailed analysis
- **Parameters**: 
  - `query` (required): The question or prompt to send to Gemini
  - `directory` (required): Working directory for the query  
  - `files` (required list): List of file paths to attach
  - `model` (optional): Model name (flash, pro, or custom)
- **Use Case**: File-specific analysis, multi-file comparisons, code reviews
- **File Handling**: Reads files, concatenates with headers, passes to Gemini
- **Example**: Code reviews, debugging specific files, analyzing project structure

### `get_debug_info`
- **Purpose**: Diagnostic tool for troubleshooting timeout and configuration issues
- **Parameters**: None required
- **Use Case**: Debugging timeout problems, verifying setup, system diagnostics
- **Output**: Comprehensive debug information including:
  - Current timeout configuration and recommendations
  - Gemini CLI status, version, and authentication
  - Environment variables and system information
  - Configuration validation and warnings
- **Example**: Run when experiencing timeout issues or setup problems

## Error Handling & Troubleshooting

### Diagnostic Tools

**Primary Diagnostic Tool**: Use `get_debug_info()` MCP tool for comprehensive system diagnostics. This tool provides:
- Timeout configuration analysis with recommendations
- Gemini CLI version and authentication status  
- Environment variable validation
- System status and warnings

### Common Error Patterns
- **"CLI not available"**: Gemini CLI not installed or not in PATH
  - Solution: `npm install -g @google/gemini-cli`
- **"Authentication required"**: Not logged into Gemini
  - Solution: `gemini auth login`
- **"Timeout after X seconds"**: Query took longer than configured timeout
  - **Immediate Solution**: Increase GEMINI_BRIDGE_TIMEOUT environment variable
  - **Recommended Values**: 
    - Default operations: 60s
    - Large file analysis: 240s
    - Complex multi-file operations: 300s+
  - **Alternative**: Break queries into smaller parts or reduce file size
- **"Large content size warning"**: Files total >100KB, may cause timeouts
  - Solution: Increase timeout or reduce file count/size
- **"Directory does not exist"**: Invalid directory parameter
  - Solution: Use absolute paths or verify directory exists
- **"No files provided"**: Missing files parameter for file-attachment mode
  - Solution: Provide at least one valid file path

### Advanced Timeout Troubleshooting

**Timeout Configuration Priority**:
1. Check environment variable: `GEMINI_BRIDGE_TIMEOUT`
2. Validate value is positive integer
3. Default to 60 seconds if invalid/missing
4. Log configuration at startup for visibility

**Debugging Timeout Issues**:
1. **Run Diagnostics**: Use `get_debug_info()` tool first
2. **Check Logs**: Server now logs detailed timing and content size information
3. **Verify Configuration**: Ensure GEMINI_BRIDGE_TIMEOUT is properly set
4. **Test Incremental**: Start with small queries, gradually increase complexity
5. **Monitor Content Size**: Large files (>100KB total) need higher timeouts
6. **Verify CLI Performance**: Test `gemini` command directly with similar content

**Timeout Recommendations by Use Case**:
```bash
# Basic code queries (default)
GEMINI_BRIDGE_TIMEOUT=60

# Large file analysis (recommended for your 240s use case)
GEMINI_BRIDGE_TIMEOUT=240  

# Complex multi-file analysis
GEMINI_BRIDGE_TIMEOUT=300

# Very large codebases or detailed analysis
GEMINI_BRIDGE_TIMEOUT=600
```

### Debugging Steps
1. **Run Diagnostic Tool**: `get_debug_info()` - Check all configuration
2. **Verify Gemini CLI**: `gemini --version`
3. **Test Authentication**: `gemini "Hello"`
4. **Check Environment**: Verify GEMINI_BRIDGE_TIMEOUT is set correctly
5. **Monitor Logs**: Check server logs for timing information
6. **Test Progressive**: Start small, increase complexity gradually

## Development Guidelines

### Code Standards
- **Python 3.9+ Compatibility**: Use modern Python features responsibly
- **Type Hints**: Include type annotations for all functions
- **Error Handling**: Explicit error messages with actionable solutions
- **Documentation**: Keep CLAUDE.md, README.md, and code comments in sync

### Testing Requirements
- **Manual Testing**: Verify both MCP tools work with various queries
- **Integration Testing**: Test with Claude Code in development
- **Cross-Platform**: Ensure compatibility across Python versions (3.9-3.12)
- **CI/CD Verification**: All GitHub Actions must pass

### Performance Characteristics
- **Startup Time**: Near-instant MCP server startup
- **Memory Usage**: Minimal memory footprint (~10MB)
- **Execution Time**: Limited by configurable timeout (default: 60 seconds)
- **Scalability**: Stateless design allows multiple concurrent requests

## Package Information

### Dependencies
- **Required**: `mcp>=1.0.0`
- **External**: Gemini CLI (npm package `@google/gemini-cli`)
- **Python**: Compatible with Python 3.9+

### Installation Details
- **Package Name**: `gemini-bridge`
- **PyPI**: Available as `pip install gemini-bridge`
- **Entry Point**: `gemini-bridge = "src:main"`
- **Module Execution**: `python -m src`

### Configuration
- **Default Model**: gemini-2.5-flash for optimal performance
- **Timeout**: Configurable via GEMINI_BRIDGE_TIMEOUT environment variable (default: 60 seconds)
- **Working Directory**: Configurable per request
- **File Encoding**: UTF-8 with error handling

#### Timeout Configuration
Set the `GEMINI_BRIDGE_TIMEOUT` environment variable to customize execution timeout:

```bash
# Example: 2-minute timeout for large file analysis
claude mcp add gemini-bridge -s user --env GEMINI_BRIDGE_TIMEOUT=120 -- uvx gemini-bridge
```

**Valid Values:**
- Positive integers (seconds)
- Default: 60 seconds if not set or invalid
- Recommended: 120-300 seconds for large files or complex queries

## Security Considerations

### Secure Practices
- **Input Validation**: Basic validation for file paths and queries
- **Process Isolation**: Subprocess execution for CLI calls
- **No Network Exposure**: All network requests handled by Gemini CLI
- **Minimal Attack Surface**: Simple, stateless architecture

### Best Practices
- Keep Gemini CLI updated: `npm update -g @google/gemini-cli`
- Use absolute paths for file operations
- Validate directory permissions before operations
- Monitor for unusual CLI behavior or errors

## Release & Deployment

### Version Management
- **Semantic Versioning**: MAJOR.MINOR.PATCH format
- **Current Version**: 1.0.2 (check `src/__init__.py`)
- **Release Tags**: Git tags trigger automated PyPI publishing

### Deployment Options
1. **PyPI + uvx** (Recommended): `uvx gemini-bridge`
2. **PyPI + pip**: `pip install gemini-bridge`
3. **Development**: `python -m src` from source

### CI/CD Pipeline
- **GitHub Actions**: Automated testing on Python 3.9-3.12
- **PyPI Publishing**: Triggered by version tags (v*.*)
- **Quality Gates**: Build verification, import testing, package validation

## Support & Community

### Getting Help
- **Issues**: [GitHub Issues](https://github.com/shelakh/gemini-bridge/issues)
- **Documentation**: README.md, CONTRIBUTING.md, SECURITY.md
- **MCP Protocol**: [Model Context Protocol](https://modelcontextprotocol.io/)

### Contributing
- **Guidelines**: See CONTRIBUTING.md for detailed development setup
- **Code Style**: Follow PEP 8, use type hints, include docstrings
- **Testing**: Manual testing required, automated CI verification
- **Community**: Respectful, constructive feedback welcome

---

This CLAUDE.md file serves as the authoritative development guide for the Gemini Bridge project. Keep it updated as the project evolves, ensuring consistency with README.md, CONTRIBUTING.md, and actual implementation.