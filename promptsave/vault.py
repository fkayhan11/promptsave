#!/usr/bin/env python3
"""
PromptSave Vault CLI - View, search, analyze, handoff, pin, export, unlock,
and lock your .env-encrypted prompt logs.

Usage:
    python3 promptsave/vault.py list
    python3 promptsave/vault.py view <project>
    python3 promptsave/vault.py search <query> [--tool claude] [--project name]
    python3 promptsave/vault.py handoff <project> [--last 10] [--no-copy]
    python3 promptsave/vault.py pin <project> <number> --tag <name>
    python3 promptsave/vault.py pins
    python3 promptsave/vault.py copy <tag>
    python3 promptsave/vault.py unpin <tag>
    python3 promptsave/vault.py stats
    python3 promptsave/vault.py export <project> --format json|md|html [--output file]
    python3 promptsave/vault.py unlock
    python3 promptsave/vault.py lock
"""
import argparse
from collections import Counter
import datetime
import html
import json
import os
import re
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import crypto  # noqa: E402
import hook  # noqa: E402

ENTRY_PATTERN = re.compile(
    r"^## (\d+)\. (.+?) · (\d{4}-\d{2}-\d{2} \d{2}:\d{2})(?: · ([^\n]+))?\n\n"
    r"(`{3,})text\n(.*?)\n\5",
    re.M | re.S,
)


def resolve_context():
    try:
        center = hook.central_dir()
    except Exception:
        center = os.path.join(os.path.dirname(SCRIPT_DIR), "projects")
        os.makedirs(center, exist_ok=True)
    _, key = hook.get_encryption_settings(center)
    return center, key


def require_key(key):
    if not key:
        print(
            "Error: PROMPTSAVE_KEY not found in .env or environment.\n"
            "Run `promptsave install` to generate a local .env key.",
            file=sys.stderr,
        )
        sys.exit(1)


def copy_to_clipboard(text):
    """Best-effort cross-platform clipboard copy using native OS utilities."""
    commands = []
    if sys.platform == "darwin":
        commands.append(["pbcopy"])
    elif sys.platform.startswith("win"):
        commands.append(["clip"])
    else:
        commands.extend(
            [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]
        )
    for cmd in commands:
        if shutil.which(cmd[0]):
            try:
                proc = subprocess.run(
                    cmd, input=text, text=True, capture_output=True, check=False
                )
                if proc.returncode == 0:
                    return True
            except OSError:
                continue
    return False


def discover_projects(center):
    """Return sorted dict of {project_name: (path, is_encrypted)}."""
    found = {}
    if not os.path.isdir(center):
        return found
    for fname in sorted(os.listdir(center)):
        if fname.endswith(".md.enc"):
            found[fname[:-7]] = (os.path.join(center, fname), True)
        elif fname.endswith(".md") and fname[:-3] not in found:
            found[fname[:-3]] = (os.path.join(center, fname), False)
    return found


def read_project_text(path, is_encrypted, key):
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    if is_encrypted:
        require_key(key)
        return crypto.decrypt_text(raw, key)
    return raw


def parse_entries(markdown_text):
    """Parse numbered prompt entries from a PromptSave Markdown document."""
    entries = []
    for m in ENTRY_PATTERN.finditer(markdown_text):
        entries.append(
            {
                "number": int(m.group(1)),
                "tool": m.group(2).strip(),
                "timestamp": m.group(3).strip(),
                "git": (m.group(4) or "").strip(),
                "prompt": m.group(6),
            }
        )
    return entries


