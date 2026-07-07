#!/usr/bin/env python3
"""Moby — thin entrypoint shim.

The implementation lives in the moby/ package (which shadows this file on
import — `import moby` resolves to the package). This shim exists so the
GitHub Actions workflow command stays `python moby.py`.
"""
import sys

from moby.pipeline import main

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 — fail loudly in CI logs, no alert spam
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
