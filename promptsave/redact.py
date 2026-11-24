#!/usr/bin/env python3
"""
Automatic secret redaction for PromptSave.

Scans prompts before saving and replaces accidentally pasted API keys,
tokens, and private keys with safe placeholders like `[REDACTED_API_KEY]`.
Zero external dependencies.
"""
import re

PATTERNS = [
    (
        "PRIVATE_KEY",
        re.compile(
            r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z0-9 ]*PRIVATE KEY-----"
        ),
    ),
    ("OPENAI_KEY", re.compile(r"\bsk-(?:proj-|ant-|live-|test-)?[A-Za-z0-9_-]{20,}\b")),
    ("GITHUB_TOKEN", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b")),
    ("GITHUB_PAT", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("AWS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GOOGLE_API_KEY", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("SLACK_TOKEN", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    (
        "JWT",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ),
    (
        "BEARER_TOKEN",
        re.compile(r"(?i)(Authorization\s*:\s*Bearer\s+)[A-Za-z0-9._\-]{16,}"),
    ),
]


def redact_secrets(text):
    """Return (redacted_text, count_of_redactions)."""
    if not isinstance(text, str) or not text:
        return text, 0
    total = 0
    result = text
    for label, pattern in PATTERNS:
        if label == "BEARER_TOKEN":
            result, n = pattern.subn(r"\1[REDACTED_BEARER_TOKEN]", result)
        else:
            result, n = pattern.subn(f"[REDACTED_{label}]", result)
        total += n
    return result, total