def normalize_project_name(name):
    for suffix in (".md.enc", ".md"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def load_project_entries(center, key, project_name):
    name = normalize_project_name(project_name)
    projects = discover_projects(center)
    if name not in projects:
        raise FileNotFoundError(f"Project '{project_name}' not found in {center}")
    path, is_enc = projects[name]
    text = read_project_text(path, is_enc, key)
    return name, text, parse_entries(text)


def pins_path():
    return os.path.join(hook.get_state_dir(), ".pins.json")


def load_pins():
    return hook.load_json(pins_path(), {})


def save_pins(pins):
    path = pins_path()
    hook.save_json(path, pins)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def build_handoff_text(project_name, entries, last_n=10):
    selected = entries[-last_n:] if last_n > 0 else entries
    lines = [
        f"# Context Handoff — {project_name}",
        "",
        f"I am continuing work on `{project_name}` and switching AI coding assistants.",
        f"Here are my last {len(selected)} prompt(s) in chronological order so you have full context:",
        "",
    ]
    for idx, entry in enumerate(selected, 1):
        git_part = f" · {entry['git']}" if entry.get("git") else ""
        lines.append(f"### {idx}. [{entry['tool']} · {entry['timestamp']}{git_part}]")
        lines.append(entry["prompt"])
        lines.append("")
    lines.append("Please acknowledge this context and wait for my next instruction.")
    return "\n".join(lines) + "\n"


def cmd_list(center):
    projects = discover_projects(center)
    if not projects:
        print("No saved project logs yet.")
        return
    print(f"Projects directory: {center}\n")
    for name, (path, is_enc) in projects.items():
        tag = "[encrypted]" if is_enc else "[plaintext]"
        print(f"  {tag}  {name}  ({os.path.basename(path)})")


def cmd_view(center, key, project_name):
    try:
        _, text, _ = load_project_entries(center, key, project_name)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(text)


def cmd_search(center, key, query, tool_filter=None, project_filter=None):
    projects = discover_projects(center)
    if not projects:
        print("No saved project logs yet.")
        return
    q_lower = query.lower()
    t_lower = tool_filter.lower() if tool_filter else None
    p_lower = project_filter.lower() if project_filter else None
    hits = 0

    for name, (path, is_enc) in projects.items():
        if p_lower and p_lower not in name.lower():
            continue
        try:
            text = read_project_text(path, is_enc, key)
        except ValueError as exc:
            print(f"Warning: could not decrypt '{name}': {exc}", file=sys.stderr)
            continue
        for entry in parse_entries(text):
            if t_lower and t_lower not in entry["tool"].lower():
                continue
            if q_lower in entry["prompt"].lower():
                hits += 1
                snippet = " ".join(entry["prompt"].splitlines())
                if len(snippet) > 120:
                    snippet = snippet[:117] + "..."
                git_part = f" · {entry['git']}" if entry.get("git") else ""
                print(f"[{name} #{entry['number']}] {entry['tool']} · {entry['timestamp']}{git_part}")
                print(f"  {snippet}\n")

    if hits == 0:
        print(f"No matches found for '{query}'.")
    else:
        print(f"Found {hits} matching prompt(s).")


def cmd_handoff(center, key, project_name, last_n=10, no_copy=False):
    try:
        name, _, entries = load_project_entries(center, key, project_name)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    if not entries:
        print(f"No prompts recorded yet for '{name}'.", file=sys.stderr)
        sys.exit(1)
    brief = build_handoff_text(name, entries, last_n=last_n)
    print(brief)
    if not no_copy:
        copied = copy_to_clipboard(brief)
        if copied:
            print(
                f"(Copied handoff for '{name}' — last {min(last_n, len(entries))} prompts — to clipboard!)",
                file=sys.stderr,
            )


def cmd_pin(center, key, project_name, number, tag):
    try:
        name, _, entries = load_project_entries(center, key, project_name)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    match = next((e for e in entries if e["number"] == number), None)
    if not match:
        print(f"Error: Prompt #{number} not found in '{name}'.", file=sys.stderr)
        sys.exit(1)
    pins = load_pins()
    pins[tag] = {
        "project": name,
        "number": number,
        "tool": match["tool"],
        "prompt": match["prompt"],
        "pinned_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    save_pins(pins)
    print(f"Pinned {name} #{number} as '{tag}'. Copy anytime with: promptsave copy {tag}")


def cmd_pins():
    pins = load_pins()
    if not pins:
        print("No pinned prompts yet. Pin one with: promptsave pin <project> <number> --tag <name>")
        return
    print("Pinned Prompts")
    print("=" * 48)
    for tag, info in sorted(pins.items()):
        snippet = " ".join(info["prompt"].splitlines())
        if len(snippet) > 80:
            snippet = snippet[:77] + "..."
        print(f"  [{tag}] ({info['project']} #{info['number']} · {info['tool']})")
        print(f"    {snippet}\n")


def cmd_copy(tag, no_copy=False):
    pins = load_pins()
    if tag not in pins:
        print(f"Error: Pin '{tag}' not found. Run `promptsave pins` to see saved pins.", file=sys.stderr)
        sys.exit(1)
    text = pins[tag]["prompt"]
    print(text)
    if not no_copy and copy_to_clipboard(text):
        print(f"(Copied pinned prompt '{tag}' to clipboard!)", file=sys.stderr)


def cmd_unpin(tag):
    pins = load_pins()
    if tag not in pins:
        print(f"Error: Pin '{tag}' not found.", file=sys.stderr)
        sys.exit(1)
    del pins[tag]
    save_pins(pins)
    print(f"Removed pin '{tag}'.")


def cmd_stats(center, key):
    projects = discover_projects(center)
    if not projects:
        print("No saved project logs yet.")
        return
    tool_counts = Counter()
    project_counts = Counter()
    total = 0

    for name, (path, is_enc) in projects.items():
        try:
            text = read_project_text(path, is_enc, key)
        except ValueError:
            continue
        entries = parse_entries(text)
        project_counts[name] = len(entries)
        total += len(entries)
        for entry in entries:
            tool_counts[entry["tool"]] += 1

    print("PromptSave Statistics")
    print("=" * 48)
    print(f"Total projects : {len(project_counts)}")
    print(f"Total prompts  : {total}\n")

    if tool_counts:
        print("By AI Tool:")
        max_c = max(tool_counts.values())
        for tool, count in tool_counts.most_common():
            bar_len = max(1, int(round((count / max_c) * 20)))
            bar = "#" * bar_len
            print(f"  {tool:<14} {count:>4}  {bar}")
        print()

    if project_counts:
        print("By Project:")
        for name, count in project_counts.most_common():
            print(f"  {name:<24} {count:>4} prompt(s)")


def render_html(project_name, entries):
    cards = []
    for e in entries:
        git_badge = (
            f"<span class='git'>{html.escape(e['git'])}</span>" if e.get("git") else ""
        )
        cards.append(
            f"<article class='card'>"
            f"<header><span class='num'>#{e['number']}</span> "
            f"<span class='tool'>{html.escape(e['tool'])}</span>"
            f"{git_badge}"
            f"<time>{html.escape(e['timestamp'])}</time></header>"
            f"<pre>{html.escape(e['prompt'])}</pre>"
            f"</article>"
        )
    body = "\n".join(cards) or "<p>No prompts recorded.</p>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(project_name)} — PromptSave Export</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          background: #0d1117; color: #e6edf3; max-width: 860px; margin: 2rem auto; padding: 0 1.25rem; }}
  h1 {{ font-size: 1.6rem; border-bottom: 1px solid #30363d; padding-bottom: 0.5rem; }}
  .meta {{ color: #8b949e; margin-bottom: 1.5rem; font-size: 0.9rem; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 1rem; }}
  .card header {{ display: flex; gap: 0.6rem; align-items: center; flex-wrap: wrap; margin-bottom: 0.6rem; font-size: 0.86rem; }}
  .num {{ font-weight: 700; color: #58a6ff; }}
  .tool {{ background: #21262d; padding: 0.15rem 0.55rem; border-radius: 999px; border: 1px solid #30363d; }}
  .git {{ background: #1f2937; color: #79c0ff; padding: 0.15rem 0.55rem; border-radius: 999px; font-family: monospace; font-size: 0.8rem; }}
  time {{ color: #8b949e; margin-left: auto; }}
  pre {{ white-space: pre-wrap; word-wrap: break-word; background: #0d1117; padding: 0.85rem;
         border-radius: 6px; margin: 0; font-size: 0.92rem; line-height: 1.5; }}
</style>
</head>
<body>
  <h1>{html.escape(project_name)} — Prompt History</h1>
  <div class="meta">Exported by PromptSave · {len(entries)} prompt(s)</div>
  {body}
</body>
</html>
"""


def cmd_export(center, key, project_name, fmt, output_path=None):
    try:
        name, markdown_text, entries = load_project_entries(center, key, project_name)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if fmt == "md":
        rendered = markdown_text
    elif fmt == "json":
        payload = {"project": name, "prompts": entries}
        rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    else:  # html
        rendered = render_html(name, entries)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(rendered)
        print(f"Exported '{name}' ({fmt}) -> {output_path}")
    else:
        print(rendered)


def cmd_unlock(center, key):
    require_key(key)
    count = 0
    for fname in sorted(os.listdir(center)):
        if not fname.endswith(".md.enc"):
            continue
        enc_path = os.path.join(center, fname)
        plain_path = os.path.join(center, fname[:-4])
        with open(enc_path, "r", encoding="utf-8") as f:
            plaintext = crypto.decrypt_text(f.read(), key)
        with open(plain_path, "w", encoding="utf-8") as f:
            f.write(plaintext)
        count += 1
    print(f"Unlocked {count} file(s) in {center}. Run `promptsave lock` when done reading.")


def cmd_lock(center, key):
    require_key(key)
    count = 0
    for fname in sorted(os.listdir(center)):
        if not fname.endswith(".md"):
            continue
        plain_path = os.path.join(center, fname)
        enc_path = plain_path + ".enc"
        with open(plain_path, "r", encoding="utf-8") as f:
            plaintext = f.read()
        encrypted = crypto.encrypt_text(plaintext, key)
        with open(enc_path, "w", encoding="utf-8") as f:
            f.write(encrypted)
        os.remove(plain_path)
        count += 1
    print(f"Locked {count} file(s) in {center}. Plaintext .md copies removed.")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="View, search, handoff, pin, analyze, export, unlock, and lock PromptSave logs."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List all tracked project logs")

    p_view = sub.add_parser("view", help="Decrypt and print a project's prompt history")
    p_view.add_argument("project", help="Project name (e.g. my-web-app)")

    p_search = sub.add_parser("search", help="Search across all encrypted prompt logs")
    p_search.add_argument("query", help="Keyword or phrase to search for")
    p_search.add_argument("--tool", help="Filter by AI CLI (e.g. claude, codex, cursor, gemini)")
    p_search.add_argument("--project", help="Filter by project name substring")

    p_handoff = sub.add_parser("handoff", help="Generate a context-handoff brief for switching AI CLIs")
    p_handoff.add_argument("project", help="Project name")
    p_handoff.add_argument("--last", type=int, default=10, help="Include last N prompts (default: 10)")
    p_handoff.add_argument("--no-copy", action="store_true", help="Print only; do not copy to clipboard")

    p_pin = sub.add_parser("pin", help="Pin a reusable prompt under a short tag")
    p_pin.add_argument("project", help="Project name")
    p_pin.add_argument("number", type=int, help="Prompt number (e.g. 4)")
    p_pin.add_argument("--tag", "-t", required=True, help="Short tag name (e.g. refactor)")

    sub.add_parser("pins", help="List all pinned prompts")

    p_copy = sub.add_parser("copy", help="Print and copy a pinned prompt to clipboard")
    p_copy.add_argument("tag", help="Pin tag name")
    p_copy.add_argument("--no-copy", action="store_true", help="Print only; do not copy to clipboard")

    p_unpin = sub.add_parser("unpin", help="Remove a pinned prompt")
    p_unpin.add_argument("tag", help="Pin tag name")

    sub.add_parser("stats", help="Show prompt counts by AI tool and by project")

    p_export = sub.add_parser("export", help="Export a project's prompts to json, md, or html")
    p_export.add_argument("project", help="Project name")
    p_export.add_argument("--format", "-f", choices=("json", "md", "html"), default="json")
    p_export.add_argument("--output", "-o", help="Output file path (prints to stdout if omitted)")

    sub.add_parser("unlock", help="Decrypt all .md.enc files to .md for local browsing")
    sub.add_parser("lock", help="Encrypt all .md files to .md.enc and remove plaintext copies")

    args = parser.parse_args(argv)
    center, key = resolve_context()

    if args.command == "list":
        cmd_list(center)
    elif args.command == "view":
        cmd_view(center, key, args.project)
    elif args.command == "search":
        cmd_search(center, key, args.query, tool_filter=args.tool, project_filter=args.project)
    elif args.command == "handoff":
        cmd_handoff(center, key, args.project, last_n=args.last, no_copy=args.no_copy)
    elif args.command == "pin":
        cmd_pin(center, key, args.project, args.number, args.tag)
    elif args.command == "pins":
        cmd_pins()
    elif args.command == "copy":
        cmd_copy(args.tag, no_copy=args.no_copy)
    elif args.command == "unpin":
        cmd_unpin(args.tag)
    elif args.command == "stats":
        cmd_stats(center, key)
    elif args.command == "export":
        cmd_export(center, key, args.project, args.format, output_path=args.output)
    elif args.command == "unlock":
        cmd_unlock(center, key)
    elif args.command == "lock":
        cmd_lock(center, key)


if __name__ == "__main__":
    main()
