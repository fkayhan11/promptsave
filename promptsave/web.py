#!/usr/bin/env python3
"""
PromptSave Local Web UI — Zero-dependency localhost browser interface.

Binds strictly to 127.0.0.1, decrypts your .env-protected logs purely in
memory, and provides live search, AI tool filters, one-click copy, pinning,
and AI context handoff generation.

Usage:
    promptsave ui [--port 8787] [--no-browser]
"""
import argparse
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import sys
import urllib.parse
import webbrowser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import vault  # noqa: E402

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PromptSave Vault</title>
<style>
  :root {
    --bg: #0b0f17; --panel: #111827; --card: #161f30; --border: #253047;
    --text: #e5e7eb; --muted: #94a3b8; --accent: #60a5fa; --accent-bg: #1e3a5f;
    --green: #34d399; --purple: #a78bfa;
  }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background: var(--bg); color: var(--text); display: flex; height: 100vh; overflow: hidden; }
  aside { width: 260px; background: var(--panel); border-right: 1px solid var(--border);
          display: flex; flex-direction: column; flex-shrink: 0; }
  .brand { padding: 1.1rem 1.2rem; border-bottom: 1px solid var(--border); }
  .brand h1 { margin: 0; font-size: 1.15rem; letter-spacing: -0.02em; }
  .brand .sub { font-size: 0.78rem; color: var(--muted); margin-top: 0.25rem; }
  .nav { padding: 0.75rem; overflow-y: auto; flex: 1; }
  .nav-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em;
               color: var(--muted); padding: 0.5rem 0.6rem 0.35rem; }
  .nav-item { display: flex; justify-content: space-between; align-items: center; width: 100%;
              background: transparent; border: none; color: var(--text); padding: 0.55rem 0.7rem;
              border-radius: 7px; cursor: pointer; font-size: 0.88rem; text-align: left; }
  .nav-item:hover { background: rgba(255,255,255,0.05); }
  .nav-item.active { background: var(--accent-bg); color: #fff; font-weight: 600; }
  .badge { font-size: 0.74rem; color: var(--muted); background: rgba(255,255,255,0.06);
           padding: 0.1rem 0.45rem; border-radius: 999px; }
  main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
  .topbar { padding: 0.9rem 1.4rem; border-bottom: 1px solid var(--border); background: var(--panel);
            display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }
  .search { flex: 1; min-width: 220px; background: var(--bg); border: 1px solid var(--border);
            color: var(--text); padding: 0.55rem 0.85rem; border-radius: 8px; font-size: 0.9rem; outline: none; }
  .search:focus { border-color: var(--accent); }
  .pills { display: flex; gap: 0.4rem; flex-wrap: wrap; }
  .pill { background: var(--bg); border: 1px solid var(--border); color: var(--muted);
          padding: 0.35rem 0.7rem; border-radius: 999px; font-size: 0.8rem; cursor: pointer; }
  .pill.active { background: var(--accent); color: #0b0f17; border-color: var(--accent); font-weight: 600; }
  .btn { background: var(--accent-bg); border: 1px solid var(--accent); color: #fff;
         padding: 0.45rem 0.85rem; border-radius: 7px; font-size: 0.82rem; cursor: pointer; font-weight: 500; }
  .btn:hover { filter: brightness(1.12); }
  .btn-ghost { background: transparent; border: 1px solid var(--border); color: var(--muted);
               padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.76rem; cursor: pointer; }
  .btn-ghost:hover { color: var(--text); border-color: var(--muted); }
  .content { flex: 1; overflow-y: auto; padding: 1.4rem; }
  .header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; gap: 1rem; }
  .header-row h2 { margin: 0; font-size: 1.25rem; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px;
          padding: 1rem 1.15rem; margin-bottom: 0.9rem; }
  .card-head { display: flex; align-items: center; gap: 0.55rem; flex-wrap: wrap; margin-bottom: 0.65rem; font-size: 0.82rem; }
  .num { color: var(--accent); font-weight: 700; }
  .proj-tag { color: var(--purple); font-weight: 600; }
  .tool-tag { background: rgba(255,255,255,0.06); padding: 0.15rem 0.55rem; border-radius: 999px; }
  .git-tag { background: rgba(52,211,153,0.12); color: var(--green); padding: 0.15rem 0.55rem;
             border-radius: 999px; font-family: ui-monospace, monospace; font-size: 0.76rem; }
  .ts { color: var(--muted); margin-left: auto; }
  pre { margin: 0; white-space: pre-wrap; word-wrap: break-word; background: var(--bg);
        padding: 0.85rem 1rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.88rem; line-height: 1.5; }
  .empty { color: var(--muted); text-align: center; padding: 3rem 1rem; }
  .toast { position: fixed; bottom: 1.25rem; right: 1.25rem; background: #16a34a; color: #fff;
           padding: 0.6rem 1rem; border-radius: 8px; font-size: 0.85rem; font-weight: 500;
           opacity: 0; transition: opacity 0.2s; pointer-events: none; }
  .toast.show { opacity: 1; }
</style>
</head>
<body>
  <aside>
    <div class="brand">
      <h1>PromptSave Vault</h1>
      <div class="sub" id="vaultMeta">Loading...</div>
    </div>
    <div class="nav" id="sidebar"></div>
  </aside>
  <main>
    <div class="topbar">
      <input class="search" id="searchInput" placeholder="Search prompts across projects..." autocomplete="off">
      <div class="pills" id="toolPills"></div>
      <button class="btn" id="handoffBtn" style="display:none">Copy Handoff</button>
    </div>
    <div class="content" id="content"></div>
  </main>
  <div class="toast" id="toast">Copied!</div>
<script>
let DATA = { projects: [], pins: {}, stats: {} };
let ACTIVE = "__all__";
let TOOL = "All";

function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 1800);
}

