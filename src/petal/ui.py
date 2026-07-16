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
        T.apply_theme(self.db.get_setting("theme", "Lavender"))
        self.index = 0
        today = date.today()
        self.cal_year, self.cal_month = today.year, today.month

        page.title = "Petal"
        page.theme = T.app_theme()
        page.bgcolor = T.BG
        page.padding = 0
        page.window_width, page.window_height = 430, 880

        self.body = ft.Container(expand=True, gradient=T.page_gradient())
        page.floating_action_button = ft.FloatingActionButton(
            icon=ft.Icons.ADD, bgcolor=T.ACCENT, foreground_color="white",
            shape=ft.CircleBorder(), on_click=lambda e: self.open_log())
        page.floating_action_button_location = \
            ft.FloatingActionButtonLocation.CENTER_DOCKED
        page.bottom_appbar = self._bottom_bar()
        page.add(self.body)

        if self.db.has_pin():
            self._show_lock()
        else:
            self.render()

    # ---- bottom app bar (docked FAB notch) -----------------------------
    def _nav_item(self, idx, icon, sel_icon, lbl) -> ft.Control:
        active = self.index == idx
        return ft.Container(
            on_click=lambda e, i=idx: self._select(i),
            border_radius=16, padding=ft.padding.symmetric(horizontal=14, vertical=6),
            bgcolor=T.alpha(T.PRIMARY, 0.14) if active else None,
            content=ft.Column(
                spacing=2, tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(sel_icon if active else icon,
                            color=T.PRIMARY if active else T.MUTED, size=22),
                    ft.Text(lbl, size=11, color=T.PRIMARY if active else T.MUTED,
                            weight=ft.FontWeight.W_600 if active else ft.FontWeight.W_500),
                ]))

    def _bottom_bar(self) -> ft.BottomAppBar:
        items = [self._nav_item(*n) for n in self._NAV]
        return ft.BottomAppBar(
            bgcolor=T.SURFACE, shape=ft.NotchShape.CIRCULAR, notch_margin=8,
            height=72, padding=ft.padding.symmetric(horizontal=10),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(items[:2], spacing=4),
                    ft.Container(width=52),  # gap for the docked FAB notch
                    ft.Row(items[2:], spacing=4),
                ]))

    def _select(self, i: int):
        self.index = i
        self.render()

    def _chrome(self, show: bool):
        """Show/hide bottom bar + FAB (hidden on the lock screen / log form)."""
        self.page.bottom_appbar.visible = show
        self.page.floating_action_button.visible = show

    def render(self):
        self.page.appbar = None
        self.page.bottom_appbar = self._bottom_bar()
        self._chrome(True)
        self.body.gradient = T.hero_gradient() if self.index == 0 else T.page_gradient()
        view = [self._home, self._calendar, self._insights, self._settings][self.index]()
        self.body.content = ft.Column([view], scroll=ft.ScrollMode.AUTO, expand=True)
        self.page.update()

    def _toast(self, msg: str):
        self.page.open(ft.SnackBar(ft.Text(msg), bgcolor=T.PRIMARY_DEEP))

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
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=14,
            controls=[
                ft.Text(self._greeting(), size=22, color=T.ON_HERO,
                        weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Text(today.strftime("%A, %d %B").upper(), size=12,
                        color=T.alpha(T.ON_HERO, 0.85), weight=ft.FontWeight.W_600,
                        style=ft.TextStyle(letter_spacing=1.2)),
                ft.Row([W.cycle_ring(s, size=260)],
                       alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([T.pill("Log period", icon=ft.Icons.WATER_DROP,
                               on_click=lambda e: self.open_log(), filled=False)],
                       alignment=ft.MainAxisAlignment.CENTER),
            ],
        )

        insight = T.card(ft.Column(spacing=12, controls=[
            ft.Row([W.phase_chip(s.phase)]) if s.phase else ft.Container(),
            self._info_row(ft.Icons.EGG_OUTLINED, T.C_OVULATION, "Ovulation",
                           fmt(s.ovulation_date)),
            self._info_row(ft.Icons.SPA_OUTLINED, T.C_OVULATION, "Fertile window",
                           fertile),
            self._info_row(ft.Icons.EVENT_REPEAT, T.PRIMARY, "Next period",
                           fmt(s.next_predicted)),
        ]))

        tiles = ft.Row(spacing=12, controls=[
            W.stat_tile(f"{s.avg_cycle_days or '—'}", "avg cycle (days)"),
            W.stat_tile(f"{s.avg_period_days or '—'}", "avg period (days)"),
            W.stat_tile(f"{s.logged_count}", "cycles logged"),
        ])

        return ft.Container(
            padding=ft.padding.only(left=18, right=18, top=18, bottom=28),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=18, controls=[hero, insight, tiles, self._phase_card(s)]))

    @staticmethod
    def _info_row(icon, icon_color, label, value) -> ft.Control:
        return ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
            ft.Row([ft.Icon(icon, color=icon_color, size=20),
                    ft.Text(label, color=T.MUTED, size=13)]),
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

        return T.card(ft.Column(spacing=10, controls=[
            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                T.label("CURRENT PHASE"),
                ft.Text(day_txt, size=12, color=T.MUTED) if day_txt else ft.Container(),
            ]),
            ft.Row(spacing=10, controls=[
                ft.Container(width=14, height=14, bgcolor=color, border_radius=7),
                ft.Text(title, size=18, weight=ft.FontWeight.BOLD, color=T.ON_SURFACE),
            ]),
            ft.Text(desc, size=13, color=T.MUTED) if desc else ft.Container(),
            ft.Divider(height=1, color="#EEE"),
            ft.Row(spacing=10, vertical_alignment=ft.CrossAxisAlignment.START, controls=[
                ft.Icon(ft.Icons.SCIENCE_OUTLINED, color=color, size=20),
                ft.Column(spacing=2, expand=True, controls=[
                    T.label("HORMONE INSIGHT"),
                    ft.Text(fact, size=13, color=T.ON_SURFACE),
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
                ft.Text(title, size=18, weight=ft.FontWeight.BOLD, color=T.ON_SURFACE),
                ft.IconButton(ft.Icons.CHEVRON_RIGHT, icon_color=T.PRIMARY,
                              on_click=lambda e: self._shift_month(1)),
            ])
        grid = T.card(ft.Column(spacing=14, controls=[
            W.calendar_grid(self.cal_year, self.cal_month, dm, date.today()),
            ft.Divider(height=1, color="#EEE"),
            W.calendar_legend(),
        ]))
        return ft.Container(
            padding=ft.padding.only(left=16, right=16, top=16, bottom=24),
            content=ft.Column(spacing=14, controls=[header, grid]))

    # ---- Insights ------------------------------------------------------
    def _insights(self) -> ft.Control:
        s = self._stats()
        entries = self.db.list_all()
        tiles = ft.Row(spacing=12, controls=[
            W.stat_tile(f"{s.avg_cycle_days or '—'}", "avg cycle (days)"),
            W.stat_tile(f"{s.avg_period_days or '—'}", "avg period (days)"),
        ])
        tiles2 = ft.Row(spacing=12, controls=[
            W.stat_tile(f"{s.cycle_day or '—'}", "current cycle day"),
            W.stat_tile(f"{s.logged_count}", "cycles logged"),
        ])
        history = [ft.Row([T.h1("History"),
                           ft.Text(f"{len(entries)} entries", color=T.MUTED, size=12)],
                          alignment=ft.MainAxisAlignment.SPACE_BETWEEN)]
        if entries:
            history += [self._entry_card(e) for e in entries]
        else:
            history.append(ft.Container(
                padding=24, alignment=ft.alignment.center,
                content=ft.Text("No entries yet — tap + to log a period.",
                                color=T.MUTED)))
        return ft.Container(
            padding=ft.padding.only(left=16, right=16, top=16, bottom=24),
            content=ft.Column(spacing=14, controls=[
                T.h1("Insights"), tiles, tiles2, ft.Container(height=4), *history]))

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
                ft.Row(spacing=12, expand=True, controls=[
                    ft.Container(width=8, height=42, bgcolor=T.C_PERIOD, border_radius=4),
                    ft.Column(spacing=2, expand=True, controls=[
                        ft.Text(rng, weight=ft.FontWeight.BOLD, size=15, color=T.ON_SURFACE),
                        ft.Text(" • ".join(sub), size=12, color=T.MUTED),
                        *([ft.Text(entry.notes, size=12, italic=True,
                                   color=T.MUTED)] if entry.notes else []),
                    ]),
                ]),
                ft.Row(spacing=0, controls=[
                    ft.IconButton(ft.Icons.EDIT_OUTLINED, icon_color=T.PRIMARY,
                                  on_click=lambda e, en=entry: self.open_log(en)),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=T.MUTED,
                                  on_click=lambda e, en=entry: self._confirm_delete(en)),
                ]),
            ]))

    def _confirm_delete(self, entry: PeriodEntry):
        def _do(e):
            self.db.delete(entry.id)
            self.page.close(dlg)
            self.render()
        dlg = ft.AlertDialog(
            modal=True, title=ft.Text("Delete entry?"),
            content=ft.Text(f"Remove period starting "
                            f"{entry.start_date.strftime('%d %b %Y')}?"),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.close(dlg)),
                     ft.FilledButton("Delete", on_click=_do)])
        self.page.open(dlg)

    # ---- Settings (centered content) -----------------------------------
    @staticmethod
    def _sec_label(text: str) -> ft.Control:
        return ft.Row([T.label(text)], alignment=ft.MainAxisAlignment.CENTER)

    def _settings(self) -> ft.Control:
        C = ft.CrossAxisAlignment.CENTER
        name_tf = ft.TextField(label="Name", border_radius=14, border_color=T.PRIMARY,
                               text_align=ft.TextAlign.CENTER,
                               value=self.db.get_setting("profile_name", ""))
        bday = {"d": self._parse_iso(self.db.get_setting("profile_birthday"))}
        bday_btn = ft.OutlinedButton(icon=ft.Icons.CAKE_OUTLINED, style=T.obtn_style())

        def sync_bday():
            bday_btn.text = bday["d"].strftime("%d %b %Y") if bday["d"] else "Not set"
            self.page.update()
        bday_btn.on_click = lambda e: self._pick_date(
            bday["d"] or date(2000, 1, 1), lambda d: (bday.update(d=d), sync_bday()))
        sync_bday()

        dc, dp = self._defaults()
        cyc_tf = ft.TextField(label="Default cycle length (days)", value=str(dc),
                              border_radius=14, border_color=T.PRIMARY,
                              text_align=ft.TextAlign.CENTER,
                              input_filter=ft.NumbersOnlyInputFilter())
        per_tf = ft.TextField(label="Default period length (days)", value=str(dp),
                              border_radius=14, border_color=T.PRIMARY,
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

        profile = T.card(ft.Column(spacing=14, horizontal_alignment=C, controls=[
            self._sec_label("PROFILE"), name_tf,
            ft.Row(alignment=ft.MainAxisAlignment.CENTER,
                   controls=[ft.Text("Birthday", color=T.MUTED), bday_btn]),
        ]))
        prefs = T.card(ft.Column(spacing=14, horizontal_alignment=C, controls=[
            self._sec_label("CYCLE PREFERENCES"),
            ft.Text("Used for predictions until you've logged enough history.",
                    size=12, color=T.MUTED, text_align=ft.TextAlign.CENTER),
            cyc_tf, per_tf,
        ]))
        save_btn = ft.Row(alignment=ft.MainAxisAlignment.CENTER,
                          controls=[T.pill("Save", icon=ft.Icons.CHECK, on_click=save_prefs)])

        appearance = T.card(ft.Column(spacing=12, horizontal_alignment=C, controls=[
            self._sec_label("APPEARANCE"),
            ft.Text("Theme", color=T.ON_SURFACE, weight=ft.FontWeight.W_600,
                    text_align=ft.TextAlign.CENTER),
            ft.Row(wrap=True, spacing=16, run_spacing=14,
                   alignment=ft.MainAxisAlignment.SPACE_EVENLY,
                   controls=[self._theme_swatch(n) for n in T.THEMES]),
        ]))

        lock = T.card(ft.Column(spacing=12, horizontal_alignment=C, controls=[
            self._sec_label("APP LOCK"),
            ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[
                ft.Icon(ft.Icons.LOCK_OUTLINE, color=T.PRIMARY, size=20),
                ft.Text("PIN lock " + ("enabled" if self.db.has_pin() else "off"),
                        color=T.ON_SURFACE, weight=ft.FontWeight.W_600)]),
            ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=10, controls=(
                [ft.OutlinedButton("Change PIN", style=T.obtn_style(),
                                   on_click=lambda e: self._pin_dialog(True)),
                 ft.TextButton("Remove PIN", on_click=self._remove_pin)]
                if self.db.has_pin() else
                [T.pill("Set PIN", icon=ft.Icons.PIN, on_click=lambda e: self._pin_dialog())]
            )),
        ]))

        data = T.card(ft.Column(spacing=12, horizontal_alignment=C, controls=[
            self._sec_label("DATA"),
            ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=10, controls=[
                ft.OutlinedButton("Load sample data", icon=ft.Icons.DATASET,
                                  style=T.obtn_style(), on_click=self._load_sample),
                ft.TextButton("Delete all data", icon=ft.Icons.DELETE_FOREVER,
                              on_click=self._confirm_clear_all),
            ]),
        ]))

        about = T.card(ft.Column(spacing=8, horizontal_alignment=C, controls=[
            self._sec_label("ABOUT"),
            ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=10, controls=[
                ft.Icon(ft.Icons.FAVORITE, color=T.C_PERIOD, size=22),
                ft.Column(spacing=0, horizontal_alignment=C, controls=[
                    ft.Text("Petal", color=T.ON_SURFACE,
                            weight=ft.FontWeight.BOLD, size=15),
                    ft.Text(f"Version {APP_VERSION}", color=T.MUTED, size=12),
                ]),
            ]),
            ft.Text("A private period and cycle tracker — log periods, symptoms "
                    "and moods, and see your phase, fertile window and next-period "
                    "predictions at a glance. Your data stays on your device.",
                    size=13, color=T.MUTED, text_align=ft.TextAlign.CENTER),
        ]))

        return ft.Container(
            padding=ft.padding.only(left=16, right=16, top=16, bottom=24),
            content=ft.Column(spacing=14, controls=[
                ft.Row([T.h1("Settings")], alignment=ft.MainAxisAlignment.CENTER),
                profile, prefs, save_btn, appearance, lock, data, about]))

    def _theme_swatch(self, name: str) -> ft.Control:
        pal = T.THEMES[name]
        active = self.db.get_setting("theme", "Lavender") == name
        return ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4,
            controls=[
                ft.Container(
                    width=52, height=52, border_radius=26,
                    gradient=ft.LinearGradient(begin=ft.alignment.top_left,
                                               end=ft.alignment.bottom_right,
                                               colors=pal["hero"]),
                    border=ft.border.all(3, T.PRIMARY if active else "#00000000"),
                    on_click=lambda e, n=name: self._set_theme(n),
                    content=(ft.Icon(ft.Icons.CHECK, color=pal["on_hero"], size=22)
                             if active else None),
                    alignment=ft.alignment.center),
                ft.Text(name, size=11, color=T.MUTED),
            ])

    def _set_theme(self, name: str):
        self.db.set_setting("theme", name)
        T.apply_theme(name)
        self.page.theme = T.app_theme()
        self.page.bgcolor = T.BG
        self.render()

    # ---- PIN / lock ----------------------------------------------------
    def _pin_dialog(self, change: bool = False):
        p1 = ft.TextField(label="Enter PIN", password=True, can_reveal_password=True,
                          keyboard_type=ft.KeyboardType.NUMBER, max_length=6,
                          border_color=T.PRIMARY,
                          input_filter=ft.NumbersOnlyInputFilter(), border_radius=14)
        p2 = ft.TextField(label="Confirm PIN", password=True, can_reveal_password=True,
                          keyboard_type=ft.KeyboardType.NUMBER, max_length=6,
                          border_color=T.PRIMARY,
                          input_filter=ft.NumbersOnlyInputFilter(), border_radius=14)
        err = ft.Text("", color=T.C_PERIOD, size=12, visible=False)

        def _save(e):
            v = p1.value or ""
            if len(v) < 4:
                err.value, err.visible = "PIN must be at least 4 digits.", True
                self.page.update(); return
            if v != (p2.value or ""):
                err.value, err.visible = "PINs don't match.", True
                self.page.update(); return
            self.db.set_pin(v)
            self.page.close(dlg)
            self._toast("PIN updated")
            self.render()

        dlg = ft.AlertDialog(
            modal=True, title=ft.Text("Change PIN" if change else "Set PIN"),
            content=ft.Column([p1, p2, err], tight=True, spacing=12, width=300),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.close(dlg)),
                     ft.FilledButton("Save", on_click=_save)])
        self.page.open(dlg)

    def _remove_pin(self, e):
        def _do(ev):
            self.db.clear_pin()
            self.page.close(dlg)
            self._toast("PIN removed")
            self.render()
        dlg = ft.AlertDialog(
            modal=True, title=ft.Text("Remove PIN?"),
            content=ft.Text("The app will no longer be locked."),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.close(dlg)),
                     ft.FilledButton("Remove", on_click=_do)])
        self.page.open(dlg)

    def _show_lock(self):
        self._chrome(False)
        self.page.appbar = None
        self.body.gradient = T.hero_gradient()
        pin_tf = ft.TextField(
            password=True, can_reveal_password=True, width=220,
            text_align=ft.TextAlign.CENTER, keyboard_type=ft.KeyboardType.NUMBER,
            max_length=6, input_filter=ft.NumbersOnlyInputFilter(),
            border_color=T.ON_HERO, color=T.ON_HERO,
            hint_text="PIN", hint_style=ft.TextStyle(color=T.alpha(T.ON_HERO, 0.7)))
        err = ft.Text("", color="#FFCDD2", size=13, visible=False)

        def unlock(e=None):
            if self.db.check_pin(pin_tf.value or ""):
                self.render()
            else:
                err.value, err.visible = "Incorrect PIN", True
                pin_tf.value = ""
                self.page.update()
        pin_tf.on_submit = unlock

        self.body.content = ft.Container(
            alignment=ft.alignment.center,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=18,
                controls=[
                    ft.Icon(ft.Icons.LOCK, color=T.ON_HERO, size=48),
                    ft.Text("Enter your PIN", color=T.ON_HERO, size=20,
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
            self.page.close(dlg)
            self._toast("All entries deleted")
            self.render()
        dlg = ft.AlertDialog(
            modal=True, title=ft.Text("Delete all data?"),
            content=ft.Text("This permanently removes every logged period."),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.close(dlg)),
                     ft.FilledButton("Delete all", on_click=_do)])
        self.page.open(dlg)

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
        self.page.open(dp)

    # ---- log form ------------------------------------------------------
    def open_log(self, entry: Optional[PeriodEntry] = None):
        editing = entry is not None
        st = {"start": entry.start_date if editing else date.today(),
              "end": entry.end_date if editing else None}

        start_btn = ft.OutlinedButton(icon=ft.Icons.CALENDAR_MONTH, style=T.obtn_style())
        end_btn = ft.OutlinedButton(icon=ft.Icons.CALENDAR_MONTH, style=T.obtn_style())

        def sync():
            start_btn.text = st["start"].strftime("%d %b %Y")
            end_btn.text = st["end"].strftime("%d %b %Y") if st["end"] else "Not set"
            self.page.update()

        start_btn.on_click = lambda e: self._pick_date(
            st["start"], lambda d: (st.update(start=d), sync()))
        end_btn.on_click = lambda e: self._pick_date(
            st["end"] or st["start"], lambda d: (st.update(end=d), sync()))

        flow_dd = ft.Dropdown(label="Flow", value=entry.flow if editing else "Medium",
                              options=[ft.dropdown.Option(f) for f in FLOW_LEVELS],
                              border_radius=14, border_color=T.PRIMARY)
        mood_dd = ft.Dropdown(label="Mood", value=entry.mood if editing else "",
                              options=[ft.dropdown.Option(key="", text="— None —")] +
                              [ft.dropdown.Option(m) for m in MOODS],
                              border_radius=14, border_color=T.PRIMARY)
        notes_tf = ft.TextField(label="Notes", multiline=True, min_lines=2, max_lines=4,
                                border_radius=14, border_color=T.PRIMARY,
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

        form = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=16, controls=[
            T.card(ft.Column(spacing=14, controls=[
                ft.Row([ft.Text("Start", width=70, color=T.MUTED), start_btn]),
                ft.Row([ft.Text("End", width=70, color=T.MUTED), end_btn,
                        ft.TextButton("Clear",
                                      on_click=lambda e: (st.update(end=None), sync()))]),
            ])),
            T.card(ft.Column(spacing=14, controls=[flow_dd, mood_dd])),
            T.card(ft.Column(spacing=10, controls=[
                T.label("SYMPTOMS"),
                ft.Row(chips, wrap=True, spacing=6, run_spacing=6)])),
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
