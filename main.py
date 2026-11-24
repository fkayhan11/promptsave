#!/usr/bin/env python3
"""
PromptSave Desktop Launcher.

Run:
    python3 main.py            Launch the native dark-mode desktop GUI
    python3 main.py --web      Launch the localhost browser dashboard instead
    python3 main.py --help     Show launcher options
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if os.path.join(ROOT, "promptsave") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "promptsave"))

import gui  # noqa: E402
import web  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Launch the PromptSave Vault desktop GUI (or browser UI with --web)."
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Launch the localhost browser dashboard (`promptsave ui`) instead of the desktop GUI.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8787,
        help="Port for --web mode (default: 8787).",
    )
    args = parser.parse_args(argv)
    if args.web:
        web.main(["--port", str(args.port)])
    else:
        gui.launch_gui()


if __name__ == "__main__":
    main()
