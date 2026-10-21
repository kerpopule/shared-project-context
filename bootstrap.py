#!/usr/bin/env python3
"""One-command local setup, with no pip or server requirement."""

from shared_context.__main__ import main
import sys

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.append("setup")
    raise SystemExit(main())