async function copyText(text, label) {
  await navigator.clipboard.writeText(text);
  toast(label || "Copied to clipboard!");
}

function esc(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function renderSidebar() {
  const sb = document.getElementById("sidebar");
  const total = DATA.stats.total_prompts || 0;
  const pinCount = Object.keys(DATA.pins || {}).length;
  let html = `<div class="nav-label">Overview</div>`;
  html += `<button class="nav-item ${ACTIVE==='__all__'?'active':''}" onclick="selectView('__all__')">All Prompts <span class="badge">${total}</span></button>`;
  html += `<button class="nav-item ${ACTIVE==='__pins__'?'active':''}" onclick="selectView('__pins__')">Pinned <span class="badge">${pinCount}</span></button>`;
  html += `<div class="nav-label">Projects</div>`;
  for (const p of DATA.projects) {
    html += `<button class="nav-item ${ACTIVE===p.name?'active':''}" onclick="selectView('${esc(p.name)}')">${esc(p.name)} <span class="badge">${p.count}</span></button>`;
  }
  sb.innerHTML = html;
}

function renderPills() {
  const tools = ["All", ...Object.keys(DATA.stats.by_tool || {})];
  document.getElementById("toolPills").innerHTML = tools.map(t =>
    `<button class="pill ${TOOL===t?'active':''}" onclick="selectTool('${esc(t)}')">${esc(t)}</button>`
  ).join("");
}

function selectView(v) { ACTIVE = v; renderSidebar(); renderContent(); }
function selectTool(t) { TOOL = t; renderPills(); renderContent(); }

async function pinPrompt(project, number) {
  const tag = prompt(`Pin ${project} #${number} under tag name:`, `${project}-${number}`);
  if (!tag) return;
  const res = await fetch("/api/pin", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ project, number, tag: tag.trim() })
  });
  if (res.ok) {
    toast(`Pinned as '${tag.trim()}'`);
    await loadData();
  }
}

async function copyHandoff() {
  if (ACTIVE.startsWith("__")) return;
  const res = await fetch(`/api/handoff?project=${encodeURIComponent(ACTIVE)}&last=10`);
  const data = await res.json();
  if (data.text) await copyText(data.text, `Copied handoff for ${ACTIVE}!`);
}

