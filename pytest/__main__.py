"""Entry point for the pytest shim."""

from __future__ import annotations

import sys

from . import main


if __name__ == "__main__":
    sys.exit(main())
