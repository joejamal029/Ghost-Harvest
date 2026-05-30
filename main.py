"""
GhostHarvest v2.1 — Entry point.

Requests UAC elevation on Windows, then launches the GUI.
"""

import sys

from ghost_harvest.utils import elevate, is_admin
from ghost_harvest.app import GhostHarvest


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("GhostHarvest runs on Windows only.")
    if not is_admin():
        elevate()
    GhostHarvest().mainloop()


if __name__ == "__main__":
    main()
