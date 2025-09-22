# Repository Guidelines

## Project Structure & Module Organization
The package lives under `src/`, with `mcp_server.py` defining the FastMCP tools and `__main__.py` exposing the module entry point. Project metadata, dependency pins, and the `gemini-bridge` console script are declared in `pyproject.toml`. Reference docs and policies (`README.md`, `CONTRIBUTING.md`, `SECURITY.md`) sit in the repository root. Create new modules inside `src/` and keep supporting assets (sample configs, text fixtures) alongside their consumers.

## Build, Test, and Development Commands
- `pip install -e .` — install in editable mode for local development.
- `python -m src` — launch the MCP server directly; use `CTRL+C` to exit.
- `uvx gemini-bridge` — run the packaged CLI exactly as downstream clients will.
- `uvx --from build pyproject-build` — build distribution artifacts before publishing or testing installation.
Run commands from the project root to ensure relative paths resolve correctly.

## Coding Style & Naming Conventions
Follow PEP 8 with 4-space indentation and an 88-character target line length. Use descriptive, lowercase `snake_case` for functions and variables, `UPPER_SNAKE_CASE` for constants, and reserve `CamelCase` for classes. Keep functions small, add docstrings describing intent, and include type hints on public interfaces. Prefer expressive log messages over inline comments; only annotate logic that is non-obvious.

## Testing Guidelines
No automated suite ships today, so validate changes by exercising both tools: `python -m src` for the stdio server and `uvx gemini-bridge -- --help` or a sample prompt to confirm CLI wiring. When introducing automated tests, place them under `tests/`, target `pytest`, and mirror module names (e.g., `tests/test_mcp_server.py`). Cover environment-sensitive paths such as `_normalize_model_name` and `_get_timeout`, and document manual test steps in your PR.

## Commit & Pull Request Guidelines
Commit messages follow Conventional Commit prefixes (`feat:`, `fix:`, `chore:`, `docs:`) and should explain the motivation. Keep commits atomic and focused on one concern. Pull requests must include a concise summary, linked issues, and a brief testing log (commands run, expected vs. actual behavior). Request a review once CI (when available) passes and respond to feedback with follow-up commits rather than force-pushes.

## Security & Configuration Tips
Authenticate the Gemini CLI (`gemini auth login`) before running tools and avoid hard-coding credentials. Use the `GEMINI_BRIDGE_TIMEOUT` environment variable for tuning, but never commit `.env` files or shell history containing secrets. Validate file paths carefully when adding features that read from disk to preserve the server’s minimal, secure surface area.
