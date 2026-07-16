"""Reusable visual widgets: the cycle ring and the calendar grid."""
from __future__ import annotations

import calendar as _cal
import math
from datetime import date
from typing import Dict, Optional

import flet as ft
import flet.canvas as cv

from . import cycle_stats as cs
from . import theme as T

_TAU = math.pi * 2


def cycle_ring(stats: cs.CycleStats, size: int = 250) -> ft.Control:
    """Flo-style hero ring: track + progress arc with centred cycle info."""
    stroke = 18
    inset = stroke / 2 + 2
    box = size - inset * 2
    start = -math.pi / 2  # 12 o'clock
    ink = T.ON_HERO

    track = cv.Arc(
        x=inset, y=inset, width=box, height=box,
        start_angle=0, sweep_angle=_TAU,
        paint=ft.Paint(style=ft.PaintingStyle.STROKE, stroke_width=stroke,
                       color=T.alpha(ink, 0.28), stroke_cap=ft.StrokeCap.ROUND),
    )
    progress = cv.Arc(
        x=inset, y=inset, width=box, height=box,
        start_angle=start, sweep_angle=_TAU * max(stats.progress, 0.001),
        paint=ft.Paint(style=ft.PaintingStyle.STROKE, stroke_width=stroke,
                       color=ink, stroke_cap=ft.StrokeCap.ROUND),
    )
    ring = cv.Canvas([track, progress], width=size, height=size)

    if stats.cycle_day:
        big = str(stats.cycle_day)
        top = "CYCLE DAY"
        if stats.days_until_next is not None:
            if stats.days_until_next > 0:
                bottom = f"Period in {stats.days_until_next} days"
            elif stats.days_until_next == 0:
                bottom = "Period expected today"
            else:
                bottom = f"Period {abs(stats.days_until_next)} days late"
        else:
            bottom = ""
    else:
        big, top, bottom = "–", "NO DATA", "Log your first period"

    center = ft.Column(
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0,
        controls=[
            ft.Text(top, size=12, color=T.alpha(ink, 0.85), weight=ft.FontWeight.W_600,
                    style=ft.TextStyle(letter_spacing=1.5)),
            ft.Text(big, size=64, color=ink, weight=ft.FontWeight.BOLD),
            ft.Text(bottom, size=14, color=ink, weight=ft.FontWeight.W_500),
        ],
    )
    return ft.Container(
        width=size, height=size,
        content=ft.Stack([ring, ft.Container(center, alignment=ft.alignment.center,
                                             width=size, height=size)]),
    )


def phase_chip(phase: Optional[str]) -> ft.Control:
    if not phase:
        return ft.Container()
    color = T.PHASE_COLORS.get(phase, T.PRIMARY)
    return ft.Container(
        content=ft.Text(f"{phase} phase", color="white", size=13,
                        weight=ft.FontWeight.W_600),
        bgcolor=color, border_radius=20,
        padding=ft.padding.symmetric(horizontal=16, vertical=8),
    )


def stat_tile(value: str, caption: str) -> ft.Control:
    return ft.Container(
        expand=True, padding=14, border_radius=18, bgcolor=T.SURFACE,
        content=ft.Column(spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                          controls=[
                              ft.Text(value, size=22, weight=ft.FontWeight.BOLD,
                                      color=T.PRIMARY_DEEP),
                              ft.Text(caption, size=11, color=T.MUTED),
                          ]),
    )


_LEGEND = [
    (T.C_PERIOD, "Period"),
    (T.C_PREDICTED, "Predicted"),
    (T.C_FERTILE, "Fertile"),
    (T.C_OVULATION, "Ovulation"),
]


def calendar_legend() -> ft.Control:
    dots = []
    for color, name in _LEGEND:
        dots.append(ft.Row(spacing=6, tight=True, controls=[
            ft.Container(width=12, height=12, bgcolor=color, border_radius=6),
            ft.Text(name, size=11, color=T.MUTED),
        ]))
    return ft.Row(dots, alignment=ft.MainAxisAlignment.SPACE_AROUND, wrap=True)


def _day_cell(day: int, cat: Optional[str], is_today: bool) -> ft.Control:
    fill = {
        cs.PERIOD: T.C_PERIOD, cs.PERIOD_PREDICTED: T.C_PREDICTED,
        cs.FERTILE: T.C_FERTILE, cs.OVULATION: T.C_OVULATION,
    }.get(cat)
    dark = cat in (cs.PERIOD, cs.OVULATION)
    txt = ft.Text(str(day), size=13,
                  color="white" if dark and fill else T.ON_SURFACE,
                  weight=ft.FontWeight.BOLD if is_today else ft.FontWeight.W_500)
    return ft.Container(
        width=38, height=38, alignment=ft.alignment.center, content=txt,
        bgcolor=fill, border_radius=19,
        border=ft.border.all(2, T.PRIMARY) if is_today else None,
    )


def calendar_grid(year: int, month: int, day_map: Dict[date, str],
                  today: date) -> ft.Control:
    head = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_AROUND,
        controls=[ft.Container(width=38, alignment=ft.alignment.center,
                               content=ft.Text(d, size=11, color=T.MUTED,
                                               weight=ft.FontWeight.W_600))
                  for d in ["M", "T", "W", "T", "F", "S", "S"]],
    )
    rows = [head]
    for week in _cal.Calendar(firstweekday=0).monthdayscalendar(year, month):
        cells = []
        for dnum in week:
            if dnum == 0:
                cells.append(ft.Container(width=38, height=38))
            else:
                d = date(year, month, dnum)
                cells.append(_day_cell(dnum, day_map.get(d), d == today))
        rows.append(ft.Row(cells, alignment=ft.MainAxisAlignment.SPACE_AROUND))
    return ft.Column(rows, spacing=6)
