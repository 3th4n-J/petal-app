"""Derived cycle statistics: predictions, phases, fertile window, calendar map.

Cycle length = days between consecutive period start dates. Ovulation is
estimated at (cycle_length - 14) days into the cycle, with a fertile window of
the 5 days before ovulation through 1 day after -- the standard simple model
apps like Flo start from before personalising.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import mean
from typing import Dict, List, Optional

from .models import PeriodEntry

DEFAULT_CYCLE_DAYS = 28
DEFAULT_PERIOD_DAYS = 5
LUTEAL_DAYS = 14  # days from ovulation to next period

# Day-classification categories used by the calendar + ring.
PERIOD = "period"          # logged period day
PERIOD_PREDICTED = "predicted"
FERTILE = "fertile"
OVULATION = "ovulation"

PHASE_MENSTRUAL = "Menstrual"
PHASE_FOLLICULAR = "Follicular"
PHASE_OVULATION = "Ovulation"
PHASE_LUTEAL = "Luteal"


@dataclass
class CycleStats:
    logged_count: int
    avg_cycle_days: Optional[float]
    avg_period_days: Optional[float]
    last_start: Optional[date]
    next_predicted: Optional[date]
    days_until_next: Optional[int]
    # live cycle state (relative to `today`)
    cycle_day: Optional[int] = None          # 1-indexed day of current cycle
    cycle_length: int = DEFAULT_CYCLE_DAYS   # effective length used for maths
    period_length: int = DEFAULT_PERIOD_DAYS
    phase: Optional[str] = None
    ovulation_date: Optional[date] = None
    fertile_start: Optional[date] = None
    fertile_end: Optional[date] = None
    progress: float = 0.0                    # 0..1 around the ring


def _gaps(starts: List[date]) -> List[int]:
    return [(b - a).days for a, b in zip(starts, starts[1:]) if 0 < (b - a).days <= 90]


def compute(entries: List[PeriodEntry], today: Optional[date] = None,
            default_cycle: int = DEFAULT_CYCLE_DAYS,
            default_period: int = DEFAULT_PERIOD_DAYS) -> CycleStats:
    today = today or date.today()
    starts = sorted(e.start_date for e in entries if e.start_date)

    gaps = _gaps(starts)
    avg_cycle = round(mean(gaps), 1) if gaps else None
    lengths = [e.period_length for e in entries if e.period_length]
    avg_period = round(mean(lengths), 1) if lengths else None

    cycle_len = round(avg_cycle) if avg_cycle else default_cycle
    period_len = round(avg_period) if avg_period else default_period

    last_start = starts[-1] if starts else None
    next_pred = last_start + timedelta(days=cycle_len) if last_start else None
    days_until = (next_pred - today).days if next_pred else None

    stats = CycleStats(
        logged_count=len(entries), avg_cycle_days=avg_cycle,
        avg_period_days=avg_period, last_start=last_start,
        next_predicted=next_pred, days_until_next=days_until,
        cycle_length=cycle_len, period_length=period_len,
    )

    if last_start:
        cycle_day = (today - last_start).days + 1
        # If we've sailed past a predicted start, roll the anchor forward so the
        # ring reflects the *current* cycle rather than a stale one.
        anchor = last_start
        while cycle_day > cycle_len + 2 and cycle_day > 0:
            anchor = anchor + timedelta(days=cycle_len)
            cycle_day = (today - anchor).days + 1
        stats.cycle_day = max(cycle_day, 1)
        stats.progress = min(max(stats.cycle_day / cycle_len, 0.0), 1.0)

        ov_offset = max(cycle_len - LUTEAL_DAYS, 1)
        stats.ovulation_date = anchor + timedelta(days=ov_offset - 1)
        stats.fertile_start = stats.ovulation_date - timedelta(days=5)
        stats.fertile_end = stats.ovulation_date + timedelta(days=1)
        stats.next_predicted = anchor + timedelta(days=cycle_len)
        stats.days_until_next = (stats.next_predicted - today).days
        stats.phase = _phase(stats.cycle_day, period_len, ov_offset)

    return stats


def _phase(cycle_day: int, period_len: int, ov_offset: int) -> str:
    if cycle_day <= period_len:
        return PHASE_MENSTRUAL
    if ov_offset - 1 <= cycle_day <= ov_offset + 1:
        return PHASE_OVULATION
    if cycle_day < ov_offset - 1:
        return PHASE_FOLLICULAR
    return PHASE_LUTEAL


def _daterange(a: date, b: date):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def day_map(entries: List[PeriodEntry], today: Optional[date] = None,
            months_ahead: int = 3, default_cycle: int = DEFAULT_CYCLE_DAYS,
            default_period: int = DEFAULT_PERIOD_DAYS) -> Dict[date, str]:
    """Classify dates for the calendar.

    Precedence: logged period > ovulation > fertile > predicted.
    Projects predicted periods / fertile windows forward `months_ahead` cycles.
    """
    today = today or date.today()
    stats = compute(entries, today, default_cycle, default_period)
    out: Dict[date, str] = {}

    # Predicted (future) first, so logged/actual can overwrite.
    if stats.last_start and stats.cycle_length:
        cl, pl = stats.cycle_length, stats.period_length
        anchor = stats.next_predicted or stats.last_start
        for _ in range(max(months_ahead, 1) + 1):
            for d in _daterange(anchor, anchor + timedelta(days=pl - 1)):
                out[d] = PERIOD_PREDICTED
            ov = anchor - timedelta(days=LUTEAL_DAYS)
            for d in _daterange(ov - timedelta(days=5), ov + timedelta(days=1)):
                out.setdefault(d, FERTILE)
            out[ov] = OVULATION
            anchor = anchor + timedelta(days=cl)

    # Current-cycle fertile window / ovulation.
    if stats.fertile_start and stats.fertile_end:
        for d in _daterange(stats.fertile_start, stats.fertile_end):
            out.setdefault(d, FERTILE)
    if stats.ovulation_date:
        out.setdefault(stats.ovulation_date, OVULATION)

    # Logged periods win outright.
    for e in entries:
        if not e.start_date:
            continue
        end = e.end_date or e.start_date
        for d in _daterange(e.start_date, end):
            out[d] = PERIOD

    return out
