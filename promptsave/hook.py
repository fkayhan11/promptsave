#!/usr/bin/env python3
"""
PromptSave hook - Automatically logs prompts sent to AI CLIs (Claude Code,
OpenAI Codex CLI, Antigravity CLI) into numbered Markdown files organized by
project, with optional authenticated .env encryption.

Layout:
    <repo>/
      .env                 -> Local secret key (gitignored, never shared)
      projects/
        my-project.md.enc  -> Encrypted numbered prompt history (or .md if unencrypted)
      summary/
        README.md          -> Auto-generated overview table of all tracked projects

Usage (invoked automatically by CLI lifecycle hooks):
    python3 hook.py <claude|codex|antigravity>   (reads JSON payload from stdin)

Design guarantees:
    - Zero external dependencies (Python 3.8+ standard library only)
    - Cross-platform (macOS, Linux, Windows)
    - Never blocks or crashes the host AI CLI (always exits with code 0)
"""
from contextlib import contextmanager
import datetime
import hashlib
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import crypto  # noqa: E402

FOLDER_NAME = "promptsave"
MARKER = ".promptsave"
TOOL_NAMES = {
    "claude": "Claude Code",
    "codex": "Codex",
    "antigravity": "Antigravity",
    "gemini": "Gemini CLI",
    "cursor": "Cursor",
}


def get_state_dir():
    return os.path.expanduser(os.environ.get("PROMPTSAVE_HOME", "~/.promptsave"))


def get_config_path():
    return os.path.join(get_state_dir(), "config.json")


def get_container_dirs():
    home = os.path.expanduser("~")
    candidates = [
        "/",
        home,
        os.path.join(home, "Desktop"),
        os.path.join(home, "Documents"),
        os.path.join(home, "Downloads"),
    ]
    return {os.path.realpath(p) for p in candidates if p}


