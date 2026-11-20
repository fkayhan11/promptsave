#!/usr/bin/env python3
"""
PromptSave installer (run ONCE per machine).

Registers the PromptSave lifecycle hook globally for:
  - Claude Code      (~/.claude/settings.json)
  - OpenAI Codex CLI (~/.codex/hooks.json)
  - Antigravity CLI  (~/.gemini/config/hooks.json)
  - Gemini CLI       (~/.gemini/settings.json)
  - Cursor           (~/.cursor/hooks.json)

Also generates a local `.env` file with a unique 256-bit `PROMPTSAVE_KEY` so
your saved prompt logs are encrypted at rest and private to your machine.

Usage:
    python3 promptsave/install.py               Install or update hooks
    python3 promptsave/install.py --status      Check installation status
    python3 promptsave/install.py --set-center  Point central log folder to this repo
    python3 promptsave/install.py --uninstall   Remove all hooks (keeps saved prompts)
"""
import argparse
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import crypto  # noqa: E402

HOME = os.path.expanduser("~")
INSTALL_DIR = os.path.expanduser(os.environ.get("PROMPTSAVE_HOME", "~/.promptsave"))
BACKUP_DIR = os.path.join(INSTALL_DIR, "backups")
HOOK_DST = os.path.join(INSTALL_DIR, "hook.py")
CRYPTO_DST = os.path.join(INSTALL_DIR, "crypto.py")
PY = sys.executable or "python3"

CLAUDE_SETTINGS = os.path.join(HOME, ".claude", "settings.json")
CODEX_HOOKS = os.path.join(HOME, ".codex", "hooks.json")
AGY_HOOKS = os.path.join(HOME, ".gemini", "config", "hooks.json")
GEMINI_SETTINGS = os.path.join(HOME, ".gemini", "settings.json")
CURSOR_HOOKS = os.path.join(HOME, ".cursor", "hooks.json")

TAG = "promptsave"


def hook_command(tool):
    return f'"{PY}" "{HOOK_DST}" {tool}'


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            txt = f.read().strip()
            return json.loads(txt) if txt else {}
    except FileNotFoundError:
        return {}


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rendered = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            if f.read() == rendered:
                return False
        os.makedirs(BACKUP_DIR, exist_ok=True)
        stamp = int(time.time())
        bname = f"{os.path.basename(os.path.dirname(path))}-{os.path.basename(path)}.{stamp}.bak"
        shutil.copy2(path, os.path.join(BACKUP_DIR, bname))
    with open(path, "w", encoding="utf-8") as f:
        f.write(rendered)
    return True


def strip_ours(groups):
    out = []
    for group in groups or []:
        hooks = [h for h in group.get("hooks", []) if TAG not in h.get("command", "")]
        if hooks:
            out.append(dict(group, hooks=hooks))
    return out


def update_claude_style(data, tool, remove, event="UserPromptSubmit"):
    hooks = data.setdefault("hooks", {})
    groups = strip_ours(hooks.get(event))
    if not remove:
        entry = {"type": "command", "command": hook_command(tool), "timeout": 10}
        if tool == "gemini":
            entry["name"] = TAG
            groups.append({"matcher": "", "hooks": [entry]})
        else:
            groups.append({"hooks": [entry]})
    if groups:
        hooks[event] = groups
    else:
        hooks.pop(event, None)
    if not hooks:
        data.pop("hooks", None)
    return data


def update_antigravity(data, remove):
    data.pop(TAG, None)
    if not remove:
        data[TAG] = {
            "PreInvocation": [
                {"type": "command", "command": hook_command("antigravity"), "timeout": 10}
            ]
        }
    return data


def update_cursor(data, remove):
    if not remove:
        data.setdefault("version", 1)
    hooks = data.setdefault("hooks", {})
    entries = [
        e for e in hooks.get("beforeSubmitPrompt", [])
        if TAG not in e.get("command", "")
    ]
    if not remove:
        entries.append({"command": hook_command("cursor")})
    if entries:
        hooks["beforeSubmitPrompt"] = entries
    else:
        hooks.pop("beforeSubmitPrompt", None)
    if not hooks:
        data.pop("hooks", None)
    return data


def has_hook(path, style):
    data = load_json(path)
    if style == "agy":
        return TAG in data
    if style == "cursor":
        entries = data.get("hooks", {}).get("beforeSubmitPrompt", [])
        return any(TAG in e.get("command", "") for e in entries)
    event = "BeforeAgent" if style == "gemini" else "UserPromptSubmit"
    groups = data.get("hooks", {}).get(event, [])
    return any(
        TAG in h.get("command", "")
        for g in groups
        for h in g.get("hooks", [])
    )


def ensure_env_file(repo_root):
    """Create a local .env with a unique 256-bit key if one does not exist."""
    env_path = os.path.join(repo_root, ".env")
    if os.path.isfile(env_path):
        return env_path, False
    key = crypto.generate_key()
    content = (
        "# PromptSave local encryption configuration\n"
        "# NEVER commit or share this file! It is gitignored by default.\n"
        f"PROMPTSAVE_KEY={key}\n"
        "PROMPTSAVE_ENCRYPT=true\n"
    )
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(content)
    try:
        os.chmod(env_path, 0o600)
    except OSError:
        pass
    return env_path, True


