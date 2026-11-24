import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK_SCRIPT = os.path.join(REPO_ROOT, "promptsave", "hook.py")
VAULT_SCRIPT = os.path.join(REPO_ROOT, "promptsave", "vault.py")
CLI_SCRIPT = os.path.join(REPO_ROOT, "promptsave", "cli.py")
sys.path.insert(0, os.path.join(REPO_ROOT, "promptsave"))
import crypto  # noqa: E402
import hook  # noqa: E402
import redact  # noqa: E402
import web  # noqa: E402


class TestCrypto(unittest.TestCase):
    def test_encrypt_decrypt_roundtrip(self):
        key = crypto.generate_key()
        secret_msg = "Build a secure auth flow with UTF-8: şğıöüç 🚀"
        enc = crypto.encrypt_text(secret_msg, key)
        self.assertTrue(enc.startswith("PROMPTSAVE-ENC-V1\n"))
        self.assertNotIn("secure auth flow", enc)
        self.assertEqual(crypto.decrypt_text(enc, key), secret_msg)

    def test_wrong_key_fails(self):
        enc = crypto.encrypt_text("top secret prompt", crypto.generate_key())
        with self.assertRaises(ValueError):
            crypto.decrypt_text(enc, crypto.generate_key())

    def test_tampered_ciphertext_fails(self):
        key = crypto.generate_key()
        enc = crypto.encrypt_text("do not tamper", key)
        lines = enc.splitlines()
        payload = lines[1]
        tampered_char = "A" if payload[10] != "A" else "B"
        tampered = lines[0] + "\n" + payload[:10] + tampered_char + payload[11:] + "\n"
        with self.assertRaises(ValueError):
            crypto.decrypt_text(tampered, key)