@contextmanager
def file_lock(lock_path):
    """Cross-platform advisory file lock (Unix fcntl / Windows msvcrt)."""
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    with open(lock_path, "a+", encoding="utf-8") as lock_file:
        try:
            import fcntl

            fcntl.flock(lock_file, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
        except ImportError:
            try:
                import msvcrt

                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                yield


def central_dir():
    with open(get_config_path(), "r", encoding="utf-8") as f:
        cfg = json.load(f)
    d = cfg.get("center") or cfg.get("merkez")
    if not d:
        raise ValueError("Missing center directory in config.json")
    os.makedirs(d, exist_ok=True)
    return d


def get_encryption_settings(center):
    """Return (enabled: bool, secret_key: str) from repo .env or environment."""
    repo_root = os.path.dirname(center)
    env_vals = crypto.load_env(os.path.join(repo_root, ".env"))
    key = os.environ.get("PROMPTSAVE_KEY") or env_vals.get("PROMPTSAVE_KEY", "")
    enc_flag = os.environ.get("PROMPTSAVE_ENCRYPT") or env_vals.get("PROMPTSAVE_ENCRYPT", "")
    if enc_flag:
        enabled = enc_flag.strip().lower() in ("1", "true", "yes", "on")
    else:
        enabled = bool(key)
    return enabled and bool(key), key


def has_marker(directory, central_repo=None):
    """Check whether `directory` contains a promptsave marker folder/file.

    Recognizes:
      - <dir>/.promptsave
      - <dir>/promptsave/.promptsave
      - <dir>/promptsave copy/.promptsave
      - <dir>/<repo-copy>/promptsave/.promptsave
    """
    if os.path.isfile(os.path.join(directory, MARKER)):
        return True
    if os.path.realpath(directory) in get_container_dirs():
        return False
    try:
        entries = list(os.scandir(directory))
    except OSError:
        return False
    for entry in entries:
        try:
            if not entry.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue
        if "promptsave" not in entry.name.lower():
            continue
        if central_repo and os.path.realpath(entry.path) == central_repo:
            continue
        if os.path.isfile(os.path.join(entry.path, MARKER)):
            return True
        if os.path.isfile(os.path.join(entry.path, FOLDER_NAME, MARKER)):
            return True
    return False


def find_project(start_dirs, central_repo=None):
    """Walk upward from candidate working directories to locate a tracked project root."""
    for start in start_dirs:
        if not start:
            continue
        d = os.path.abspath(start)
        while True:
            if has_marker(d, central_repo):
                return d
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    return None


def clean_prompt(text):
    if not isinstance(text, str):
        return ""
    matches = re.findall(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", text, re.S)
    if matches:
        text = matches[-1]
    text = re.sub(r"<ADDITIONAL_METADATA>.*?</ADDITIONAL_METADATA>", "", text, flags=re.S)
    return text.strip()


def extract(tool, data):
    """Extract (prompt_text, session_id, candidate_cwds) from a hook JSON payload."""
    if tool == "antigravity":
        prompt = data.get("lastUserInput", "")
        session = data.get("conversationId", "")
        cwds = [data.get("cwd")] + list(data.get("workspacePaths") or [])
    elif tool == "cursor":
        prompt = data.get("prompt") or ""
        session = data.get("conversation_id") or data.get("session_id") or ""
        cwds = [data.get("cwd")] + list(data.get("workspace_roots") or [])
    else:  # claude, codex, gemini
        prompt = data.get("prompt") or data.get("user_prompt") or ""
        session = data.get("session_id") or data.get("sessionId") or ""
        cwds = [data.get("cwd")]
    cwds = [c for c in cwds if c]
    if not cwds:
        cwds.append(os.getcwd())
    return clean_prompt(prompt), session, cwds


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def last_user_step(transcript):
    """Read the latest USER_INPUT step_index from an Antigravity JSONL transcript."""
    if not transcript:
        return ""
    try:
        with open(transcript, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 4_000_000))
            last = ""
            for line in f:
                if b'"USER_INPUT"' in line:
                    m = re.search(rb'"step_index":\s*(\d+)', line)
                    if m:
                        last = m.group(1).decode()
            return last
    except Exception:
        return ""


def already_logged(tool, session, prompt, data):
    """Deduplicate repeated PreInvocation calls within the same Antigravity turn."""
    if tool != "antigravity":
        return False
    state_dir = get_state_dir()
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, ".state.json")
    state = load_json(path, {})
    step_id = last_user_step(data.get("transcriptPath"))
    key = hashlib.sha1(f"{prompt}|{step_id}".encode("utf-8")).hexdigest()
    if state.get(session) == key:
        return True
    state[session] = key
    if len(state) > 200:
        state = dict(list(state.items())[-100:])
    save_json(path, state)
    return False


def safe_name(name):
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", name).strip()
    return cleaned or "project"


def project_file(projects, project_path):
    """Assign a stable, unique Markdown base filename to each project path."""
    if project_path in projects:
        return projects[project_path]
    base = safe_name(os.path.basename(project_path))
    used = set(projects.values())
    fname, i = f"{base}.md", 2
    while fname in used or fname.lower() == "readme.md":
        fname, i = f"{base} ({i}).md", i + 1
    projects[project_path] = fname
    return fname


def code_fence_for(text):
    """Return a backtick fence longer than any backtick run inside `text`."""
    runs = re.findall(r"`+", text)
    longest = max((len(r) for r in runs), default=0)
    return "`" * max(3, longest + 1)


