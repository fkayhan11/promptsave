# Contributing to PromptSave

Thank you for your interest in contributing! PromptSave is intentionally kept lightweight, local-first, and dependency-free.

## Guidelines

- **Zero external dependencies:** Keep `hook.py`, `install.py`, and tests strictly within the Python 3.8+ standard library.
- **Never block the host CLI:** `hook.py` must always exit with status code `0`, even on unexpected errors.
- **Cross-platform:** Avoid OS-specific APIs without fallbacks (macOS, Linux, and Windows should all work).
- **Add tests:** Any new CLI integration or bug fix should include a test in `tests/test_hook.py`.

## Running Tests

```bash
python3 -m unittest discover -s tests -v
```

## Submitting a Pull Request

1. Fork the repository and create a feature branch.
2. Make your changes and run the unit test suite.
3. Open a pull request describing what you changed and why.
