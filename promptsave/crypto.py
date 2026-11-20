#!/usr/bin/env python3
"""
Authenticated local encryption for PromptSave using Python's standard library.

Scheme (PROMPTSAVE-ENC-V1):
  - Key derivation : PBKDF2-HMAC-SHA256 (200,000 iterations, random 16-byte salt)
                     producing 32-byte encryption key + 32-byte MAC key
  - Stream cipher  : SHA-256 counter mode (CTR) with random 16-byte nonce
  - Integrity      : Encrypt-then-MAC using HMAC-SHA256 over (version || salt || nonce || ciphertext)
  - Storage format : ASCII header "PROMPTSAVE-ENC-V1\\n" + base64 payload

Zero external dependencies. Works identically on macOS, Linux, and Windows.
"""
import base64
import hashlib
import hmac
import os
import secrets
import struct

MAGIC = b"PSV1"
HEADER = "PROMPTSAVE-ENC-V1\n"
SALT_LEN = 16
NONCE_LEN = 16
MAC_LEN = 32
PBKDF2_ITERS = 200_000


def generate_key():
    """Generate a cryptographically secure 256-bit hex secret key."""
    return secrets.token_hex(32)


def _derive_keys(secret, salt):
    key_material = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        salt,
        PBKDF2_ITERS,
        dklen=64,
    )
    return key_material[:32], key_material[32:]


def _keystream(enc_key, nonce, length):
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hashlib.sha256(enc_key + nonce + struct.pack(">Q", counter)).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def encrypt_text(plaintext, secret):
    """Encrypt UTF-8 plaintext with `secret` and return an ASCII envelope string."""
    if not secret:
        raise ValueError("Encryption secret key must not be empty.")
    data = plaintext.encode("utf-8")
    salt = secrets.token_bytes(SALT_LEN)
    nonce = secrets.token_bytes(NONCE_LEN)
    enc_key, mac_key = _derive_keys(secret, salt)

    stream = _keystream(enc_key, nonce, len(data))
    ciphertext = bytes(a ^ b for a, b in zip(data, stream))

    body = MAGIC + salt + nonce + ciphertext
    tag = hmac.new(mac_key, body, hashlib.sha256).digest()
    encoded = base64.b64encode(body + tag).decode("ascii")
    return HEADER + encoded + "\n"


def decrypt_text(envelope, secret):
    """Verify MAC and decrypt an ASCII envelope string using `secret`."""
    if not secret:
        raise ValueError("Encryption secret key must not be empty.")
    text = envelope.strip()
    if text.startswith(HEADER.strip()):
        text = text[len(HEADER.strip()):].strip()
    try:
        raw = base64.b64decode(text.encode("ascii"), validate=True)
    except Exception as exc:
        raise ValueError("Corrupted encrypted file (invalid base64).") from exc

    min_len = len(MAGIC) + SALT_LEN + NONCE_LEN + MAC_LEN
    if len(raw) < min_len or not raw.startswith(MAGIC):
        raise ValueError("Invalid PromptSave encrypted file format.")

    body = raw[:-MAC_LEN]
    tag = raw[-MAC_LEN:]
    salt_start = len(MAGIC)
    nonce_start = salt_start + SALT_LEN
    ct_start = nonce_start + NONCE_LEN

    salt = body[salt_start:nonce_start]
    nonce = body[nonce_start:ct_start]
    ciphertext = body[ct_start:]

    enc_key, mac_key = _derive_keys(secret, salt)
    expected_tag = hmac.new(mac_key, body, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("Decryption failed: wrong PROMPTSAVE_KEY or tampered file.")

    stream = _keystream(enc_key, nonce, len(ciphertext))
    plaintext = bytes(a ^ b for a, b in zip(ciphertext, stream))
    return plaintext.decode("utf-8")


def load_env(env_path):
    """Parse a simple KEY=VALUE .env file without external dependencies."""
    values = {}
    if not env_path or not os.path.isfile(env_path):
        return values
    with open(env_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            values[key] = val
    return values
