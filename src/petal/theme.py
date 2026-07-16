"""Visual language: soft-pastel palettes with runtime theme switching."""
from __future__ import annotations

import flet as ft

# ---- selectable palettes (soft pastels) --------------------------------
# Each: primary, primary_deep, lilac (nav indicator), accent (FAB),
# bg / bg2 (page gradient), hero (full-bleed gradient), on_hero (ink on hero).
THEMES = {
    "Lavender":  dict(primary="#7C4DFF", primary_deep="#5E35B1", lilac="#B39DDB",
                      accent="#FF80AB", bg="#F6F2FF", bg2="#EDE7FF",
                      hero=["#7C4DFF", "#9575CD", "#B39DDB"], on_hero="#FFFFFF"),
    "Coral":     dict(primary="#FF6F91", primary_deep="#C2185B", lilac="#F8BBD0",
                      accent="#FF8A65", bg="#FFF3F5", bg2="#FFE1E8",
                      hero=["#FF6F91", "#FF8FA3", "#FFC1CC"], on_hero="#FFFFFF"),
    "Teal":      dict(primary="#26A69A", primary_deep="#00796B", lilac="#80CBC4",
                      accent="#4DD0E1", bg="#EFFBF8", bg2="#D7F3EC",
                      hero=["#009688", "#26A69A", "#80CBC4"], on_hero="#FFFFFF"),
    "Baby blue": dict(primary="#5C9DFF", primary_deep="#1976D2", lilac="#90CAF9",
                      accent="#64B5F6", bg="#F0F6FF", bg2="#DCEAFF",
                      hero=["#5C9DFF", "#7FB2FF", "#AECBFF"], on_hero="#FFFFFF"),
    "Storm":     dict(primary="#607D8B", primary_deep="#37474F", lilac="#B0BEC5",
                      accent="#90A4AE", bg="#F4F6F7", bg2="#E3E8EB",
                      hero=["#546E7A", "#607D8B", "#90A4AE"], on_hero="#FFFFFF"),
    "Pale":      dict(primary="#8E8AA8", primary_deep="#5E5A78", lilac="#CFCADF",
                      accent="#B7B2CC", bg="#FFFFFF", bg2="#F3F1F7",
                      hero=["#D9D5E8", "#E9E6F2", "#FBFAFE"], on_hero="#4A4660"),
}

# ---- active palette (mutated by apply_theme) ---------------------------
PRIMARY = PRIMARY_DEEP = LILAC = ACCENT = BG = ON_HERO = ""
_BG2 = ""
_HERO: list[str] = []

# ---- constants shared across all themes --------------------------------
SURFACE = "#FFFFFF"
ON_SURFACE = "#2E2A3F"
MUTED = "#8E86A8"

# semantic cycle colours (kept stable so calendar dots stay legible)
C_PERIOD = "#F06292"
C_PREDICTED = "#F8BBD0"
C_FERTILE = "#B2DFDB"
C_OVULATION = "#4DB6AC"

PHASE_COLORS = {
    "Menstrual": "#F06292", "Follicular": "#9575CD",
    "Ovulation": "#4DB6AC", "Luteal": "#7E57C2",
}


def apply_theme(name: str) -> None:
    global PRIMARY, PRIMARY_DEEP, LILAC, ACCENT, BG, _BG2, _HERO, ON_HERO
    pal = THEMES.get(name, THEMES["Lavender"])
    PRIMARY = pal["primary"]
    PRIMARY_DEEP = pal["primary_deep"]
    LILAC = pal["lilac"]
    ACCENT = pal["accent"]
    BG = pal["bg"]
    _BG2 = pal["bg2"]
    _HERO = pal["hero"]
    ON_HERO = pal["on_hero"]


apply_theme("Lavender")


def alpha(hex_color: str, a: float) -> str:
    """#RRGGBB -> #AARRGGBB for the given 0..1 opacity."""
    return f"#{int(max(0.0, min(1.0, a)) * 255):02X}{hex_color.lstrip('#')}"


def app_theme() -> ft.Theme:
    return ft.Theme(color_scheme_seed=PRIMARY, use_material3=True)


def page_gradient() -> ft.LinearGradient:
    return ft.LinearGradient(begin=ft.alignment.top_center,
                             end=ft.alignment.bottom_center, colors=[BG, _BG2])


def hero_gradient() -> ft.LinearGradient:
    return ft.LinearGradient(begin=ft.alignment.top_left,
                             end=ft.alignment.bottom_right, colors=_HERO)


def card(content: ft.Control, **kw) -> ft.Container:
    return ft.Container(
        content=content, bgcolor=SURFACE, border_radius=sc(22),
        padding=kw.pop("padding", sc(18)),
        shadow=ft.BoxShadow(blur_radius=sc(24), spread_radius=0,
                            color="#1A5E35B1", offset=ft.Offset(0, sc(8))),
        **kw)


def pill(text: str, icon=None, on_click=None, filled: bool = True) -> ft.Control:
    style = ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=sc(30)),
        padding=ft.padding.symmetric(horizontal=sc(24), vertical=sc(18)),
        bgcolor=PRIMARY if filled else SURFACE,
        color="white" if filled else PRIMARY, elevation={"": 0})
    return ft.FilledButton(text=text, icon=icon, on_click=on_click, style=style)


def h1(text: str, color: str = ON_SURFACE) -> ft.Text:
    return ft.Text(text, size=sc(22), weight=ft.FontWeight.BOLD, color=color)


def label(text: str, color: str = MUTED) -> ft.Text:
    return ft.Text(text, size=sc(12), weight=ft.FontWeight.W_600, color=color,
                   style=ft.TextStyle(letter_spacing=0.5))


def obtn_style() -> ft.ButtonStyle:
    """Outlined-button style whose border follows the active theme."""
    return ft.ButtonStyle(side=ft.BorderSide(1.4, PRIMARY), color=PRIMARY,
                          shape=ft.RoundedRectangleBorder(radius=sc(14)))


def fab_gradient() -> ft.LinearGradient:
    """A soft gradient for the add button, drawn from the active theme."""
    return ft.LinearGradient(begin=ft.alignment.top_left,
                             end=ft.alignment.bottom_right, colors=[PRIMARY, ACCENT])


# ---- responsive scaling -------------------------------------------------
# All sizes are authored for a 430px-wide phone; sc() scales them to the
# actual viewport so text, icons and controls grow/shrink together.
BASE_W = 430.0
_MIN_SCALE, _MAX_SCALE = 0.85, 1.35
SCALE = 1.0


def set_scale(width, height=None) -> bool:
    """Recompute the global scale from viewport width. True if it changed."""
    global SCALE
    if not width:
        return False
    s = max(_MIN_SCALE, min(_MAX_SCALE, float(width) / BASE_W))
    if abs(s - SCALE) < 0.01:
        return False
    SCALE = s
    return True


def sc(value: float) -> float:
    """Scale a design size to the current viewport."""
    return round(value * SCALE, 1)
