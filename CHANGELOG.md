# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.5] - 2025-08-26

### Added
- **Configurable Timeout**: Added `GEMINI_BRIDGE_TIMEOUT` environment variable support
  - Users can now configure timeout values for longer queries (large files, complex analysis)
  - Default remains 60 seconds for backward compatibility
  - Invalid values fall back to default with proper logging warnings
- **Improved Error Messages**: Timeout error messages now display actual timeout value used
- **Enhanced Documentation**: Added comprehensive timeout configuration examples in README.md and CLAUDE.md

### Changed
- **Warning System**: Replaced `print()` statements with proper `logging.warning()` for library code
- **Error Handling**: Timeout validation with clear feedback for invalid environment variable values

### Technical Details
- Added `_get_timeout()` function for environment variable handling
- Updated both `execute_gemini_simple()` and `execute_gemini_with_files()` to use configurable timeout
- Maintains extreme simplicity principles while solving user-reported timeout issues

## [1.0.0] - 2025-08-24

### Added

#### Core Features
- **MCP Server Implementation**: Complete Model Context Protocol server for bridging Claude Code to Gemini AI
- **Two MCP Tools**:
  - `consult_gemini`: Direct CLI bridge for simple queries with optional model selection
  - `consult_gemini_with_files`: CLI bridge with file attachment support for detailed analysis
- **CLI Integration**: Direct integration with Google's official Gemini CLI
- **Model Support**: Support for both "flash" (gemini-2.5-flash) and "pro" (gemini-2.5-pro) models

#### Architecture & Design
- **Stateless Operation**: No session management, caching, or complex state
- **Fixed Timeout**: 60-second maximum execution time for all operations
- **Simple Error Handling**: Clear error messages with fail-fast approach
- **Minimal Dependencies**: Only requires `mcp>=1.0.0` and external Gemini CLI

#### Deployment & Installation
- **uvx Support**: Production deployment via uvx with built wheel
- **Development Mode**: Traditional pip installation for development
- **Startup Scripts**: 
  - `start_server_uvx.sh` for production
  - `start_server_dev.sh` for development
- **Package Configuration**: Complete pyproject.toml with metadata and entry points

#### Documentation
- **Comprehensive README**: Installation, usage examples, troubleshooting
- **Contributing Guidelines**: Development setup, code style, PR process
- **Security Policy**: Vulnerability reporting, best practices, update process
- **License**: MIT License for open source use

#### Developer Experience
- **Claude Code Integration**: Seamless MCP protocol integration
- **Error Diagnostics**: Clear error messages for common issues
- **Development Tools**: Easy local testing and development setup

### Technical Details

#### Dependencies
- **Required**: `mcp>=1.0.0`
- **External**: Gemini CLI (npm package `@google/gemini-cli`)
- **Python**: Compatible with Python 3.9+

#### File Structure
```
gemini-bridge/
├── src/
│   ├── __init__.py              # Package entry point and version
│   ├── __main__.py              # Module execution entry point  
│   └── mcp_server.py            # Core MCP server implementation
├── start_server_uvx.sh         # Production startup script
├── start_server_dev.sh         # Development startup script
├── pyproject.toml              # Python package configuration
└── [documentation files]       # README, CONTRIBUTING, SECURITY, etc.
```

#### Configuration
- **Default Model**: gemini-2.5-flash for optimal performance
- **Timeout**: 60 seconds for all CLI operations
- **Working Directory**: Configurable per request
- **File Encoding**: UTF-8 with error handling

### Security Considerations
- **Input Validation**: Basic validation for file paths and queries
- **Process Isolation**: Subprocess execution for CLI calls
- **No Network Exposure**: All network requests handled by Gemini CLI
- **Minimal Attack Surface**: Simple, stateless architecture

### Performance Characteristics
- **Startup Time**: Near-instant MCP server startup
- **Memory Usage**: Minimal memory footprint
- **Execution Time**: Limited by 60-second timeout
- **Scalability**: Stateless design allows multiple concurrent requests

## [Unreleased]

### Planned
- Additional error recovery mechanisms
- Enhanced file type detection
- Configuration file support
- Extended model options
- Performance optimizations

### Under Consideration
- Async operation support
- Batch query processing
- Custom timeout configuration
- Response caching options
- Integration testing framework

---

## Release Notes

### Version 1.0.0 Highlights

This initial release establishes Gemini Bridge as a production-ready MCP server with a focus on:

1. **Simplicity**: Straightforward architecture that's easy to understand and maintain
2. **Reliability**: Robust error handling and fixed timeout protection  
3. **Integration**: Seamless Claude Code integration via MCP protocol
4. **Performance**: Direct CLI integration for optimal speed and cost efficiency
5. **Community**: Complete open source documentation and contribution guidelines

### Migration Notes

This is the initial public release, so no migration is required. Future versions will include migration guidance here.

### Breaking Changes

None in this initial release. Future breaking changes will be clearly documented here.

### Deprecation Warnings

None in this initial release. Future deprecations will be announced here with migration timelines.

---

## Contributors

Special thanks to all contributors who made this release possible:

- **Core Development**: Project architecture and implementation
- **Documentation**: Comprehensive documentation and examples
- **Testing**: Manual testing across different environments
- **Community**: Feedback and suggestions for improvement

## Links

- **Repository**: [https://github.com/shelakh/gemini-bridge](https://github.com/shelakh/gemini-bridge)
- **Issues**: [https://github.com/shelakh/gemini-bridge/issues](https://github.com/shelakh/gemini-bridge/issues)
- **MCP Protocol**: [https://modelcontextprotocol.io/](https://modelcontextprotocol.io/)
- **Gemini CLI**: [https://www.npmjs.com/package/@google/gemini-cli](https://www.npmjs.com/package/@google/gemini-cli)
## [1.1.1] - 2025-09-05

### Fixed
- Improved MCP tool metadata so clients display parameter types accurately.

## [1.1.0] - 2025-09-05

### Added
- **Per-call timeout overrides**: Both MCP tools now accept `timeout_seconds`, letting clients extend execution time without changing global env vars.
- **Attachment guardrails**: Inline file uploads enforce configurable limits, surface truncation warnings, and provide environment knobs for tuning.
- **@-command delegation**: `consult_gemini_with_files` can forward `@path` prompts directly to Gemini CLI via `mode="at_command"` for large context loads.
- **Unit tests**: New pytest coverage across timeout handling, file preprocessing, and execution modes.

### Changed
- **Documentation**: Updated README, CLAUDE.md, and CONTRIBUTING guidelines with the new parameters, guardrails, and testing workflow.
- **CI**: Continuous integration now installs pytest and executes the suite on every build.
