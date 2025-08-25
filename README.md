# Gemini Bridge

![CI Status](https://github.com/eLyiN/gemini-bridge/actions/workflows/ci.yml/badge.svg)
![PyPI Version](https://img.shields.io/pypi/v/gemini-bridge)
![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![MCP Compatible](https://img.shields.io/badge/MCP-compatible-green.svg)
![Gemini CLI](https://img.shields.io/badge/Gemini-CLI-blue.svg)

[![Open in GitHub Codespaces](https://img.shields.io/badge/Open%20in-GitHub%20Codespaces-blue?logo=github&logoColor=white)](https://github.com/shelakh/gemini-bridge/blob/main/README.md)

A lightweight MCP (Model Context Protocol) server that enables Claude Code to interact with Google's Gemini AI through the official CLI. Designed for simplicity, reliability, and seamless integration.

## ✨ Features

- **Direct Gemini CLI Integration**: Zero API costs using official Gemini CLI
- **Simple MCP Tools**: Two core functions for basic queries and file analysis
- **Stateless Operation**: No sessions, caching, or complex state management
- **Production Ready**: Robust error handling with configurable 60-second timeouts
- **Minimal Dependencies**: Only requires `mcp>=1.0.0` and Gemini CLI
- **Easy Deployment**: Support for both uvx and traditional pip installation

## 🚀 Quick Start

### Prerequisites

1. **Install Gemini CLI**:
   ```bash
   npm install -g @google/gemini-cli
   ```

2. **Authenticate with Gemini**:
   ```bash
   gemini auth login
   ```

3. **Verify installation**:
   ```bash
   gemini --version
   ```

### Installation

**🎯 Recommended: PyPI Installation**
```bash
# Install from PyPI
pip install gemini-bridge

# Add to Claude Code with uvx (recommended)
claude mcp add gemini-bridge -s user -- uvx gemini-bridge
```

**Alternative: From Source**
```bash
# Clone the repository
git clone https://github.com/shelakh/gemini-bridge.git
cd gemini-bridge

# Build and install locally
uvx --from build pyproject-build
pip install dist/*.whl

# Add to Claude Code
claude mcp add gemini-bridge -s user -- uvx gemini-bridge
```

**Development Installation**
```bash
# Clone and install in development mode
git clone https://github.com/shelakh/gemini-bridge.git
cd gemini-bridge
pip install -e .

# Add to Claude Code (development)
claude mcp add gemini-bridge-dev -s user -- python -m src
```

## 🛠️ Available Tools

### `consult_gemini`
Direct CLI bridge for simple queries.

**Parameters:**
- `query` (string): The question or prompt to send to Gemini
- `directory` (string): Working directory for the query (default: current directory)
- `model` (string, optional): Model to use - "flash" or "pro" (default: "flash")

**Example:**
```python
consult_gemini(
    query="Find authentication patterns in this codebase",
    directory="/path/to/project",
    model="flash"
)
```

### `consult_gemini_with_files`
CLI bridge with file attachments for detailed analysis.

**Parameters:**
- `query` (string): The question or prompt to send to Gemini
- `directory` (string): Working directory for the query
- `files` (list): List of file paths relative to the directory
- `model` (string, optional): Model to use - "flash" or "pro" (default: "flash")

**Example:**
```python
consult_gemini_with_files(
    query="Analyze these auth files and suggest improvements",
    directory="/path/to/project",
    files=["src/auth.py", "src/models.py"],
    model="pro"
)
```

## 📋 Usage Examples

### Basic Code Analysis
```python
# Simple research query
consult_gemini(
    query="What authentication patterns are used in this project?",
    directory="/Users/dev/my-project"
)
```

### Detailed File Review
```python
# Analyze specific files
consult_gemini_with_files(
    query="Review these files and suggest security improvements",
    directory="/Users/dev/my-project",
    files=["src/auth.py", "src/middleware.py"],
    model="pro"
)
```

### Multi-file Analysis
```python
# Compare multiple implementation files
consult_gemini_with_files(
    query="Compare these database implementations and recommend the best approach",
    directory="/Users/dev/my-project",
    files=["src/db/postgres.py", "src/db/sqlite.py", "src/db/redis.py"]
)
```

## 🏗️ Architecture

### Core Design
- **CLI-First**: Direct subprocess calls to `gemini` command
- **Stateless**: Each tool call is independent with no session state
- **Fixed Timeout**: 60-second maximum execution time
- **Simple Error Handling**: Clear error messages with fail-fast approach

### Project Structure
```
gemini-bridge/
├── src/
│   ├── __init__.py              # Entry point
│   ├── __main__.py              # Module execution entry point
│   └── mcp_server.py            # Main MCP server implementation
├── .github/                     # GitHub templates and workflows
├── pyproject.toml              # Python package configuration
├── README.md                   # This file
├── CONTRIBUTING.md             # Contribution guidelines
├── CODE_OF_CONDUCT.md          # Community standards
├── SECURITY.md                 # Security policies
├── CHANGELOG.md               # Version history
└── LICENSE                    # MIT license
```

## 🔧 Development

### Local Testing
```bash
# Install in development mode
pip install -e .

# Run directly
python -m src

# Test CLI availability
gemini --version
```

### Integration with Claude Code
The server automatically integrates with Claude Code when properly configured through the MCP protocol.

## 🔍 Troubleshooting

### CLI Not Available
```bash
# Install Gemini CLI
npm install -g @google/gemini-cli

# Authenticate
gemini auth login

# Test
gemini --version
```

### Connection Issues
- Verify Gemini CLI is properly authenticated
- Check network connectivity
- Ensure Claude Code MCP configuration is correct
- Check that the `gemini` command is in your PATH

### Common Error Messages
- **"CLI not available"**: Gemini CLI is not installed or not in PATH
- **"Authentication required"**: Run `gemini auth login`
- **"Timeout after 60 seconds"**: Query took too long, try breaking it into smaller parts

## 🤝 Contributing

We welcome contributions from the community! Please read our [Contributing Guidelines](CONTRIBUTING.md) for details on how to get started.

### Quick Contributing Guide
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔄 Version History

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

## 🆘 Support

- **Issues**: Report bugs or request features via [GitHub Issues](https://github.com/shelakh/gemini-bridge/issues)
- **Discussions**: Join the community discussion
- **Documentation**: Additional docs can be created in the `docs/` directory

---

**Focus**: A simple, reliable bridge between Claude Code and Gemini AI through the official CLI.