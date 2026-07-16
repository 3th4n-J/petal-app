"""Flet entry point for `flet run main.py` and `flet build apk`.

Real code lives in the src/petal package.
"""
import flet as ft

from petal.ui import main

if __name__ == "__main__":
    ft.app(target=main)
