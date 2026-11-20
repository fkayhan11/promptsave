# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-11-20

### Added
- Automatic prompt logging for **Claude Code**, **OpenAI Codex CLI**, and **Antigravity CLI**.
- Local `.env` authenticated encryption (`PBKDF2-HMAC-SHA256` + `SHA-256-CTR` + `HMAC-SHA256`) enabled by default with per-user 256-bit keys.
- `promptsave/vault.py` CLI (`list`, `view`, `unlock`, `lock`) for reading and managing encrypted prompt logs.
- Centralized project-based logs under `projects/` and auto-generated overview at `summary/README.md`.
- Smart marker detection supporting `promptsave/`, copied/renamed folders, and subdirectories.
- Cross-platform file locking (`fcntl` on Unix/macOS, `msvcrt` on Windows).
- Unified installer (`promptsave/install.py`) with `--status`, `--set-center`, and `--uninstall` options.
- Unit test suite and GitHub Actions CI across Ubuntu, macOS, and Windows.
