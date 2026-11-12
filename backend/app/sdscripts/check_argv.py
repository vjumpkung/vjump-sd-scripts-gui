"""Check that a script's real argparse parser accepts an argument list.

Standalone and stdlib-only; run it with the sd-scripts virtualenv python:

    python check_argv.py --sd-scripts-dir <dir> --script flux_train_network.py < args.json

``args.json`` is a JSON list of strings (the arguments after the script path).
Exit status: 0 when the parser accepts them, 2 with the argparse error otherwise
(1 for import failures).
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import logging
import os
import sys


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sd-scripts-dir", required=True)
    parser.add_argument("--script", required=True)
    options = parser.parse_args(argv)

    arguments = json.load(sys.stdin)
    if not isinstance(arguments, list) or not all(
        isinstance(a, str) for a in arguments
    ):
        print("stdin must be a JSON list of strings", file=sys.stderr)
        return 1

    sys.dont_write_bytecode = True
    sd_dir = os.path.abspath(options.sd_scripts_dir)
    sys.path.insert(0, sd_dir)
    os.chdir(sd_dir)
    logging.disable(logging.CRITICAL)
    module_name = (
        options.script[:-3] if options.script.endswith(".py") else options.script
    )
    try:
        with contextlib.redirect_stdout(sys.stderr):
            module = importlib.import_module(module_name)
            script_parser = module.setup_parser()
    except BaseException as error:  # noqa: BLE001
        if isinstance(error, KeyboardInterrupt):
            raise
        print(f"import failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1

    try:
        script_parser.parse_args(arguments)
    except SystemExit as error:
        # argparse already printed the message to stderr.
        return 0 if error.code in (0, None) else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
