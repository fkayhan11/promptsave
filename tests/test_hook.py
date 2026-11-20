import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK_SCRIPT = os.path.join(REPO_ROOT, "promptsave", "hook.py")
VAULT_SCRIPT = os.path.join(REPO_ROOT, "promptsave", "vault.py")
sys.path.insert(0, os.path.join(REPO_ROOT, "promptsave"))
import crypto  # noqa: E402
import hook  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