function renderContent() {
  const q = document.getElementById("searchInput").value.trim().toLowerCase();
  const hBtn = document.getElementById("handoffBtn");
  hBtn.style.display = ACTIVE.startsWith("__") ? "none" : "inline-block";
  const box = document.getElementById("content");

  if (ACTIVE === "__pins__") {
    const entries = Object.entries(DATA.pins || {});
    if (!entries.length) { box.innerHTML = `<div class="empty">No pinned prompts yet. Click "Pin" on any prompt card to save it here.</div>`; return; }
    box.innerHTML = `<div class="header-row"><h2>Pinned Prompts</h2></div>` + entries.map(([tag, info]) => `
      <div class="card">
        <div class="card-head">
          <span class="num">${esc(tag)}</span>
          <span class="proj-tag">${esc(info.project)} #${info.number}</span>
          <span class="tool-tag">${esc(info.tool)}</span>
          <span class="ts">${esc(info.pinned_at || "")}</span>
          <button class="btn-ghost" onclick='copyText(${JSON.stringify(info.prompt)}, "Copied pin!")'>Copy</button>
        </div>
        <pre>${esc(info.prompt)}</pre>
      </div>`).join("");
    return;
  }

  let items = [];
  for (const p of DATA.projects) {
    if (ACTIVE !== "__all__" && p.name !== ACTIVE) continue;
    for (const e of p.entries) {
      if (TOOL !== "All" && e.tool !== TOOL) continue;
      if (q && !e.prompt.toLowerCase().includes(q) && !p.name.toLowerCase().includes(q)) continue;
      items.push({ ...e, project: p.name });
    }
  }
  items.reverse();

  const title = ACTIVE === "__all__" ? "All Prompts" : ACTIVE;
  if (!items.length) {
    box.innerHTML = `<div class="header-row"><h2>${esc(title)}</h2></div><div class="empty">No matching prompts found.</div>`;
    return;
  }
  box.innerHTML = `<div class="header-row"><h2>${esc(title)} (${items.length})</h2></div>` + items.map(e => `
    <div class="card">
      <div class="card-head">
        <span class="num">#${e.number}</span>
        ${ACTIVE === "__all__" ? `<span class="proj-tag">${esc(e.project)}</span>` : ""}
        <span class="tool-tag">${esc(e.tool)}</span>
        ${e.git ? `<span class="git-tag">${esc(e.git)}</span>` : ""}
        <span class="ts">${esc(e.timestamp)}</span>
        <button class="btn-ghost" onclick='copyText(${JSON.stringify(e.prompt)}, "Prompt copied!")'>Copy</button>
        <button class="btn-ghost" onclick='pinPrompt(${JSON.stringify(e.project)}, ${e.number})'>Pin</button>
      </div>
      <pre>${esc(e.prompt)}</pre>
    </div>`).join("");
}

async function loadData() {
  const res = await fetch("/api/data");
  DATA = await res.json();
  document.getElementById("vaultMeta").textContent =
    `${DATA.stats.total_projects} projects · ${DATA.stats.total_prompts} prompts · ${DATA.stats.encrypted ? "Encrypted" : "Plaintext"}`;
  renderSidebar();
  renderPills();
  renderContent();
}

document.getElementById("searchInput").addEventListener("input", renderContent);
document.getElementById("handoffBtn").addEventListener("click", copyHandoff);
loadData();
</script>
</body>
</html>
"""


def build_vault_snapshot():
    center, key = vault.resolve_context()
    projects_map = vault.discover_projects(center)
    projects = []
    tool_counts = Counter()
    total = 0
    any_enc = False

    for name, (path, is_enc) in projects_map.items():
        if is_enc:
            any_enc = True
        try:
            text = vault.read_project_text(path, is_enc, key)
            entries = vault.parse_entries(text)
        except Exception:
            entries = []
        for e in entries:
            tool_counts[e["tool"]] += 1
        total += len(entries)
        projects.append(
            {"name": name, "encrypted": is_enc, "count": len(entries), "entries": entries}
        )

    return {
        "projects": projects,
        "pins": vault.load_pins(),
        "stats": {
            "total_projects": len(projects),
            "total_prompts": total,
            "by_tool": dict(tool_counts.most_common()),
            "encrypted": any_enc,
        },
    }


class VaultHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return  # Keep terminal clean

    def _send(self, code, content_type, body):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self._send(200, "text/html; charset=utf-8", HTML_PAGE)
        elif parsed.path == "/api/data":
            self._send(200, "application/json; charset=utf-8", json.dumps(build_vault_snapshot()))
        elif parsed.path == "/api/handoff":
            qs = urllib.parse.parse_qs(parsed.query)
            proj = (qs.get("project") or [""])[0]
            last_n = int((qs.get("last") or ["10"])[0])
            center, key = vault.resolve_context()
            try:
                name, _, entries = vault.load_project_entries(center, key, proj)
                text = vault.build_handoff_text(name, entries, last_n=last_n)
                self._send(200, "application/json; charset=utf-8", json.dumps({"text": text}))
            except Exception as exc:
                self._send(404, "application/json; charset=utf-8", json.dumps({"error": str(exc)}))
        else:
            self._send(404, "text/plain; charset=utf-8", "Not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/pin":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            try:
                body = json.loads(raw)
                center, key = vault.resolve_context()
                vault.cmd_pin(center, key, body["project"], int(body["number"]), body["tag"])
                self._send(200, "application/json; charset=utf-8", '{"ok": true}')
            except Exception as exc:
                self._send(400, "application/json; charset=utf-8", json.dumps({"error": str(exc)}))
        else:
            self._send(404, "text/plain; charset=utf-8", "Not found")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Launch the local PromptSave web UI.")
    parser.add_argument("--port", "-p", type=int, default=8787, help="Localhost port (default: 8787)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically")
    args = parser.parse_args(argv)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), VaultHandler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"PromptSave Vault UI running at {url} (localhost only)")
    print("Press Ctrl+C to stop.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped PromptSave UI.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
