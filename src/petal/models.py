"""Data models for the period tracker."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional

# Fixed option sets keep the UI pickers and DB values in sync.
FLOW_LEVELS = ["Light", "Medium", "Heavy"]
MOODS = ["Happy", "Calm", "Sad", "Irritable", "Anxious", "Energetic", "Tired"]
SYMPTOMS = [
    "Cramps", "Headache", "Bloating", "Fatigue", "Backache",
    "Tender breasts", "Acne", "Nausea", "Cravings", "Diarrhea",
]


@dataclass
class PeriodEntry:
    """A single logged period (the core record of the app)."""

    start_date: date
    end_date: Optional[date] = None
    flow: str = "Medium"
    mood: str = ""
    symptoms: List[str] = field(default_factory=list)
    notes: str = ""
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    @property
    def period_length(self) -> Optional[int]:
        """Duration of the period in days (inclusive), if an end date is set."""
        if self.end_date is None:
            return None
        return (self.end_date - self.start_date).days + 1

    @property
    def symptoms_csv(self) -> str:
        return ",".join(self.symptoms)
