"""Entry point: `python -m petal` / `uv run petal`."""
import flet as ft

from .ui import main


def run() -> None:
    ft.app(target=main)


if __name__ == "__main__":
    run()
