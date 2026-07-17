"""Flo-inspired Flet UI: docked-FAB bottom bar over Today, Calendar, Insights, Settings."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import flet as ft

from . import __version__ as APP_VERSION
from . import cycle_stats as cs
from . import theme as T
from . import widgets as W
from .db import Database
from .models import FLOW_LEVELS, MOODS, SYMPTOMS, PeriodEntry
from .seed import SAMPLE


class CycleApp:
    _NAV = [
        (0, ft.Icons.FAVORITE_BORDER, ft.Icons.FAVORITE, "Today"),
        (1, ft.Icons.CALENDAR_MONTH_OUTLINED, ft.Icons.CALENDAR_MONTH, "Calendar"),
        (2, ft.Icons.INSIGHTS_OUTLINED, ft.Icons.INSIGHTS, "Insights"),
        (3, ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS, "Settings"),
    ]

    def __init__(self, page: ft.Page):
        self.page = page
        self.db = Database()
        self.db.purge_expired(30)
        T.apply_theme(self.db.get_setting("theme", "Lavender"))
        self.index = 0
        today = date.today()
        self.cal_year, self.cal_month = today.year, today.month

        page.title = "Petal"
        page.theme = T.app_theme()
        page.bgcolor = T.BG
        page.padding = 0
        try:
            page.window.width, page.window.height = 430, 880
        except Exception:
            pass
        self._mode = "main"
        self._form_entry = None
        T.set_scale(page.width or 430)
        page.on_resize = self._on_resize

        self.body = ft.Container(expand=True, gradient=T.page_gradient())
        page.floating_action_button = self._fab()
        page.floating_action_button_location = \
            ft.FloatingActionButtonLocation.CENTER_DOCKED
        self._switcher = ft.AnimatedSwitcher(
            content=ft.Container(), transition=ft.AnimatedSwitcherTransition.FADE,
            duration=220, reverse_duration=120,
            switch_in_curve=ft.AnimationCurve.EASE_OUT,
            switch_out_curve=ft.AnimationCurve.EASE_IN)
        page.bottom_appbar = self._build_nav()
        page.add(self.body)

        if self.db.has_pin():
            self._show_lock()
        else:
            self.render()

    # ---- bottom app bar (docked FAB notch) -----------------------------
    def _pill_left(self, index: int) -> float:
        slot = (0, 1, 3, 4)[index]          # centre slot (2) is the FAB notch
        center = slot * self._slotW + self._slotW / 2
        return center - self._pill_w / 2

    def _build_nav(self) -> ft.BottomAppBar:
        barW = self.page.width or 430
        self._slotW = barW / 5.0
        self._pill_w = min(self._slotW * 0.82, T.sc(80))
        self._pill_h = T.sc(52)
        bar_h = T.sc(72)
        self._pill_top = (bar_h - self._pill_h) / 2
        # The active "box" is a positioned pill that slides + springs between items.
        self._pill = ft.Container(
            width=self._pill_w, height=self._pill_h, border_radius=T.sc(16),
            bgcolor=T.alpha(T.PRIMARY, 0.16),
            left=self._pill_left(self.index), top=self._pill_top,
            animate_position=ft.Animation(480, ft.AnimationCurve.ELASTIC_OUT),
            animate=ft.Animation(250, ft.AnimationCurve.EASE_OUT))
        self._nav_icons, self._nav_labels, cells = [], [], []
        for i, (idx, icon, sel_icon, lbl) in enumerate(self._NAV):
            active = i == self.index
            ic = ft.Icon(sel_icon if active else icon, size=T.sc(22),
                         color=T.PRIMARY if active else T.MUTED)
            lb = ft.Text(lbl, size=T.sc(11), color=T.PRIMARY if active else T.MUTED,
                         weight=ft.FontWeight.W_600 if active else ft.FontWeight.W_500)
            self._nav_icons.append(ic)
            self._nav_labels.append(lb)
            cells.append(ft.Container(
                width=self._slotW, alignment=ft.Alignment.CENTER,
                on_click=lambda e, k=i: self._select(k),
                content=ft.Column([ic, lb], spacing=2, tight=True,
                                  alignment=ft.MainAxisAlignment.CENTER,
                                  horizontal_alignment=ft.CrossAxisAlignment.CENTER)))
        row = ft.Row(spacing=0, controls=[
            cells[0], cells[1], ft.Container(width=self._slotW), cells[2], cells[3]])
        return ft.BottomAppBar(
            bgcolor=T.SURFACE, shape=ft.CircularRectangleNotchShape(), notch_margin=T.sc(8),
            height=bar_h, padding=0, elevation=24,
            shadow_color=T.alpha(T.PRIMARY_DEEP, 0.65),
            content=ft.Stack([self._pill, row]))

    def _sync_nav(self):
        for i, (idx, icon, sel_icon, lbl) in enumerate(self._NAV):
            active = i == self.index
            self._nav_icons[i].icon = sel_icon if active else icon
            self._nav_icons[i].color = T.PRIMARY if active else T.MUTED
            self._nav_labels[i].color = T.PRIMARY if active else T.MUTED
            self._nav_labels[i].weight = (ft.FontWeight.W_600 if active
                                          else ft.FontWeight.W_500)
        self._pill.left = self._pill_left(self.index)

    def _fab(self) -> ft.FloatingActionButton:
        # FABs only take a solid bgcolor, so the gradient lives in a circular
        # content container while the FAB itself stays transparent (keeps the notch).
        return ft.FloatingActionButton(
            content=ft.Container(
                width=T.sc(56), height=T.sc(56), border_radius=T.sc(28), alignment=ft.Alignment.CENTER,
                gradient=T.fab_gradient(),
                content=ft.Icon(ft.Icons.ADD, color="white", size=T.sc(26))),
            bgcolor="#00000000", elevation=0, shape=ft.CircleBorder(),
            on_click=lambda e: self.open_log())

    def _select(self, i: int):
        self.index = i
        self.render()

    def _on_resize(self, e=None):
        # Recompute scale + slot positions and rebuild the nav/FAB, then the
        # current screen, so everything resizes with the window.
        T.set_scale(self.page.width)
        self.page.bottom_appbar = self._build_nav()
        self.page.floating_action_button = self._fab()
        if self._mode == "lock":
            self._show_lock()
        elif self._mode == "form":
            self.open_log(self._form_entry)
        elif self._mode == "trash":
            self._show_trash()
        else:
            self.render()

    def _chrome(self, show: bool):
        """Show/hide bottom bar + FAB (hidden on the lock screen / log form)."""
        self.page.bottom_appbar.visible = show
        self.page.floating_action_button.visible = show

    def render(self):
        self._mode = "main"
        self.page.appbar = None
        self._chrome(True)
        self.body.gradient = T.hero_gradient() if self.index == 0 else T.page_gradient()
        view = [self._home, self._calendar, self._insights, self._settings][self.index]()
        self._switcher.content = ft.Column([view], scroll=ft.ScrollMode.AUTO, expand=True)
        self.body.content = self._switcher
        self._sync_nav()
        self.page.update()

    def _toast(self, msg: str):
        self.page.show_dialog(ft.SnackBar(ft.Text(msg), bgcolor=T.PRIMARY_DEEP))

    def _defaults(self):
        return (self.db.get_int("default_cycle", cs.DEFAULT_CYCLE_DAYS),
                self.db.get_int("default_period", cs.DEFAULT_PERIOD_DAYS))

    def _stats(self) -> cs.CycleStats:
        dc, dp = self._defaults()
        return cs.compute(self.db.list_all(), default_cycle=dc, default_period=dp)

    def _greeting(self) -> str:
        name = (self.db.get_setting("profile_name") or "").strip()
        who = name.split()[0] if name else "there"
        h = datetime.now().hour
        part = ("Good morning" if h < 12 else
                "Good afternoon" if h < 17 else
                "Good evening" if h < 21 else "Good night")
        return f"{part}, {who}"

    # ---- Today (full-bleed, centered) ----------------------------------
    def _home(self) -> ft.Control:
        s = self._stats()
        today = date.today()

        def fmt(d): return d.strftime("%d %b") if d else "—"
        fertile = "—"
        if s.fertile_start and s.fertile_end:
            fertile = f"{fmt(s.fertile_start)} – {fmt(s.fertile_end)}"

        hero = ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=T.sc(14),
            controls=[
                ft.Text(self._greeting(), size=T.sc(22), color=T.ON_HERO,
                        weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Text(today.strftime("%A, %d %B").upper(), size=T.sc(12),
                        color=T.alpha(T.ON_HERO, 0.85), weight=ft.FontWeight.W_600,
                        style=ft.TextStyle(letter_spacing=1.2)),
                ft.Row([W.cycle_ring(s, size=T.sc(260))],
                       alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([T.pill("Log period", icon=ft.Icons.WATER_DROP,
                               on_click=lambda e: self.open_log(), filled=False)],
                       alignment=ft.MainAxisAlignment.CENTER),
            ],
        )

        insight = T.card(ft.Column(spacing=T.sc(12), controls=[
            ft.Row([W.phase_chip(s.phase)]) if s.phase else ft.Container(),
            self._info_row(ft.Icons.EGG_OUTLINED, T.C_OVULATION, "Ovulation",
                           fmt(s.ovulation_date)),
            self._info_row(ft.Icons.SPA_OUTLINED, T.C_OVULATION, "Fertile window",
                           fertile),
            self._info_row(ft.Icons.EVENT_REPEAT, T.PRIMARY, "Next period",
                           fmt(s.next_predicted)),
        ]))

        tiles = ft.Row(spacing=T.sc(12), controls=[
            W.stat_tile(f"{s.avg_cycle_days or '—'}", "avg cycle (days)"),
            W.stat_tile(f"{s.avg_period_days or '—'}", "avg period (days)"),
            W.stat_tile(f"{s.logged_count}", "cycles logged"),
        ])

        return ft.Container(
            padding=ft.Padding.only(left=T.sc(18), right=T.sc(18), top=T.sc(18), bottom=T.sc(28)),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=T.sc(18), controls=[hero, insight, tiles, self._phase_card(s)]))

    @staticmethod
    def _info_row(icon, icon_color, label, value) -> ft.Control:
        return ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
            ft.Row([ft.Icon(icon, color=icon_color, size=T.sc(20)),
                    ft.Text(label, color=T.MUTED, size=T.sc(13))]),
            ft.Text(value, weight=ft.FontWeight.W_600, color=T.ON_SURFACE)])

    def _phase_card(self, s: cs.CycleStats) -> ft.Control:
        """Current menstrual phase + a hormone fun-fact."""
        if s.phase:
            info = cs.PHASE_INFO.get(s.phase, {})
            color = T.PHASE_COLORS.get(s.phase, T.PRIMARY)
            title = f"{s.phase} phase"
            desc = info.get("desc", "")
            fact = info.get("hormone", "")
            day_txt = f"Day {s.cycle_day}" if s.cycle_day else ""
        else:
            color = T.PRIMARY
            title = "Cycle phase"
            desc = "Log a period to see your current phase."
            fact = cs.GENERAL_FACTS[date.today().day % len(cs.GENERAL_FACTS)]
            day_txt = ""

        return T.card(ft.Column(spacing=T.sc(10), controls=[
            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                T.label("CURRENT PHASE"),
                ft.Text(day_txt, size=T.sc(12), color=T.MUTED) if day_txt else ft.Container(),
            ]),
            ft.Row(spacing=T.sc(10), controls=[
                ft.Container(width=T.sc(14), height=T.sc(14), bgcolor=color, border_radius=T.sc(7)),
                ft.Text(title, size=T.sc(18), weight=ft.FontWeight.BOLD, color=T.ON_SURFACE),
            ]),
            ft.Text(desc, size=T.sc(13), color=T.MUTED) if desc else ft.Container(),
            ft.Divider(height=T.sc(1), color="#EEE"),
            ft.Row(spacing=T.sc(10), vertical_alignment=ft.CrossAxisAlignment.START, controls=[
                ft.Icon(ft.Icons.SCIENCE_OUTLINED, color=color, size=T.sc(20)),
                ft.Column(spacing=T.sc(2), expand=True, controls=[
                    T.label("HORMONE INSIGHT"),
                    ft.Text(fact, size=T.sc(13), color=T.ON_SURFACE),
                ]),
            ]),
        ]))

    # ---- Calendar ------------------------------------------------------
    def _shift_month(self, delta: int):
        m = self.cal_month + delta
        self.cal_year += (m - 1) // 12
        self.cal_month = (m - 1) % 12 + 1
        self.render()

    def _calendar(self) -> ft.Control:
        dc, dp = self._defaults()
        dm = cs.day_map(self.db.list_all(), default_cycle=dc, default_period=dp)
        title = date(self.cal_year, self.cal_month, 1).strftime("%B %Y")
        header = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.IconButton(ft.Icons.CHEVRON_LEFT, icon_color=T.PRIMARY,
                              on_click=lambda e: self._shift_month(-1)),
                ft.Text(title, size=T.sc(18), weight=ft.FontWeight.BOLD, color=T.ON_SURFACE),
                ft.IconButton(ft.Icons.CHEVRON_RIGHT, icon_color=T.PRIMARY,
                              on_click=lambda e: self._shift_month(1)),
            ])
        grid = T.card(ft.Column(spacing=T.sc(14), controls=[
            W.calendar_grid(self.cal_year, self.cal_month, dm, date.today()),
            ft.Divider(height=T.sc(1), color="#EEE"),
            W.calendar_legend(),
        ]))
        return ft.Container(
            padding=ft.Padding.only(left=T.sc(16), right=T.sc(16), top=T.sc(16), bottom=T.sc(24)),
            content=ft.Column(spacing=T.sc(14), controls=[header, grid]))

    # ---- Insights ------------------------------------------------------
    def _insights(self) -> ft.Control:
        s = self._stats()
        entries = self.db.list_all()
        tiles = ft.Row(spacing=T.sc(12), controls=[
            W.stat_tile(f"{s.avg_cycle_days or '—'}", "avg cycle (days)"),
            W.stat_tile(f"{s.avg_period_days or '—'}", "avg period (days)"),
        ])
        tiles2 = ft.Row(spacing=T.sc(12), controls=[
            W.stat_tile(f"{s.cycle_day or '—'}", "current cycle day"),
            W.stat_tile(f"{s.logged_count}", "cycles logged"),
        ])
        history = [ft.Row([T.h1("History"),
                           ft.Text(f"{len(entries)} entries", color=T.MUTED, size=T.sc(12))],
                          alignment=ft.MainAxisAlignment.SPACE_BETWEEN)]
        if entries:
            history += [self._entry_card(e) for e in entries]
        else:
            history.append(ft.Container(
                padding=24, alignment=ft.Alignment.CENTER,
                content=ft.Text("No entries yet — tap + to log a period.",
                                color=T.MUTED)))
        return ft.Container(
            padding=ft.Padding.only(left=T.sc(16), right=T.sc(16), top=T.sc(16), bottom=T.sc(24)),
            content=ft.Column(spacing=T.sc(14), controls=[
                T.h1("Insights"), tiles, tiles2, ft.Container(height=T.sc(4)), *history]))

    def _entry_card(self, entry: PeriodEntry) -> ft.Control:
        rng = entry.start_date.strftime("%d %b %Y")
        if entry.end_date:
            rng += f"  →  {entry.end_date.strftime('%d %b')} · {entry.period_length}d"
        sub = [f"Flow: {entry.flow}"]
        if entry.mood:
            sub.append(entry.mood)
        if entry.symptoms:
            sub.append(", ".join(entry.symptoms))
        return T.card(padding=14, content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=T.sc(12), expand=True, controls=[
                    ft.Container(width=T.sc(8), height=T.sc(42), bgcolor=T.C_PERIOD, border_radius=T.sc(4)),
                    ft.Column(spacing=T.sc(2), expand=True, controls=[
                        ft.Text(rng, weight=ft.FontWeight.BOLD, size=T.sc(15), color=T.ON_SURFACE),
                        ft.Text(" • ".join(sub), size=T.sc(12), color=T.MUTED),
                        *([ft.Text(entry.notes, size=T.sc(12), italic=True,
                                   color=T.MUTED)] if entry.notes else []),
                    ]),
                ]),
                ft.Row(spacing=T.sc(0), controls=[
                    ft.IconButton(ft.Icons.EDIT_OUTLINED, icon_color=T.PRIMARY,
                                  on_click=lambda e, en=entry: self.open_log(en)),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=T.MUTED,
                                  on_click=lambda e, en=entry: self._confirm_delete(en)),
                ]),
            ]))

    def _confirm_delete(self, entry: PeriodEntry):
        def _do(e):
            self.db.delete(entry.id)
            self.page.pop_dialog()
            self._toast("Moved to trash")
            self.render()
        dlg = ft.AlertDialog(
            modal=True, title=ft.Text("Move to trash?"),
            content=ft.Text(f"The period starting "
                            f"{entry.start_date.strftime('%d %b %Y')} moves to Trash "
                            f"and is deleted after 30 days."),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
                     ft.FilledButton("Move to trash", on_click=_do)])
        self.page.show_dialog(dlg)

    # ---- Settings (centered content) -----------------------------------
    @staticmethod
    def _sec_label(text: str) -> ft.Control:
        return ft.Row([T.label(text)], alignment=ft.MainAxisAlignment.CENTER)

    def _settings(self) -> ft.Control:
        C = ft.CrossAxisAlignment.CENTER
        name_tf = ft.TextField(label="Name", border_radius=T.sc(14), border_color=T.PRIMARY,
                               text_align=ft.TextAlign.CENTER,
                               value=self.db.get_setting("profile_name", ""))
        bday = {"d": self._parse_iso(self.db.get_setting("profile_birthday"))}
        bday_btn = ft.OutlinedButton(icon=ft.Icons.CAKE_OUTLINED, style=T.obtn_style())

        def sync_bday():
            bday_btn.content = bday["d"].strftime("%d %b %Y") if bday["d"] else "Not set"
            self.page.update()
        bday_btn.on_click = lambda e: self._pick_date(
            bday["d"] or date(2000, 1, 1), lambda d: (bday.update(d=d), sync_bday()))
        sync_bday()

        dc, dp = self._defaults()
        cyc_tf = ft.TextField(label="Default cycle length (days)", value=str(dc),
                              border_radius=T.sc(14), border_color=T.PRIMARY,
                              text_align=ft.TextAlign.CENTER,
                              input_filter=ft.NumbersOnlyInputFilter())
        per_tf = ft.TextField(label="Default period length (days)", value=str(dp),
                              border_radius=T.sc(14), border_color=T.PRIMARY,
                              text_align=ft.TextAlign.CENTER,
                              input_filter=ft.NumbersOnlyInputFilter())

        def save_prefs(e):
            self.db.set_setting("profile_name", name_tf.value or "")
            if bday["d"]:
                self.db.set_setting("profile_birthday", bday["d"].isoformat())
            self.db.set_setting("default_cycle", max(int(cyc_tf.value or dc), 10))
            self.db.set_setting("default_period", max(int(per_tf.value or dp), 1))
            self._toast("Saved")
            self.render()

        profile = T.card(ft.Column(spacing=T.sc(14), horizontal_alignment=C, controls=[
            self._sec_label("PROFILE"), name_tf,
            ft.Row(alignment=ft.MainAxisAlignment.CENTER,
                   controls=[ft.Text("Birthday", color=T.MUTED), bday_btn]),
        ]))
        prefs = T.card(ft.Column(spacing=T.sc(14), horizontal_alignment=C, controls=[
            self._sec_label("CYCLE PREFERENCES"),
            ft.Text("Used for predictions until you've logged enough history.",
                    size=T.sc(12), color=T.MUTED, text_align=ft.TextAlign.CENTER),
            cyc_tf, per_tf,
        ]))
        save_btn = ft.Row(alignment=ft.MainAxisAlignment.CENTER,
                          controls=[T.pill("Save", icon=ft.Icons.CHECK, on_click=save_prefs)])

        appearance = T.card(ft.Column(spacing=T.sc(12), horizontal_alignment=C, controls=[
            self._sec_label("APPEARANCE"),
            ft.Text("Theme", color=T.ON_SURFACE, weight=ft.FontWeight.W_600,
                    text_align=ft.TextAlign.CENTER),
            ft.Row(wrap=True, spacing=T.sc(16), run_spacing=T.sc(14),
                   alignment=ft.MainAxisAlignment.SPACE_EVENLY,
                   controls=[self._theme_swatch(n) for n in T.THEMES]),
        ]))

        lock = T.card(ft.Column(spacing=T.sc(12), horizontal_alignment=C, controls=[
            self._sec_label("APP LOCK"),
            ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[
                ft.Icon(ft.Icons.LOCK_OUTLINE, color=T.PRIMARY, size=T.sc(20)),
                ft.Text("PIN lock " + ("enabled" if self.db.has_pin() else "off"),
                        color=T.ON_SURFACE, weight=ft.FontWeight.W_600)]),
            ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=T.sc(10), controls=(
                [ft.OutlinedButton("Change PIN", style=T.obtn_style(),
                                   on_click=lambda e: self._pin_dialog(True)),
                 ft.TextButton("Remove PIN", on_click=self._remove_pin)]
                if self.db.has_pin() else
                [T.pill("Set PIN", icon=ft.Icons.PIN, on_click=lambda e: self._pin_dialog())]
            )),
        ]))

        bw = T.sc(210)
        data = T.card(ft.Column(spacing=T.sc(12), horizontal_alignment=C, controls=[
            self._sec_label("DATA"),
            ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[
                ft.OutlinedButton(f"Trash ({len(self.db.list_trash())})",
                                  icon=ft.Icons.DELETE_SWEEP_OUTLINED, width=bw,
                                  style=T.obtn_style(),
                                  on_click=lambda e: self._show_trash())]),
            ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[
                ft.OutlinedButton("Delete all data", icon=ft.Icons.DELETE_FOREVER,
                                  width=bw, style=T.obtn_style(),
                                  on_click=self._confirm_clear_all)]),
            ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[
                ft.OutlinedButton("Reset app", icon=ft.Icons.RESTART_ALT, width=bw,
                                  style=T.obtn_style(), on_click=self._confirm_reset)]),
        ]))

        about = T.card(ft.Column(spacing=T.sc(8), horizontal_alignment=C, controls=[
            self._sec_label("ABOUT"),
            ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=T.sc(10), controls=[
                ft.Icon(ft.Icons.FAVORITE, color=T.C_PERIOD, size=T.sc(22)),
                ft.Column(spacing=T.sc(0), horizontal_alignment=C, controls=[
                    ft.Text("Petal", color=T.ON_SURFACE,
                            weight=ft.FontWeight.BOLD, size=T.sc(15)),
                    ft.Text(f"Version {APP_VERSION}", color=T.MUTED, size=T.sc(12)),
                ]),
            ]),
            ft.Text("A private period and cycle tracker — log periods, symptoms "
                    "and moods, and see your phase, fertile window and next-period "
                    "predictions at a glance. Your data stays on your device.",
                    size=T.sc(13), color=T.MUTED, text_align=ft.TextAlign.CENTER),
        ]))

        return ft.Container(
            padding=ft.Padding.only(left=T.sc(16), right=T.sc(16), top=T.sc(16), bottom=T.sc(24)),
            content=ft.Column(spacing=T.sc(14), controls=[
                ft.Row([T.h1("Settings")], alignment=ft.MainAxisAlignment.CENTER),
                profile, prefs, save_btn, appearance, lock, data, about]))

    def _theme_swatch(self, name: str) -> ft.Control:
        pal = T.THEMES[name]
        active = self.db.get_setting("theme", "Lavender") == name
        return ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=T.sc(4),
            controls=[
                ft.Container(
                    width=T.sc(52), height=T.sc(52), border_radius=T.sc(26),
                    gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT,
                                               end=ft.Alignment.BOTTOM_RIGHT,
                                               colors=pal["hero"]),
                    border=ft.Border.all(3, T.PRIMARY if active else "#00000000"),
                    on_click=lambda e, n=name: self._set_theme(n),
                    content=(ft.Icon(ft.Icons.CHECK, color=pal["on_hero"], size=T.sc(22))
                             if active else None),
                    alignment=ft.Alignment.CENTER),
                ft.Text(name, size=T.sc(11), color=T.MUTED),
            ])

    def _set_theme(self, name: str):
        self.db.set_setting("theme", name)
        T.apply_theme(name)
        self.page.theme = T.app_theme()
        self.page.bgcolor = T.BG
        self.page.bottom_appbar = self._build_nav()
        self.page.floating_action_button = self._fab()
        self.render()

    # ---- PIN / lock ----------------------------------------------------
    def _pin_dialog(self, change: bool = False):
        p1 = ft.TextField(label="Enter PIN", password=True, can_reveal_password=True,
                          keyboard_type=ft.KeyboardType.NUMBER, max_length=6,
                          border_color=T.PRIMARY,
                          input_filter=ft.NumbersOnlyInputFilter(), border_radius=T.sc(14))
        p2 = ft.TextField(label="Confirm PIN", password=True, can_reveal_password=True,
                          keyboard_type=ft.KeyboardType.NUMBER, max_length=6,
                          border_color=T.PRIMARY,
                          input_filter=ft.NumbersOnlyInputFilter(), border_radius=T.sc(14))
        err = ft.Text("", color=T.C_PERIOD, size=T.sc(12), visible=False)

        def _save(e):
            v = p1.value or ""
            if len(v) < 4:
                err.value, err.visible = "PIN must be at least 4 digits.", True
                self.page.update(); return
            if v != (p2.value or ""):
                err.value, err.visible = "PINs don't match.", True
                self.page.update(); return
            self.db.set_pin(v)
            self.page.pop_dialog()
            self._toast("PIN updated")
            self.render()

        dlg = ft.AlertDialog(
            modal=True, title=ft.Text("Change PIN" if change else "Set PIN"),
            content=ft.Column([p1, p2, err], tight=True, spacing=T.sc(12), width=T.sc(300)),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
                     ft.FilledButton("Save", on_click=_save)])
        self.page.show_dialog(dlg)

    def _remove_pin(self, e):
        def _do(ev):
            self.db.clear_pin()
            self.page.pop_dialog()
            self._toast("PIN removed")
            self.render()
        dlg = ft.AlertDialog(
            modal=True, title=ft.Text("Remove PIN?"),
            content=ft.Text("The app will no longer be locked."),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
                     ft.FilledButton("Remove", on_click=_do)])
        self.page.show_dialog(dlg)

    def _show_lock(self):
        self._mode = "lock"
        self._chrome(False)
        self.page.appbar = None
        self.body.gradient = T.hero_gradient()
        pin_tf = ft.TextField(
            password=True, can_reveal_password=True, width=T.sc(220),
            text_align=ft.TextAlign.CENTER, keyboard_type=ft.KeyboardType.NUMBER,
            max_length=6, input_filter=ft.NumbersOnlyInputFilter(),
            border_color=T.ON_HERO, color=T.ON_HERO,
            hint_text="PIN", hint_style=ft.TextStyle(color=T.alpha(T.ON_HERO, 0.7)))
        err = ft.Text("", color="#FFCDD2", size=T.sc(13), visible=False)

        def unlock(e=None):
            if self.db.check_pin(pin_tf.value or ""):
                self.render()
            else:
                err.value, err.visible = "Incorrect PIN", True
                pin_tf.value = ""
                self.page.update()
        pin_tf.on_submit = unlock

        self.body.content = ft.Container(
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=T.sc(18),
                controls=[
                    ft.Icon(ft.Icons.LOCK, color=T.ON_HERO, size=T.sc(48)),
                    ft.Text("Enter your PIN", color=T.ON_HERO, size=T.sc(20),
                            weight=ft.FontWeight.BOLD),
                    pin_tf, err,
                    T.pill("Unlock", icon=ft.Icons.LOCK_OPEN, on_click=unlock,
                           filled=False),
                ]))
        self.page.update()

    # ---- data actions --------------------------------------------------
    def _load_sample(self, e):
        from datetime import timedelta
        if self.db.list_all():
            self._toast("Sample data skipped — entries already exist")
            return
        today = date.today()
        for days_ago, length, flow, mood, symptoms, notes in SAMPLE:
            start = today - timedelta(days=days_ago)
            self.db.add(PeriodEntry(start_date=start,
                                    end_date=start + timedelta(days=length - 1),
                                    flow=flow, mood=mood, symptoms=symptoms, notes=notes))
        self._toast("Sample data loaded")
        self.render()

    def _confirm_clear_all(self, e):
        def _do(ev):
            self.db.clear_entries()
            self.page.pop_dialog()
            self._toast("All entries deleted")
            self.render()
        dlg = ft.AlertDialog(
            modal=True, title=ft.Text("Delete all data?"),
            content=ft.Text("This permanently removes every logged period."),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
                     ft.FilledButton("Delete all", on_click=_do)])
        self.page.show_dialog(dlg)

    def _confirm_reset(self, e):
        def _do(ev):
            self.db.clear_entries()
            self.db.clear_settings()
            T.apply_theme("Lavender")
            self.index = 0
            today = date.today()
            self.cal_year, self.cal_month = today.year, today.month
            self.page.theme = T.app_theme()
            self.page.bgcolor = T.BG
            self.page.bottom_appbar = self._build_nav()
            self.page.floating_action_button = self._fab()
            self.page.pop_dialog()
            self._toast("App reset to defaults")
            self.render()
        dlg = ft.AlertDialog(
            modal=True, title=ft.Text("Reset app?"),
            content=ft.Text("This clears all logged data and restores default "
                            "settings, theme and PIN. This can't be undone."),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
                     ft.FilledButton("Reset", on_click=_do)])
        self.page.show_dialog(dlg)

    @staticmethod
    def _parse_iso(s: Optional[str]) -> Optional[date]:
        return date.fromisoformat(s) if s else None

    def _pick_date(self, current: Optional[date], on_pick):
        dp = ft.DatePicker(
            first_date=date(1950, 1, 1), last_date=date(2100, 12, 31),
            value=datetime(current.year, current.month, current.day) if current else None)

        def _ch(e):
            if dp.value:
                on_pick(dp.value.date() if hasattr(dp.value, "date") else dp.value)
        dp.on_change = _ch
        self.page.show_dialog(dp)

    # ---- trash ---------------------------------------------------------
    def _show_trash(self):
        self._mode = "trash"
        self.db.purge_expired(30)
        self._chrome(False)
        self.body.gradient = T.page_gradient()
        trash = self.db.list_trash()
        if trash:
            items = [self._trash_card(e) for e in trash]
        else:
            items = [ft.Container(padding=T.sc(24), alignment=ft.Alignment.CENTER,
                                  content=ft.Text("Trash is empty.", color=T.MUTED))]
        header = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
            ft.Text("Items are permanently deleted after 30 days.",
                    size=T.sc(12), color=T.MUTED),
            (ft.TextButton("Empty trash", icon=ft.Icons.DELETE_FOREVER,
                           on_click=self._confirm_empty_trash) if trash else ft.Container()),
        ])
        col = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=T.sc(12),
                        controls=[header, *items])
        self.page.appbar = ft.AppBar(
            title=ft.Text("Trash"), bgcolor=T.PRIMARY, color="white",
            leading=ft.IconButton(ft.Icons.ARROW_BACK, icon_color="white",
                                  on_click=lambda e: self._back_to_settings()))
        self.body.content = ft.Container(col, padding=T.sc(16), expand=True)
        self.page.update()

    def _back_to_settings(self):
        self.index = 3
        self.render()

    def _trash_card(self, entry: PeriodEntry) -> ft.Control:
        days_left = 30
        if entry.deleted_at:
            days_left = max(0, 30 - (datetime.now() - entry.deleted_at).days)
        rng = entry.start_date.strftime("%d %b %Y")
        if entry.end_date:
            rng += f"  ->  {entry.end_date.strftime('%d %b')}"
        return T.card(padding=T.sc(14), content=ft.Column(spacing=T.sc(8), controls=[
            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Text(rng, weight=ft.FontWeight.BOLD, size=T.sc(15),
                        color=T.ON_SURFACE),
                ft.Text(f"{days_left}d left", size=T.sc(12), color=T.MUTED)]),
            ft.Row(alignment=ft.MainAxisAlignment.END, spacing=T.sc(6), controls=[
                ft.TextButton("Restore", icon=ft.Icons.RESTORE,
                              on_click=lambda e, en=entry: self._restore(en)),
                ft.TextButton("Delete forever", icon=ft.Icons.DELETE_FOREVER,
                              on_click=lambda e, en=entry: self._confirm_hard_delete(en)),
            ]),
        ]))

    def _restore(self, entry: PeriodEntry):
        self.db.restore(entry.id)
        self._toast("Restored")
        self._show_trash()

    def _confirm_hard_delete(self, entry: PeriodEntry):
        def _do(ev):
            self.db.hard_delete(entry.id)
            self.page.pop_dialog()
            self._toast("Deleted permanently")
            self._show_trash()
        dlg = ft.AlertDialog(
            modal=True, title=ft.Text("Delete forever?"),
            content=ft.Text("This entry will be permanently deleted. This can't be undone."),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
                     ft.FilledButton("Delete forever", on_click=_do)])
        self.page.show_dialog(dlg)

    def _confirm_empty_trash(self, e):
        def _do(ev):
            self.db.empty_trash()
            self.page.pop_dialog()
            self._toast("Trash emptied")
            self._show_trash()
        dlg = ft.AlertDialog(
            modal=True, title=ft.Text("Empty trash?"),
            content=ft.Text("Permanently delete everything in Trash. This can't be undone."),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
                     ft.FilledButton("Empty trash", on_click=_do)])
        self.page.show_dialog(dlg)

    # ---- log form ------------------------------------------------------
    def open_log(self, entry: Optional[PeriodEntry] = None):
        editing = entry is not None
        self._mode = "form"
        self._form_entry = entry
        st = {"start": entry.start_date if editing else date.today(),
              "end": entry.end_date if editing else None}

        start_btn = ft.OutlinedButton(icon=ft.Icons.CALENDAR_MONTH, style=T.obtn_style())
        end_btn = ft.OutlinedButton(icon=ft.Icons.CALENDAR_MONTH, style=T.obtn_style())

        def sync():
            start_btn.content = st["start"].strftime("%d %b %Y")
            end_btn.content = st["end"].strftime("%d %b %Y") if st["end"] else "Not set"
            self.page.update()

        start_btn.on_click = lambda e: self._pick_date(
            st["start"], lambda d: (st.update(start=d), sync()))
        end_btn.on_click = lambda e: self._pick_date(
            st["end"] or st["start"], lambda d: (st.update(end=d), sync()))

        flow_dd = ft.Dropdown(label="Flow", value=entry.flow if editing else "Medium",
                              options=[ft.dropdown.Option(f) for f in FLOW_LEVELS],
                              border_radius=T.sc(14), border_color=T.PRIMARY)
        mood_dd = ft.Dropdown(label="Mood", value=entry.mood if editing else "",
                              options=[ft.dropdown.Option(key="", text="— None —")] +
                              [ft.dropdown.Option(m) for m in MOODS],
                              border_radius=T.sc(14), border_color=T.PRIMARY)
        notes_tf = ft.TextField(label="Notes", multiline=True, min_lines=2, max_lines=4,
                                border_radius=T.sc(14), border_color=T.PRIMARY,
                                value=entry.notes if editing else "")

        selected = set(entry.symptoms) if editing else set()
        chips = []
        for name in SYMPTOMS:
            def _tog(e, n=name):
                selected.add(n) if e.control.selected else selected.discard(n)
            chips.append(ft.Chip(label=ft.Text(name), selected=name in selected,
                                 selected_color=T.LILAC, on_select=_tog))

        err = ft.Text("", color=T.C_PERIOD, visible=False)

        def save(e):
            if st["end"] and st["end"] < st["start"]:
                err.value, err.visible = "End date can't be before start date.", True
                self.page.update(); return
            data = PeriodEntry(
                id=entry.id if editing else None, start_date=st["start"],
                end_date=st["end"], flow=flow_dd.value or "Medium",
                mood=mood_dd.value or "", symptoms=sorted(selected),
                notes=notes_tf.value or "")
            try:
                self.db.update(data) if editing else self.db.add(data)
            except Exception as ex:
                err.value, err.visible = f"Could not save: {ex}", True
                self.page.update(); return
            self.render()

        form = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=T.sc(16),
                         horizontal_alignment=ft.CrossAxisAlignment.STRETCH, controls=[
            T.card(ft.Column(spacing=T.sc(14), controls=[
                ft.Row([ft.Text("Start", width=T.sc(70), color=T.MUTED), start_btn]),
                ft.Row([ft.Text("End", width=T.sc(70), color=T.MUTED), end_btn,
                        ft.TextButton("Clear",
                                      on_click=lambda e: (st.update(end=None), sync()))]),
            ])),
            T.card(ft.Column(spacing=T.sc(14), controls=[flow_dd, mood_dd])),
            T.card(ft.Column(spacing=T.sc(10), controls=[
                T.label("SYMPTOMS"),
                ft.Row(chips, wrap=True, spacing=T.sc(6), run_spacing=T.sc(6))])),
            T.card(notes_tf), err,
            ft.Row(alignment=ft.MainAxisAlignment.END, controls=[
                ft.TextButton("Cancel", on_click=lambda e: self.render()),
                T.pill("Save", icon=ft.Icons.CHECK, on_click=save)]),
        ])
        sync()

        self._chrome(False)
        self.body.gradient = T.page_gradient()
        self.page.appbar = ft.AppBar(
            title=ft.Text("Edit entry" if editing else "Log period"),
            bgcolor=T.PRIMARY, color="white",
            leading=ft.IconButton(ft.Icons.CLOSE, icon_color="white",
                                  on_click=lambda e: self._close_form()))
        self.body.content = ft.Container(form, padding=16, expand=True)
        self.page.update()

    def _close_form(self):
        self.page.appbar = None
        self.render()


def main(page: ft.Page):
    CycleApp(page)
