#!/usr/bin/env python3
"""
PromptSave Vault CLI - View, unlock, and lock your .env-encrypted prompt logs.

Usage:
    python3 promptsave/vault.py list              List all stored projects
    python3 promptsave/vault.py view <project>    Decrypt and print a project's prompts
    python3 promptsave/vault.py unlock            Temporarily decrypt .md.enc -> .md for reading
    python3 promptsave/vault.py lock              Encrypt plaintext .md -> .md.enc and remove plaintext
"""
import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import crypto  # noqa: E402
import hook  # noqa: E402


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
            "Run `python3 promptsave/install.py` to generate a local .env key.",
            file=sys.stderr,
        )
        sys.exit(1)


def cmd_list(center):
    files = sorted(
        f for f in os.listdir(center) if f.endswith(".md") or f.endswith(".md.enc")
    )
    if not files:
        print("No saved project logs yet.")
        return
    print(f"Projects directory: {center}\n")
    for fname in files:
        if fname.endswith(".md.enc"):
            print(f"  [encrypted]  {fname[:-7]}  ({fname})")
        else:
            print(f"  [plaintext]  {fname[:-3]}  ({fname})")


def cmd_view(center, key, project_name):
    base = project_name
    for suffix in (".md.enc", ".md"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    enc_path = os.path.join(center, f"{base}.md.enc")
    plain_path = os.path.join(center, f"{base}.md")

    if os.path.isfile(enc_path):
        require_key(key)
        with open(enc_path, "r", encoding="utf-8") as f:
            try:
                print(crypto.decrypt_text(f.read(), key))
            except ValueError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                sys.exit(1)
    elif os.path.isfile(plain_path):
        with open(plain_path, "r", encoding="utf-8") as f:
            print(f.read())
    else:
        print(f"Error: Project '{project_name}' not found in {center}", file=sys.stderr)
        sys.exit(1)


def cmd_unlock(center, key):
    require_key(key)
    count = 0
    for fname in sorted(os.listdir(center)):
        if not fname.endswith(".md.enc"):
            continue
        enc_path = os.path.join(center, fname)
        plain_path = os.path.join(center, fname[:-4])  # strip .enc
        with open(enc_path, "r", encoding="utf-8") as f:
            plaintext = crypto.decrypt_text(f.read(), key)
        with open(plain_path, "w", encoding="utf-8") as f:
            f.write(plaintext)
        count += 1
    print(f"Unlocked {count} file(s) in {center}. Run `vault.py lock` when done reading.")


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
        description="Manage and read .env-encrypted PromptSave logs."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List all tracked project logs")
    p_view = sub.add_parser("view", help="Decrypt and print a project's prompt history")
    p_view.add_argument("project", help="Project name (e.g. my-web-app)")
    sub.add_parser("unlock", help="Decrypt all .md.enc files to .md for local browsing")
    sub.add_parser("lock", help="Encrypt all .md files to .md.enc and remove plaintext copies")

    args = parser.parse_args(argv)
    center, key = resolve_context()

    if args.command == "list":
        cmd_list(center)
    elif args.command == "view":
        cmd_view(center, key, args.project)
    elif args.command == "unlock":
        cmd_unlock(center, key)
    elif args.command == "lock":
        cmd_lock(center, key)


if __name__ == "__main__":
    main()
