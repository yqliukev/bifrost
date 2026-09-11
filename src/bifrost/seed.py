"""Hand-written records for step 2, and the fixed `now` they are anchored to.

Everything here is dated against `SEED_NOW` rather than the wall clock, so the
same question produces the same agenda on any day. Step 6 loads these same
rows into SQLite; step 22 freezes them as the eval fixture.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from bifrost.records import CalendarEvent, EventStatus, Priority, Task

SEED_TIMEZONE = "America/New_York"
SEED_DATE = date(2026, 9, 11)
SEED_NOW = datetime(2026, 9, 11, 8, 30, tzinfo=ZoneInfo(SEED_TIMEZONE)).astimezone(UTC)
"""Friday morning, before the first meeting. Pass this in as `now`; never read the clock."""

SEED_EVENTS: tuple[CalendarEvent, ...] = (
    CalendarEvent.from_local(
        id="evt_001",
        title="Engineering standup",
        start=datetime(2026, 9, 11, 9, 15),
        end=datetime(2026, 9, 11, 9, 30),
        location="Meet",
        series_id="ser_standup",
        recurrence_id=datetime(2026, 9, 11, 9, 15, tzinfo=ZoneInfo(SEED_TIMEZONE)),
        recurrence_rule="FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR",
    ),
    CalendarEvent.from_local(
        id="evt_002",
        title="Design review: ingestion pipeline",
        start=datetime(2026, 9, 11, 11, 0),
        end=datetime(2026, 9, 11, 12, 0),
        location="Room 4B",
        description="Walk through the connector boundary before the sync work starts.",
    ),
    CalendarEvent.from_local(
        id="evt_003",
        title="Lunch with Priya",
        start=datetime(2026, 9, 11, 12, 30),
        end=datetime(2026, 9, 11, 13, 30),
        location="Cafe Sol",
    ),
    CalendarEvent.from_local(
        id="evt_004",
        title="1:1 with Dana",
        start=datetime(2026, 9, 11, 13, 0),
        end=datetime(2026, 9, 11, 13, 45),
        status=EventStatus.TENTATIVE,
        location="Room 2A",
    ),
    CalendarEvent.all_day_on(
        id="evt_005",
        title="Marta and Sam's wedding",
        day=date(2026, 9, 12),
        location="Hudson Valley",
    ),
)

SEED_TASKS: tuple[Task, ...] = (
    Task.due_local(
        id="task_001",
        title="Draft the sync.py ingestion spec",
        due=datetime(2026, 9, 11, 17, 0),
        priority=Priority.HIGH,
        estimated_minutes=90,
    ),
    Task.due_on(
        id="task_002",
        title="Reply to Priya about the calendar export",
        day=SEED_DATE,
        estimated_minutes=15,
    ),
    Task.due_on(
        id="task_003",
        title="Renew passport",
        day=date(2026, 10, 2),
        priority=Priority.LOW,
        estimated_minutes=45,
    ),
)