def read_project_content(center, fname, encrypted, key):
    enc_path = os.path.join(center, fname + ".enc")
    plain_path = os.path.join(center, fname)
    if encrypted and os.path.isfile(enc_path):
        with open(enc_path, "r", encoding="utf-8") as f:
            return crypto.decrypt_text(f.read(), key)
    if os.path.isfile(plain_path):
        with open(plain_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def write_project_content(center, fname, content, encrypted, key):
    if encrypted:
        target = os.path.join(center, fname + ".enc")
        payload = crypto.encrypt_text(content, key)
    else:
        target = os.path.join(center, fname)
        payload = content
    tmp_path = target + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(payload)
    os.replace(tmp_path, target)


def write_index(center, projects, encrypted, key):
    rows = []
    for path, fname in projects.items():
        try:
            content = read_project_content(center, fname, encrypted, key)
        except Exception:
            continue
        if not content:
            continue
        heads = re.findall(r"^## (\d+)\. (.+?) · (.+)$", content, re.M)
        if not heads:
            continue
        last = heads[-1]
        rows.append((last[2], fname, path, len(heads), last[1]))
    rows.sort(reverse=True)
    summary_dir = os.path.join(os.path.dirname(center), "summary")
    os.makedirs(summary_dir, exist_ok=True)
    out = [
        "# PromptSave Overview\n",
        "> Auto-generated by PromptSave. Encrypted logs can be read with `python3 promptsave/vault.py view <project>`.\n",
        "| Project | Prompts | Last Prompt | Last CLI | Storage | Location |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for when, fname, path, count, tool in rows:
        name = fname[:-3]
        if encrypted:
            cell = f"`{name}`"
            storage = "Encrypted (`.md.enc`)"
        else:
            link = "../projects/" + fname.replace(" ", "%20")
            cell = f"[{name}]({link})"
            storage = "Plaintext (`.md`)"
        out.append(f"| {cell} | {count} | {when} | {tool} | {storage} | `{path}` |")
    with open(os.path.join(summary_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def append_entry(center, project_path, tool, prompt):
    state_dir = get_state_dir()
    os.makedirs(state_dir, exist_ok=True)
    encrypted, key = get_encryption_settings(center)

    with file_lock(os.path.join(state_dir, ".lock")):
        reg_path = os.path.join(state_dir, ".projects.json")
        # Seamless migration from legacy registry name if present
        legacy_reg = os.path.join(state_dir, ".projeler.json")
        if not os.path.exists(reg_path) and os.path.exists(legacy_reg):
            os.replace(legacy_reg, reg_path)

        projects = load_json(reg_path, {})
        fname = project_file(projects, project_path)
        save_json(reg_path, projects)

        content = read_project_content(center, fname, encrypted, key)
        nums = re.findall(r"^## (\d+)\.", content, re.M)
        n = int(nums[-1]) + 1 if nums else 1
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        fence = code_fence_for(prompt)

        if not content:
            content = (
                f"# {fname[:-3]} — Prompt History\n\n"
                f"> Project path: `{project_path}`\n\n"
                "[Back to Overview](../summary/README.md)\n\n"
            )
        content += (
            f"## {n}. {TOOL_NAMES.get(tool, tool)} · {now}\n\n"
            f"{fence}text\n{prompt}\n{fence}\n\n---\n\n"
        )
        write_project_content(center, fname, content, encrypted, key)
        write_index(center, projects, encrypted, key)


def emit_allow_response(tool):
    """Print tool-specific non-blocking allow JSON to stdout when required."""
    if tool == "antigravity":
        print("{}")
    elif tool == "gemini":
        print('{"decision": "allow"}')
    elif tool == "cursor":
        print('{"continue": true}')


def main():
    tool = sys.argv[1] if len(sys.argv) > 1 else "claude"
    raw = sys.stdin.read().lstrip("\ufeff")
    try:
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    prompt, session, cwds = extract(tool, data)
    if prompt:
        center = central_dir()
        central_repo = os.path.realpath(os.path.dirname(center))
        project = find_project(cwds, central_repo)
        if project and not already_logged(tool, session, prompt, data):
            append_entry(center, project, tool, prompt)

    emit_allow_response(tool)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if len(sys.argv) > 1:
            emit_allow_response(sys.argv[1])
    sys.exit(0)
