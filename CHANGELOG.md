# Changelog

All notable changes to this project will be documented in this file.

## [1.2.0] - 2026-11-24

### Added
- **AI Context Handoff (`promptsave handoff <project>`)** — Generates a chronological context brief from your recent prompts and copies it to your clipboard so you can switch AI CLIs in seconds.
- **Automatic Secret Redaction (`promptsave/redact.py`)** — Detects and masks accidentally pasted API keys (OpenAI, Anthropic, GitHub, AWS, Google, Slack), JWTs, Bearer tokens, and private keys before saving (`PROMPTSAVE_REDACT=true`).
- **Git Branch & Commit Context** — Automatically records `branch @ short_sha` in each prompt header using pure Python (<1ms, no subprocess).
- **Zero-Dependency Local Web UI (`promptsave ui`)** — Launches a dark-mode localhost dashboard (`127.0.0.1:8787`) with instant search, AI tool filters, one-click copy, pinning, and handoff generation.
- **Prompt Pinning & Reuse** — `promptsave pin`, `promptsave pins`, `promptsave copy`, and `promptsave unpin` for saving and reusing favorite prompts across projects.

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
