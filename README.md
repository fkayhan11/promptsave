# PromptSave

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-3776AB.svg)](https://www.python.org/)
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-Zero-brightgreen.svg)](#)
[![Platforms](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)](#)

**PromptSave** automatically captures every prompt you send to terminal AI coding assistants — **Claude Code**, **OpenAI Codex CLI**, and **Antigravity CLI** — and stores them as numbered Markdown logs (`1, 2, 3, ...`) inside **one central encrypted vault**, organized by project.

No manual copy-pasting. No lost prompt history when you close your terminal or switch between AI tools. And with built-in **`.env` encryption**, your prompts stay strictly private to your machine.

---

## Features

- **Multi-CLI Support:** Captures prompts from **Claude Code**, **OpenAI Codex CLI**, and **Antigravity CLI** in one unified history.
- **Drop-In Project Tracking:** Copy the `promptsave/` folder into any project to start tracking it — no extra commands or flags needed per project.
- **Encrypted by Default (`.env`):** Every user gets a unique, locally generated 256-bit `PROMPTSAVE_KEY` in `.env`. Prompt files are encrypted at rest (`projects/<project>.md.enc`) using PBKDF2-HMAC-SHA256 + SHA-256-CTR + HMAC-SHA256 (Encrypt-then-MAC).
- **Strict User Isolation:** `.env`, encrypted logs, and plaintext logs are all gitignored by default. Users who clone this repository can **never** see each other's prompts.
- **Zero Dependencies:** Pure Python 3.8+ standard library. Works on macOS, Linux, and Windows.
- **Non-Blocking:** Runs silently via native CLI lifecycle hooks and never interrupts your AI session.

---

## Folder Structure

```text
promptsave/
├── .env.example           # Template for local encryption settings
├── .env                   # Auto-generated local secret key (gitignored, chmod 600)
├── projects/              # Per-project encrypted prompt logs (gitignored)
│   ├── my-web-app.md.enc  # Prompts 1, 2, 3, ... (encrypted with your .env key)
│   └── api-service.md.enc
├── summary/               # Auto-generated overview table (README.md, gitignored)
├── promptsave/            # Drop-in folder you copy into projects you want to track
│   ├── .promptsave        # Marker file (do not delete)
│   ├── crypto.py          # Zero-dependency authenticated encryption module
│   ├── hook.py            # CLI hook script that captures and logs prompts
│   ├── install.py         # One-time global hook & .env installer
│   └── vault.py           # CLI to list, view, unlock, and lock encrypted logs
├── examples/              # Sanitized sample Markdown output
└── tests/                 # Unit tests
```

All internal runtime state files (`.lock`, `.state.json`, `.projects.json`) are stored out of sight in `~/.promptsave/`.

---

## Quick Start

### 1. Clone and install once per machine

```bash
git clone https://github.com/fkayhan11/promptsave.git
cd promptsave
python3 promptsave/install.py
```

This does two things:
1. Generates a unique, private 256-bit encryption key in `.env` (never committed to Git).
2. Registers the global lifecycle hook for all three AI CLIs:

| AI CLI | Hook Event | Config File |
| --- | --- | --- |
| **Claude Code** | `UserPromptSubmit` | `~/.claude/settings.json` |
| **OpenAI Codex CLI** | `UserPromptSubmit` | `~/.codex/hooks.json` |
| **Antigravity CLI** | `PreInvocation` | `~/.gemini/config/hooks.json` |

> **One-time Codex approval:** For security, Codex CLI prompts you once to trust newly added hooks. The next time you open `codex`, choose **`2. Trust all and continue`** (or run `/hooks`). After that, it works across all projects automatically.

### 2. Track any project

Copy the `promptsave/` folder into any project you want to track:

```bash
cp -R promptsave /path/to/my-web-app/
```

Open `claude`, `codex`, or `agy` anywhere inside `/path/to/my-web-app/` and write prompts normally. Every prompt is automatically encrypted and appended to `projects/my-web-app.md.enc`.

Untracked projects (folders without `promptsave/`) are completely ignored.

### 3. Read your saved prompts

Use `vault.py` to read your encrypted prompts with your local `.env` key:

```bash
# List all tracked projects
python3 promptsave/vault.py list

# Decrypt and print a project's prompts directly in the terminal (no plaintext written to disk)
python3 promptsave/vault.py view my-web-app

# Temporarily decrypt all logs to readable .md files for browsing in your editor
python3 promptsave/vault.py unlock

# Re-encrypt and remove plaintext .md copies when done
python3 promptsave/vault.py lock
```

---

## Example Output

See [`examples/example-project.md`](examples/example-project.md) and [`examples/README.md`](examples/README.md):

```markdown
# my-web-app — Prompt History

> Project path: `/path/to/my-web-app`

## 1. Claude Code · 2026-11-20 10:15

    Scaffold a responsive login page with email/password validation.

## 2. Codex · 2026-11-20 10:28

    Add unit tests for the login form validation rules.
```

---

## Installer Commands

```bash
# Check installation status, encryption mode, and tracked projects
python3 promptsave/install.py --status

# Move the repository to a new location and update the central log path
python3 promptsave/install.py --set-center

# Uninstall all global hooks (your saved logs and .env are NOT deleted)
python3 promptsave/install.py --uninstall
```

---

## Privacy & Security

- **100% Local:** PromptSave makes zero network requests. Every user's prompts stay exclusively on their own computer.
- **Unique Key Per User:** `install.py` generates a fresh random 256-bit `PROMPTSAVE_KEY` in `.env` with `0600` permissions (owner read/write only).
- **Authenticated Encryption:** Encrypted files use PBKDF2-HMAC-SHA256 (200,000 iterations), unique random salt & nonce per write, SHA-256 CTR stream encryption, and HMAC-SHA256 integrity verification. Tampered files or wrong keys are rejected immediately.
- **Double Git Protection:** `.gitignore` blocks `.env`, `projects/*.md`, `projects/*.md.enc`, and `summary/README.md` by default. Even if an encrypted `.md.enc` file were ever copied elsewhere, it cannot be decrypted without the owner's private `.env` key.
- **Optional Plaintext Mode:** If you prefer unencrypted local Markdown files, set `PROMPTSAVE_ENCRYPT=false` in `.env`.
- **Safe Config Backups:** Existing CLI config files are backed up to `~/.promptsave/backups/` before any change.

---

## Running Tests

```bash
python3 -m unittest discover -s tests -v
```

---

## License

Licensed under the [MIT License](LICENSE).
