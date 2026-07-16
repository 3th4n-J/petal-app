"""Seed the DB with sample period entries (roughly monthly cycles)."""
from __future__ import annotations

from datetime import date, timedelta

from .db import Database
from .models import PeriodEntry

SAMPLE = [
    # (days_ago_start, length, flow, mood, symptoms, notes)
    (118, 5, "Medium", "Tired",    ["Cramps", "Fatigue"],            "Normal cycle."),
    (89,  4, "Light",  "Calm",     ["Headache"],                     ""),
    (61,  6, "Heavy",  "Irritable",["Cramps", "Bloating", "Backache"], "Heavier than usual."),
    (32,  5, "Medium", "Sad",      ["Cravings", "Acne"],             ""),
    (4,   4, "Medium", "Anxious",  ["Cramps"],                       "Current cycle."),
]


def run():
    db = Database()
    if db.list_all():
        print("DB already has entries; skipping seed.")
        return
    today = date.today()
    for days_ago, length, flow, mood, symptoms, notes in SAMPLE:
        start = today - timedelta(days=days_ago)
        db.add(PeriodEntry(
            start_date=start, end_date=start + timedelta(days=length - 1),
            flow=flow, mood=mood, symptoms=symptoms, notes=notes,
        ))
    print(f"Seeded {len(SAMPLE)} entries.")


if __name__ == "__main__":
    run()
