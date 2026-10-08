#!/usr/bin/env python3
"""Deprecated compatibility entry for existing CNKI-Paper commands."""

from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

from avereth_core import cli as _cli


if __name__ == "__main__":
    raise SystemExit(_cli.main())

# Existing Python integrations historically imported this module and patched
# controller helpers in-place.  Returning the canonical module preserves that
# narrow compatibility without retaining a second implementation.
sys.modules[__name__] = _cli
