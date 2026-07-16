"""Flet entry point for `flet run main.py` and `flet build apk`.

Real code lives in the src/cycle_tracker package.
"""
import flet as ft

from cycle_tracker.ui import main

if __name__ == "__main__":
    ft.app(target=main)