def print_status():
    cfg = load_json(os.path.join(INSTALL_DIR, "config.json"))
    center = cfg.get("center") or cfg.get("merkez") or ""
    reg = load_json(os.path.join(INSTALL_DIR, ".projects.json"))
    env_path = os.path.join(os.path.dirname(center), ".env") if center else ""
    env_vals = crypto.load_env(env_path) if env_path else {}
    enc_active = bool(env_vals.get("PROMPTSAVE_KEY")) and env_vals.get(
        "PROMPTSAVE_ENCRYPT", "true"
    ).lower() in ("1", "true", "yes", "on")

    print("PromptSave Status")
    print("-" * 44)
    print(f"Hook script : {'OK' if os.path.isfile(HOOK_DST) else 'MISSING'} ({HOOK_DST})")
    print(f"Claude Code : {'ACTIVE' if has_hook(CLAUDE_SETTINGS, 'claude') else 'NOT INSTALLED'}")
    print(f"Codex CLI   : {'ACTIVE' if has_hook(CODEX_HOOKS, 'codex') else 'NOT INSTALLED'}")
    print(f"Antigravity : {'ACTIVE' if has_hook(AGY_HOOKS, 'agy') else 'NOT INSTALLED'}")
    print(f"Gemini CLI  : {'ACTIVE' if has_hook(GEMINI_SETTINGS, 'gemini') else 'NOT INSTALLED'}")
    print(f"Cursor      : {'ACTIVE' if has_hook(CURSOR_HOOKS, 'cursor') else 'NOT INSTALLED'}")
    print(f"Center dir  : {center or '(not configured)'}")
    print(f"Encryption  : {'ENABLED (.env)' if enc_active else 'DISABLED'}")
    print(f"Tracked     : {len(reg)} project(s)")


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Install, inspect, or uninstall PromptSave global CLI hooks."
    )
    parser.add_argument(
        "--uninstall", action="store_true",
        help="Remove PromptSave hooks from all AI CLIs (keeps your saved prompts).",
    )
    parser.add_argument(
        "--set-center", action="store_true",
        help="Set this repository's projects/ folder as the central prompt store.",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show current installation status, encryption mode, and tracked projects.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.status:
        print_status()
        return

    remove = args.uninstall
    if not remove:
        os.makedirs(INSTALL_DIR, exist_ok=True)
        shutil.copy2(os.path.join(HERE, "hook.py"), HOOK_DST)
        shutil.copy2(os.path.join(HERE, "crypto.py"), CRYPTO_DST)
        try:
            os.chmod(HOOK_DST, 0o755)
        except OSError:
            pass

        cfg_path = os.path.join(INSTALL_DIR, "config.json")
        cfg = load_json(cfg_path)
        current_center = cfg.get("center") or cfg.get("merkez")
        if not current_center or args.set_center:
            new_center = os.path.join(os.path.dirname(HERE), "projects")
            cfg = {"center": new_center}
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
                f.write("\n")
            current_center = new_center

        repo_root = os.path.dirname(current_center)
        os.makedirs(current_center, exist_ok=True)
        os.makedirs(os.path.join(repo_root, "summary"), exist_ok=True)
        env_path, created = ensure_env_file(repo_root)
        print("Central projects directory:", current_center)
        if created:
            print("Generated local encryption key in:", env_path)
        else:
            print("Using existing encryption key in:", env_path)

    save_json(CLAUDE_SETTINGS, update_claude_style(load_json(CLAUDE_SETTINGS), "claude", remove))
    save_json(CODEX_HOOKS, update_claude_style(load_json(CODEX_HOOKS), "codex", remove))
    save_json(AGY_HOOKS, update_antigravity(load_json(AGY_HOOKS), remove))
    save_json(
        GEMINI_SETTINGS,
        update_claude_style(load_json(GEMINI_SETTINGS), "gemini", remove, event="BeforeAgent"),
    )
    save_json(CURSOR_HOOKS, update_cursor(load_json(CURSOR_HOOKS), remove))

    if remove:
        shutil.rmtree(INSTALL_DIR, ignore_errors=True)
        print("PromptSave uninstalled. Your saved prompt files and .env were NOT deleted.")
    else:
        print("PromptSave installed successfully!")
        print("  Claude Code  ->", CLAUDE_SETTINGS)
        print("  Codex CLI    ->", CODEX_HOOKS)
        print("  Antigravity  ->", AGY_HOOKS)
        print("  Gemini CLI   ->", GEMINI_SETTINGS)
        print("  Cursor       ->", CURSOR_HOOKS)
        print("\nNext step: run `promptsave init` in any project (or copy the `promptsave/` folder).")
        print("Read encrypted logs with: promptsave view <project>")
        print("Note for Codex CLI: approve the hook once when prompted (or run `/hooks`).")


if __name__ == "__main__":
    main()
