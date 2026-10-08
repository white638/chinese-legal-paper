#!/usr/bin/env python3
"""Public CLI for the CNKI-Paper local research engine."""

import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

from avereth_core.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
