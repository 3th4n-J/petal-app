"""Entry point: `python -m petal` / `uv run petal`."""
from pathlib import Path

import flet as ft

from .ui import main

# Project-root assets dir (src/petal/__main__.py -> PT/assets), resolved
# absolutely so it works regardless of the current working directory.
ASSETS_DIR = str(Path(__file__).resolve().parents[2] / "assets")


def run() -> None:
    ft.run(main, assets_dir=ASSETS_DIR)


if __name__ == "__main__":
    run()