class TestPromptSaveHook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.state_dir = os.path.join(self.root, "state")
        self.repo_dir = os.path.join(self.root, "promptsave-repo")
        self.center_dir = os.path.join(self.repo_dir, "projects")
        os.makedirs(self.state_dir, exist_ok=True)
        os.makedirs(self.center_dir, exist_ok=True)
        with open(os.path.join(self.state_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"center": self.center_dir}, f)

        self.secret_key = crypto.generate_key()
        self.write_env(encrypt=True, key=self.secret_key)

        self.env = os.environ.copy()
        self.env["PROMPTSAVE_HOME"] = self.state_dir
        self.env.pop("PROMPTSAVE_KEY", None)
        self.env.pop("PROMPTSAVE_ENCRYPT", None)

    def tearDown(self):
        self.tmp.cleanup()

    def write_env(self, encrypt=True, key=""):
        with open(os.path.join(self.repo_dir, ".env"), "w", encoding="utf-8") as f:
            f.write(f"PROMPTSAVE_KEY={key}\n")
            f.write(f"PROMPTSAVE_ENCRYPT={'true' if encrypt else 'false'}\n")

    def read_text(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def run_hook(self, tool, payload):
        proc = subprocess.run(
            [sys.executable, HOOK_SCRIPT, tool],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def run_vault(self, *args):
        return subprocess.run(
            [sys.executable, VAULT_SCRIPT, *args],
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )

    def make_project(self, name, variant="promptsave"):
        proj = os.path.join(self.root, name)
        if variant == "promptsave":
            marker_dir = os.path.join(proj, "promptsave")
        elif variant == "repo_copy":
            marker_dir = os.path.join(proj, "PromptSave copy", "promptsave")
        elif variant == "renamed_copy":
            marker_dir = os.path.join(proj, "promptsave copy")
        else:
            marker_dir = proj
        os.makedirs(marker_dir, exist_ok=True)
        with open(os.path.join(marker_dir, ".promptsave"), "w", encoding="utf-8"):
            pass
        return proj

    def test_encrypted_claude_codex_and_vault_cli(self):
        proj = self.make_project("finance-app")
        self.run_hook("claude", {"prompt": "Create a pivot table", "cwd": proj})
        self.run_hook("codex", {"prompt": "Add a bar chart", "cwd": proj})

        enc_path = os.path.join(self.center_dir, "finance-app.md.enc")
        plain_path = os.path.join(self.center_dir, "finance-app.md")
        self.assertTrue(os.path.isfile(enc_path))
        self.assertFalse(os.path.exists(plain_path))

        raw_enc = self.read_text(enc_path)
        self.assertNotIn("Create a pivot table", raw_enc)
        self.assertNotIn("Add a bar chart", raw_enc)

        # Vault view decrypts cleanly
        res = self.run_vault("view", "finance-app")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("## 1. Claude Code", res.stdout)
        self.assertIn("Create a pivot table", res.stdout)
        self.assertIn("## 2. Codex", res.stdout)
        self.assertIn("Add a bar chart", res.stdout)

        # Vault unlock -> lock lifecycle
        self.assertEqual(self.run_vault("unlock").returncode, 0)
        self.assertTrue(os.path.isfile(plain_path))
        self.assertEqual(self.run_vault("lock").returncode, 0)
        self.assertFalse(os.path.exists(plain_path))
        self.assertTrue(os.path.isfile(enc_path))

        summary_path = os.path.join(self.repo_dir, "summary", "README.md")
        self.assertTrue(os.path.isfile(summary_path))
        summary = self.read_text(summary_path)
        self.assertIn("`finance-app`", summary)
        self.assertIn("| 2 |", summary)

    def test_plaintext_mode_and_subfolder_cwd(self):
        self.write_env(encrypt=False, key=self.secret_key)
        proj = self.make_project("test-app", variant="repo_copy")
        sub = os.path.join(proj, "src", "components")
        os.makedirs(sub, exist_ok=True)

        out = self.run_hook(
            "antigravity",
            {
                "lastUserInput": "<USER_REQUEST>\nFix navbar alignment\n</USER_REQUEST>",
                "conversationId": "conv-1",
                "cwd": sub,
            },
        )
        self.assertEqual(out.strip(), "{}")
        md_path = os.path.join(self.center_dir, "test-app.md")
        self.assertTrue(os.path.isfile(md_path))
        content = self.read_text(md_path)
        self.assertIn("Fix navbar alignment", content)
        self.assertNotIn("<USER_REQUEST>", content)

    def test_antigravity_deduplication(self):
        self.write_env(encrypt=False, key="")
        proj = self.make_project("dedup-app", variant="renamed_copy")
        transcript = os.path.join(self.root, "transcript.jsonl")
        with open(transcript, "w", encoding="utf-8") as f:
            f.write('{"step_index": 5, "type": "USER_INPUT"}\n')

        payload = {
            "lastUserInput": "<USER_REQUEST>Run tests</USER_REQUEST>",
            "conversationId": "conv-dup",
            "transcriptPath": transcript,
            "cwd": proj,
        }
        self.run_hook("antigravity", payload)
        self.run_hook("antigravity", payload)

        with open(transcript, "a", encoding="utf-8") as f:
            f.write('{"step_index": 9, "type": "USER_INPUT"}\n')
        self.run_hook("antigravity", payload)

        content = self.read_text(os.path.join(self.center_dir, "dedup-app.md"))
        self.assertIn("## 1. Antigravity", content)
        self.assertIn("## 2. Antigravity", content)
        self.assertNotIn("## 3.", content)

    def test_untracked_project_is_ignored(self):
        untracked = os.path.join(self.root, "untracked")
        os.makedirs(untracked, exist_ok=True)
        self.run_hook("claude", {"prompt": "Should not be logged", "cwd": untracked})
        self.assertEqual(os.listdir(self.center_dir), [])

    def test_duplicate_project_names_and_backtick_fencing(self):
        self.write_env(encrypt=False, key="")
        p1 = self.make_project(os.path.join("a", "webapp"))
        p2 = self.make_project(os.path.join("b", "webapp"))
        self.run_hook("claude", {"prompt": "```python\nprint(1)\n```", "cwd": p1})
        self.run_hook("codex", {"prompt": "Second webapp", "cwd": p2})

        self.assertTrue(os.path.isfile(os.path.join(self.center_dir, "webapp.md")))
        self.assertTrue(os.path.isfile(os.path.join(self.center_dir, "webapp (2).md")))
        content = self.read_text(os.path.join(self.center_dir, "webapp.md"))
        self.assertIn("````text", content)

    def test_code_fence_helper(self):
        self.assertEqual(hook.code_fence_for("plain text"), "```")
        self.assertEqual(hook.code_fence_for("```code```"), "````")
        self.assertEqual(hook.code_fence_for("````code````"), "`````")

    def test_gemini_and_cursor_with_bom_and_search_stats_export(self):
        proj = self.make_project("ml-lab")

        # Gemini CLI hook expects {"decision": "allow"}
        g_out = self.run_hook("gemini", {"prompt": "Train a random forest model", "cwd": proj})
        self.assertEqual(json.loads(g_out), {"decision": "allow"})

        # Cursor hook with UTF-8 BOM expects {"continue": true}
        bom_payload = "\ufeff" + json.dumps(
            {"prompt": "Plot ROC curve in matplotlib", "workspace_roots": [proj]}
        )
        proc = subprocess.run(
            [sys.executable, HOOK_SCRIPT, "cursor"],
            input=bom_payload,
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {"continue": True})

        # Search across encrypted vault
        s_res = self.run_vault("search", "random forest", "--tool", "gemini")
        self.assertEqual(s_res.returncode, 0, s_res.stderr)
        self.assertIn("ml-lab #1", s_res.stdout)
        self.assertIn("Found 1 matching prompt(s).", s_res.stdout)

        # Stats
        st_res = self.run_vault("stats")
        self.assertEqual(st_res.returncode, 0, st_res.stderr)
        self.assertIn("Total prompts  : 2", st_res.stdout)
        self.assertIn("Gemini CLI", st_res.stdout)
        self.assertIn("Cursor", st_res.stdout)

        # Export JSON and HTML
        json_out = os.path.join(self.root, "export.json")
        html_out = os.path.join(self.root, "export.html")
        self.assertEqual(
            self.run_vault("export", "ml-lab", "--format", "json", "--output", json_out).returncode,
            0,
        )
        exported = json.loads(self.read_text(json_out))
        self.assertEqual(exported["project"], "ml-lab")
        self.assertEqual(len(exported["prompts"]), 2)

        self.assertEqual(
            self.run_vault("export", "ml-lab", "--format", "html", "--output", html_out).returncode,
            0,
        )
        self.assertIn("Plot ROC curve in matplotlib", self.read_text(html_out))

    def test_cli_init_command(self):
        new_proj = os.path.join(self.root, "cli-init-project")
        os.makedirs(new_proj, exist_ok=True)
        proc = subprocess.run(
            [sys.executable, CLI_SCRIPT, "init", new_proj],
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.isfile(os.path.join(new_proj, ".promptsave")))
        self.run_hook("claude", {"prompt": "Initialized via CLI", "cwd": new_proj})
        self.assertTrue(os.path.isfile(os.path.join(self.center_dir, "cli-init-project.md.enc")))

    def test_secret_redaction(self):
        sample = (
            "Use key sk-proj-abcdefghijklmnopqrstuvwxyz123456 and "
            "ghp_1234567890abcdefghijklmnopqrstuv and AKIAIOSFODNN7EXAMPLE"
        )
        cleaned, count = redact.redact_secrets(sample)
        self.assertEqual(count, 3)
        self.assertNotIn("sk-proj-", cleaned)
        self.assertNotIn("ghp_", cleaned)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", cleaned)
        self.assertIn("[REDACTED_OPENAI_KEY]", cleaned)
        self.assertIn("[REDACTED_GITHUB_TOKEN]", cleaned)
        self.assertIn("[REDACTED_AWS_KEY]", cleaned)

    def test_git_context_handoff_pins_and_web_snapshot(self):
        proj = self.make_project("shop-api")
        # Simulate a minimal .git repo with branch feat/auth @ abc1234
        git_refs = os.path.join(proj, ".git", "refs", "heads", "feat")
        os.makedirs(git_refs, exist_ok=True)
        with open(os.path.join(proj, ".git", "HEAD"), "w", encoding="utf-8") as f:
            f.write("ref: refs/heads/feat/auth\n")
        with open(os.path.join(git_refs, "auth"), "w", encoding="utf-8") as f:
            f.write("abc1234567890abcdef1234567890abcdef12345\n")

        self.run_hook(
            "claude",
            {
                "prompt": "Fix login with token ghp_1234567890abcdefghijklmnopqrstuv",
                "cwd": proj,
            },
        )
        self.run_hook("codex", {"prompt": "Add rate limiting middleware", "cwd": proj})

        # Verify Git context & secret redaction in decrypted view
        view_res = self.run_vault("view", "shop-api")
        self.assertEqual(view_res.returncode, 0, view_res.stderr)
        self.assertIn("feat/auth @ abc1234", view_res.stdout)
        self.assertIn("[REDACTED_GITHUB_TOKEN]", view_res.stdout)
        self.assertNotIn("ghp_1234567890", view_res.stdout)

        # Verify handoff output
        h_res = self.run_vault("handoff", "shop-api", "--last", "2", "--no-copy")
        self.assertEqual(h_res.returncode, 0, h_res.stderr)
        self.assertIn("# Context Handoff — shop-api", h_res.stdout)
        self.assertIn("Add rate limiting middleware", h_res.stdout)

        # Verify pin -> pins -> copy -> unpin
        self.assertEqual(
            self.run_vault("pin", "shop-api", "2", "--tag", "ratelimit").returncode, 0
        )
        pins_res = self.run_vault("pins")
        self.assertIn("[ratelimit]", pins_res.stdout)
        copy_res = self.run_vault("copy", "ratelimit", "--no-copy")
        self.assertIn("Add rate limiting middleware", copy_res.stdout)
        self.assertEqual(self.run_vault("unpin", "ratelimit").returncode, 0)

        # Verify local Web UI snapshot API
        old_home = os.environ.get("PROMPTSAVE_HOME")
        os.environ["PROMPTSAVE_HOME"] = self.state_dir
        try:
            snap = web.build_vault_snapshot()
        finally:
            if old_home is None:
                os.environ.pop("PROMPTSAVE_HOME", None)
            else:
                os.environ["PROMPTSAVE_HOME"] = old_home
        self.assertEqual(snap["stats"]["total_prompts"], 2)
        self.assertEqual(snap["projects"][0]["name"], "shop-api")
        self.assertEqual(snap["projects"][0]["entries"][0]["git"], "feat/auth @ abc1234")


if __name__ == "__main__":
    unittest.main()
