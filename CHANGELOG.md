# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-11-20

### Added
- **Gemini CLI** (`~/.gemini/settings.json` / `BeforeAgent`) and **Cursor** (`~/.cursor/hooks.json` / `beforeSubmitPrompt` with UTF-8 BOM handling) support.
- Unified `promptsave` CLI (`promptsave/cli.py`) and `pyproject.toml` packaging for `pip install -e .` / `pipx` installation.
- `promptsave init [path]` command to start tracking any project without copying folders.
- `promptsave search <query> [--tool ...] [--project ...]` for in-memory search across encrypted logs.
- `promptsave stats` for per-tool and per-project usage statistics with visual bar charts.
- `promptsave export <project> --format json|md|html [--output file]` for structured JSON, Markdown, and standalone dark-mode HTML exports.
- Redesigned GitHub `README.md` with Mermaid architecture diagram and CLI examples.

## [1.0.0] - 2026-11-20

### Added
- Automatic prompt logging for **Claude Code**, **OpenAI Codex CLI**, and **Antigravity CLI**.
- Local `.env` authenticated encryption (`PBKDF2-HMAC-SHA256` + `SHA-256-CTR` + `HMAC-SHA256`) enabled by default with per-user 256-bit keys.
- `promptsave/vault.py` CLI (`list`, `view`, `unlock`, `lock`) for reading and managing encrypted prompt logs.
- Centralized project-based logs under `projects/` and auto-generated overview at `summary/README.md`.
- Cross-platform file locking (`fcntl` on Unix/macOS, `msvcrt` on Windows) and unit test suite.
