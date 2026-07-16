"""Entry point: `python -m cycle_tracker` / `uv run cycle-tracker`."""
import flet as ft

from .ui import main


def run() -> None:
    ft.app(target=main)


if __name__ == "__main__":
    run()
