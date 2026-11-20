#!/usr/bin/env python3
"""
Unified `promptsave` CLI entry point.

Usage:
    promptsave install [--set-center]
    promptsave uninstall
    promptsave status
    promptsave init [path]
    promptsave list
    promptsave view <project>
    promptsave search <query> [--tool ...] [--project ...]
    promptsave stats
    promptsave export <project> --format json|md|html [--output file]
    promptsave unlock
    promptsave lock
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import install as installer  # noqa: E402
import vault  # noqa: E402

try:
    from promptsave import __version__
except ImportError:
    __version__ = "1.1.0"

USAGE = f"""PromptSave v{__version__} — Encrypted prompt history vault for AI CLIs

Commands:
  install [--center DIR]     Register global hooks and generate local .env key
  uninstall                  Remove all global hooks (keeps saved prompts)
  status                     Show hook status, encryption mode, and tracked count
  init [path]                Start tracking the current directory (or [path])
  list                       List all saved project logs
  view <project>             Decrypt and print a project's prompt history
  search <query> [options]   Search across all encrypted prompt logs
  stats                      Show usage statistics by AI tool and project
  export <project> [options] Export prompts to json, md, or html
  unlock                     Temporarily decrypt .md.enc -> .md for browsing
  lock                       Encrypt .md -> .md.enc and remove plaintext copies
"""


def cmd_init(args):
    target = os.path.abspath(args[0] if args else os.getcwd())
    if not os.path.isdir(target):
        print(f"Error: Directory not found: {target}", file=sys.stderr)
        sys.exit(1)
    marker_path = os.path.join(target, ".promptsave")
    if os.path.isfile(marker_path):
        print(f"Already tracked: {target}")
        return
    with open(marker_path, "w", encoding="utf-8"):
        pass
    print(f"Now tracking prompts in: {target}")
    print("Created marker file:", marker_path)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return
    if args[0] in ("-V", "--version"):
        print(f"promptsave {__version__}")
        return

    cmd, rest = args[0], args[1:]
    if cmd == "install":
        installer.main(rest)
    elif cmd == "uninstall":
        installer.main(["--uninstall", *rest])
    elif cmd == "status":
        installer.main(["--status"])
    elif cmd == "init":
        cmd_init(rest)
    elif cmd in ("list", "view", "search", "stats", "export", "unlock", "lock"):
        vault.main([cmd, *rest])
    else:
        print(f"Unknown command: {cmd}\n", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
