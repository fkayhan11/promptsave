#!/usr/bin/env python3
"""
PromptSave Desktop GUI — Zero-dependency native dark-mode desktop application
built with Python's standard `tkinter` library.

Launch with:
    python3 main.py
    promptsave gui

Features:
    - Decrypts .env-protected prompt logs purely in memory
    - Project sidebar + Pinned prompts view + Track New Folder dialog
    - Instant live search & AI tool filter
    - One-click Copy, Pin/Unpin, Copy AI Handoff, Export (HTML/JSON/MD), and Stats
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import vault  # noqa: E402
import web  # noqa: E402

COLORS = {
    "bg": "#0b0f17",
    "panel": "#111827",
    "card": "#161f30",
    "code": "#0d1320",
    "border": "#253047",
    "text": "#e5e7eb",
    "muted": "#94a3b8",
    "accent": "#3b82f6",
    "accent_hover": "#2563eb",
    "active_bg": "#1e3a5f",
    "green": "#34d399",
    "purple": "#a78bfa",
}


def launch_gui():
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, simpledialog, ttk
    except ImportError as exc:
        print(
            f"Tkinter is not available in this Python environment ({exc}).\n"
            "Falling back to local Web UI (`promptsave ui`)...",
            file=sys.stderr,
        )
        web.main([])
        return

    class PromptSaveApp(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("PromptSave Vault")
            self.geometry("1120x720")
            self.minsize(820, 520)
            self.configure(bg=COLORS["bg"])

            self.snapshot = {"projects": [], "pins": {}, "stats": {}}
            self.active_view = "__all__"
            self.search_var = tk.StringVar()
            self.tool_var = tk.StringVar(value="All")
            self.status_var = tk.StringVar(value="Ready")

            self._configure_styles()
            self._build_layout()
            self.reload_data()

            self.search_var.trace_add("write", lambda *_: self.render_cards())
            self.bind("<Command-f>", lambda _: self.search_entry.focus_set())
            self.bind("<Control-f>", lambda _: self.search_entry.focus_set())
            self.bind("<Command-r>", lambda _: self.reload_data())
            self.bind("<Control-r>", lambda _: self.reload_data())

        def _configure_styles(self):
            style = ttk.Style(self)
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass
            style.configure(
                "TCombobox",
                fieldbackground=COLORS["bg"],
                background=COLORS["panel"],
                foreground=COLORS["text"],
                bordercolor=COLORS["border"],
                arrowcolor=COLORS["text"],
            )
            style.configure(
                "Vertical.TScrollbar",
                background=COLORS["panel"],
                troughcolor=COLORS["bg"],
                bordercolor=COLORS["bg"],
                arrowcolor=COLORS["muted"],
            )

        def _make_btn(self, parent, text, command, primary=False, padx=10, pady=5):
            bg = COLORS["accent"] if primary else COLORS["card"]
            fg = "#ffffff" if primary else COLORS["text"]
            btn = tk.Label(
                parent,
                text=text,
                bg=bg,
                fg=fg,
                padx=padx,
                pady=pady,
                cursor="hand2",
                font=("Helvetica", 11, "bold" if primary else "normal"),
                highlightthickness=1,
                highlightbackground=COLORS["accent"] if primary else COLORS["border"],
            )
            btn.bind("<Button-1>", lambda _: command())
            hover_bg = COLORS["accent_hover"] if primary else COLORS["active_bg"]
            btn.bind("<Enter>", lambda _: btn.configure(bg=hover_bg))
            btn.bind("<Leave>", lambda _: btn.configure(bg=bg))
            return btn

        def _build_layout(self):
            # Left sidebar
            sidebar = tk.Frame(self, bg=COLORS["panel"], width=250)
            sidebar.pack(side="left", fill="y")
            sidebar.pack_propagate(False)

            brand = tk.Frame(sidebar, bg=COLORS["panel"], padx=16, pady=16)
            brand.pack(fill="x")
            tk.Label(
                brand,
                text="PromptSave Vault",
                bg=COLORS["panel"],
                fg="#ffffff",
                font=("Helvetica", 15, "bold"),
                anchor="w",
            ).pack(fill="x")
            self.meta_label = tk.Label(
                brand,
                text="Loading...",
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                font=("Helvetica", 10),
                anchor="w",
            )
            self.meta_label.pack(fill="x", pady=(3, 0))

            tk.Frame(sidebar, bg=COLORS["border"], height=1).pack(fill="x")

            self.nav_frame = tk.Frame(sidebar, bg=COLORS["panel"], padx=10, pady=10)
            self.nav_frame.pack(fill="both", expand=True)

            tk.Frame(sidebar, bg=COLORS["border"], height=1).pack(fill="x")
            actions = tk.Frame(sidebar, bg=COLORS["panel"], padx=12, pady=12)
            actions.pack(fill="x")
            self._make_btn(actions, "+ Track Project Folder", self.track_folder, primary=True).pack(
                fill="x", pady=(0, 6)
            )
            row = tk.Frame(actions, bg=COLORS["panel"])
            row.pack(fill="x")
            self._make_btn(row, "Refresh", self.reload_data, padx=8, pady=4).pack(
                side="left", expand=True, fill="x", padx=(0, 4)
            )
            self._make_btn(row, "Stats", self.show_stats, padx=8, pady=4).pack(
                side="left", expand=True, fill="x", padx=(4, 0)
            )

            # Vertical divider
            tk.Frame(self, bg=COLORS["border"], width=1).pack(side="left", fill="y")

            # Right main column
            main = tk.Frame(self, bg=COLORS["bg"])
            main.pack(side="left", fill="both", expand=True)

            # Top toolbar
            topbar = tk.Frame(main, bg=COLORS["panel"], padx=16, pady=12)
            topbar.pack(fill="x")

            search_box = tk.Frame(
                topbar,
                bg=COLORS["bg"],
                highlightthickness=1,
                highlightbackground=COLORS["border"],
            )
            search_box.pack(side="left", fill="x", expand=True, padx=(0, 10))
            tk.Label(
                search_box, text="Search:", bg=COLORS["bg"], fg=COLORS["muted"], padx=8
            ).pack(side="left")
            self.search_entry = tk.Entry(
                search_box,
                textvariable=self.search_var,
                bg=COLORS["bg"],
                fg=COLORS["text"],
                insertbackground="#ffffff",
                relief="flat",
                font=("Helvetica", 12),
            )
            self.search_entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))

            self.tool_combo = ttk.Combobox(
                topbar,
                textvariable=self.tool_var,
                values=["All"],
                state="readonly",
                width=14,
            )
            self.tool_combo.pack(side="left", padx=(0, 10))
            self.tool_combo.bind("<<ComboboxSelected>>", lambda _: self.render_cards())

            self.handoff_btn = self._make_btn(
                topbar, "Copy Handoff", self.copy_handoff, primary=True, padx=10, pady=5
            )
            self.handoff_btn.pack(side="left", padx=(0, 8))

            self.export_btn = self._make_btn(
                topbar, "Export", self.export_active, primary=False, padx=10, pady=5
            )
            self.export_btn.pack(side="left")

            tk.Frame(main, bg=COLORS["border"], height=1).pack(fill="x")

            # Scrollable card container
            body = tk.Frame(main, bg=COLORS["bg"])
            body.pack(fill="both", expand=True)

            self.canvas = tk.Canvas(body, bg=COLORS["bg"], highlightthickness=0)
            scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
            self.cards_frame = tk.Frame(self.canvas, bg=COLORS["bg"], padx=20, pady=16)

            self.cards_window = self.canvas.create_window(
                (0, 0), window=self.cards_frame, anchor="nw"
            )
            self.canvas.configure(yscrollcommand=scrollbar.set)
            self.canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            self.cards_frame.bind(
                "<Configure>",
                lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
            )
            self.canvas.bind(
                "<Configure>",
                lambda e: self.canvas.itemconfigure(self.cards_window, width=e.width),
            )
            self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
            self.canvas.bind_all("<Button-4>", lambda _: self.canvas.yview_scroll(-3, "units"))
            self.canvas.bind_all("<Button-5>", lambda _: self.canvas.yview_scroll(3, "units"))

            # Bottom status bar
            tk.Frame(main, bg=COLORS["border"], height=1).pack(fill="x")
            status_bar = tk.Frame(main, bg=COLORS["panel"], padx=16, pady=6)
            status_bar.pack(fill="x")
            tk.Label(
                status_bar,
                textvariable=self.status_var,
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                font=("Helvetica", 10),
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

        def _on_mousewheel(self, event):
            delta = -1 * (event.delta // 120) if abs(event.delta) >= 120 else -1 * event.delta
            self.canvas.yview_scroll(delta, "units")

        def set_status(self, message):
            self.status_var.set(message)

        def copy_text(self, text, message="Copied to clipboard!"):
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update_idletasks()
            vault.copy_to_clipboard(text)
            self.set_status(message)

        def reload_data(self):
            self.snapshot = web.build_vault_snapshot()
            stats = self.snapshot["stats"]
            mode = "Encrypted (.env)" if stats.get("encrypted") else "Plaintext"
            self.meta_label.configure(
                text=f"{stats.get('total_projects', 0)} projects · {stats.get('total_prompts', 0)} prompts · {mode}"
            )
            tools = ["All"] + list(stats.get("by_tool", {}).keys())
            self.tool_combo.configure(values=tools)
            if self.tool_var.get() not in tools:
                self.tool_var.set("All")
            self.render_sidebar()
            self.render_cards()
            self.set_status("Vault refreshed.")

        def select_view(self, view_id):
            self.active_view = view_id
            self.render_sidebar()
            self.render_cards()
            self.canvas.yview_moveto(0)

        def render_sidebar(self):
            for child in self.nav_frame.winfo_children():
                child.destroy()

            def add_section(title):
                tk.Label(
                    self.nav_frame,
                    text=title,
                    bg=COLORS["panel"],
                    fg=COLORS["muted"],
                    font=("Helvetica", 9, "bold"),
                    anchor="w",
                    padx=6,
                    pady=6,
                ).pack(fill="x")

            def add_item(label, count, view_id):
                active = self.active_view == view_id
                bg = COLORS["active_bg"] if active else COLORS["panel"]
                fg = "#ffffff" if active else COLORS["text"]
                row = tk.Frame(self.nav_frame, bg=bg, cursor="hand2", padx=8, pady=6)
                row.pack(fill="x", pady=1)
                lbl = tk.Label(
                    row,
                    text=label,
                    bg=bg,
                    fg=fg,
                    font=("Helvetica", 11, "bold" if active else "normal"),
                    anchor="w",
                )
                lbl.pack(side="left", fill="x", expand=True)
                cnt = tk.Label(
                    row,
                    text=str(count),
                    bg=COLORS["card"],
                    fg=COLORS["muted"],
                    font=("Helvetica", 9),
                    padx=6,
                    pady=1,
                )
                cnt.pack(side="right")
                for widget in (row, lbl, cnt):
                    widget.bind("<Button-1>", lambda _, v=view_id: self.select_view(v))

            add_section("OVERVIEW")
            add_item("All Prompts", self.snapshot["stats"].get("total_prompts", 0), "__all__")
            add_item("Pinned", len(self.snapshot.get("pins", {})), "__pins__")

            add_section("PROJECTS")
            for proj in self.snapshot.get("projects", []):
                add_item(proj["name"], proj["count"], proj["name"])

        def render_cards(self):
            for child in self.cards_frame.winfo_children():
                child.destroy()

            is_project = not self.active_view.startswith("__")
            if is_project:
                self.handoff_btn.pack(side="left", padx=(0, 8))
                self.export_btn.pack(side="left")
            else:
                self.handoff_btn.pack_forget()
                self.export_btn.pack_forget()

            query = self.search_var.get().strip().lower()
            tool_filter = self.tool_var.get()

            if self.active_view == "__pins__":
                self._render_pins(query)
                return

            items = []
            for proj in self.snapshot.get("projects", []):
                if is_project and proj["name"] != self.active_view:
                    continue
                for entry in proj["entries"]:
                    if tool_filter != "All" and entry["tool"] != tool_filter:
                        continue
                    if query and query not in entry["prompt"].lower() and query not in proj["name"].lower():
                        continue
                    items.append((proj["name"], entry))
            items.reverse()

            title = "All Prompts" if not is_project else self.active_view
            tk.Label(
                self.cards_frame,
                text=f"{title} ({len(items)})",
                bg=COLORS["bg"],
                fg="#ffffff",
                font=("Helvetica", 16, "bold"),
                anchor="w",
            ).pack(fill="x", pady=(0, 12))

            if not items:
                tk.Label(
                    self.cards_frame,
                    text="No matching prompts found.",
                    bg=COLORS["bg"],
                    fg=COLORS["muted"],
                    font=("Helvetica", 12),
                    pady=40,
                ).pack(fill="x")
                return

            for proj_name, entry in items:
                self._render_prompt_card(proj_name, entry, show_project=not is_project)

        def _render_pins(self, query):
            pins = self.snapshot.get("pins", {})
            tk.Label(
                self.cards_frame,
                text=f"Pinned Prompts ({len(pins)})",
                bg=COLORS["bg"],
                fg="#ffffff",
                font=("Helvetica", 16, "bold"),
                anchor="w",
            ).pack(fill="x", pady=(0, 12))

            shown = 0
            for tag, info in sorted(pins.items()):
                if query and query not in tag.lower() and query not in info["prompt"].lower():
                    continue
                shown += 1
                card = tk.Frame(
                    self.cards_frame,
                    bg=COLORS["card"],
                    padx=14,
                    pady=12,
                    highlightthickness=1,
                    highlightbackground=COLORS["border"],
                )
                card.pack(fill="x", pady=(0, 10))
                head = tk.Frame(card, bg=COLORS["card"])
                head.pack(fill="x", pady=(0, 8))
                tk.Label(
                    head, text=f"[{tag}]", bg=COLORS["card"], fg=COLORS["accent"], font=("Helvetica", 11, "bold")
                ).pack(side="left", padx=(0, 8))
                tk.Label(
                    head,
                    text=f"{info['project']} #{info['number']} · {info['tool']}",
                    bg=COLORS["card"],
                    fg=COLORS["purple"],
                    font=("Helvetica", 10),
                ).pack(side="left")

                self._make_btn(
                    head, "Unpin", lambda t=tag: self.unpin_prompt(t), padx=8, pady=2
                ).pack(side="right", padx=(6, 0))
                self._make_btn(
                    head,
                    "Copy",
                    lambda p=info["prompt"], t=tag: self.copy_text(p, f"Copied pin '{t}'!"),
                    padx=8,
                    pady=2,
                ).pack(side="right")

                self._render_code_box(card, info["prompt"])

            if shown == 0:
                tk.Label(
                    self.cards_frame,
                    text="No pinned prompts yet. Click 'Pin' on any prompt card to save it here.",
                    bg=COLORS["bg"],
                    fg=COLORS["muted"],
                    font=("Helvetica", 12),
                    pady=40,
                ).pack(fill="x")

        def _render_prompt_card(self, proj_name, entry, show_project=False):
            card = tk.Frame(
                self.cards_frame,
                bg=COLORS["card"],
                padx=14,
                pady=12,
                highlightthickness=1,
                highlightbackground=COLORS["border"],
            )
            card.pack(fill="x", pady=(0, 10))

            head = tk.Frame(card, bg=COLORS["card"])
            head.pack(fill="x", pady=(0, 8))

            tk.Label(
                head,
                text=f"#{entry['number']}",
                bg=COLORS["card"],
                fg=COLORS["accent"],
                font=("Helvetica", 11, "bold"),
            ).pack(side="left", padx=(0, 8))

            if show_project:
                tk.Label(
                    head,
                    text=proj_name,
                    bg=COLORS["card"],
                    fg=COLORS["purple"],
                    font=("Helvetica", 10, "bold"),
                ).pack(side="left", padx=(0, 8))

            tk.Label(
                head,
                text=entry["tool"],
                bg=COLORS["panel"],
                fg=COLORS["text"],
                font=("Helvetica", 10),
                padx=8,
                pady=2,
            ).pack(side="left", padx=(0, 8))

            if entry.get("git"):
                tk.Label(
                    head,
                    text=entry["git"],
                    bg="#102a25",
                    fg=COLORS["green"],
                    font=("Courier", 10),
                    padx=8,
                    pady=2,
                ).pack(side="left", padx=(0, 8))

            self._make_btn(
                head,
                "Pin",
                lambda p=proj_name, n=entry["number"]: self.pin_prompt(p, n),
                padx=8,
                pady=2,
            ).pack(side="right", padx=(6, 0))
            self._make_btn(
                head,
                "Copy",
                lambda txt=entry["prompt"]: self.copy_text(txt, "Prompt copied to clipboard!"),
                padx=8,
                pady=2,
            ).pack(side="right")

            tk.Label(
                head,
                text=entry["timestamp"],
                bg=COLORS["card"],
                fg=COLORS["muted"],
                font=("Helvetica", 10),
            ).pack(side="right", padx=(0, 10))

            self._render_code_box(card, entry["prompt"])

        def _render_code_box(self, parent, text):
            lines = text.splitlines() or [""]
            height = min(max(len(lines) + 1, 2), 14)
            box = tk.Text(
                parent,
                bg=COLORS["code"],
                fg=COLORS["text"],
                font=("Menlo" if sys.platform == "darwin" else "Courier", 11),
                height=height,
                wrap="word",
                relief="flat",
                padx=10,
                pady=8,
                highlightthickness=1,
                highlightbackground=COLORS["border"],
            )
            box.insert("1.0", text)
            box.configure(state="disabled")
            box.pack(fill="x")

        def pin_prompt(self, project, number):
            tag = simpledialog.askstring(
                "Pin Prompt",
                f"Enter a short tag name for {project} #{number}:",
                initialvalue=f"{project}-{number}",
                parent=self,
            )
            if not tag or not tag.strip():
                return
            center, key = vault.resolve_context()
            vault.cmd_pin(center, key, project, number, tag.strip())
            self.reload_data()
            self.set_status(f"Pinned {project} #{number} as '{tag.strip()}'.")

        def unpin_prompt(self, tag):
            vault.cmd_unpin(tag)
            self.reload_data()
            self.set_status(f"Removed pin '{tag}'.")

        def copy_handoff(self):
            if self.active_view.startswith("__"):
                return
            center, key = vault.resolve_context()
            try:
                name, _, entries = vault.load_project_entries(center, key, self.active_view)
                brief = vault.build_handoff_text(name, entries, last_n=10)
                self.copy_text(
                    brief, f"Copied AI handoff for '{name}' (last {min(10, len(entries))} prompts)!"
                )
            except Exception as exc:
                messagebox.showerror("Handoff Error", str(exc), parent=self)

        def export_active(self):
            if self.active_view.startswith("__"):
                return
            path = filedialog.asksaveasfilename(
                parent=self,
                title=f"Export {self.active_view}",
                initialfile=f"{self.active_view}.html",
                defaultextension=".html",
                filetypes=[
                    ("HTML Report", "*.html"),
                    ("JSON Data", "*.json"),
                    ("Markdown", "*.md"),
                ],
            )
            if not path:
                return
            ext = os.path.splitext(path)[1].lower().lstrip(".")
            fmt = ext if ext in ("html", "json", "md") else "md"
            center, key = vault.resolve_context()
            try:
                vault.cmd_export(center, key, self.active_view, fmt, output_path=path)
                self.set_status(f"Exported '{self.active_view}' -> {path}")
            except Exception as exc:
                messagebox.showerror("Export Error", str(exc), parent=self)

        def track_folder(self):
            folder = filedialog.askdirectory(
                parent=self, title="Select a project folder to track with PromptSave"
            )
            if not folder:
                return
            marker = os.path.join(folder, ".promptsave")
            with open(marker, "w", encoding="utf-8"):
                pass
            self.set_status(f"Now tracking prompts in: {folder}")
            messagebox.showinfo(
                "Project Tracked",
                f"Created `.promptsave` marker in:\n{folder}\n\n"
                "Any prompt you write in Claude Code, Codex, Antigravity, Gemini CLI, or Cursor "
                "inside this folder will now be saved automatically.",
                parent=self,
            )

        def show_stats(self):
            stats = self.snapshot.get("stats", {})
            lines = [
                f"Total projects: {stats.get('total_projects', 0)}",
                f"Total prompts : {stats.get('total_prompts', 0)}",
                "",
                "By AI Tool:",
            ]
            for tool, count in stats.get("by_tool", {}).items():
                lines.append(f"  • {tool}: {count}")
            lines.append("")
            lines.append("By Project:")
            for proj in self.snapshot.get("projects", []):
                lines.append(f"  • {proj['name']}: {proj['count']}")
            messagebox.showinfo("PromptSave Statistics", "\n".join(lines), parent=self)

    app = PromptSaveApp()
    app.mainloop()


def main(argv=None):
    launch_gui()


if __name__ == "__main__":
    main()
