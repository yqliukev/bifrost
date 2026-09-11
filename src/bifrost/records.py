"""Canonical record schema for Bifrost.

These are the normalized rows that live in the store and that tools read from.
They are deliberately *not* iCalendar objects: an `.ics` VEVENT is a wire
format with floating times, recurrence masters and provider quirks, and the
whole point of the Ring 1 / Ring 2 split is that none of that reaches the
model. `sync.py` parses provider formats and produces these.

No library is adopted for this layer, because every candidate models the wire
format rather than a canonical store: `ical`, `icalendar` and `ics.py` are all
RFC 5545 object graphs. The right place for one is step 10, inside `sync.py`,
where a parser expands a VEVENT and its RRULE into the occurrences that become
the rows below. Nothing from it is ever imported on the agent side.

Conventions that the rest of the system relies on:

- Every timestamp is timezone-aware and stored in UTC. `timezone` carries the
  IANA zone the record belongs to, for display only.
- An event row is a single *occurrence*, never a recurrence master. A repeating
  meeting produces one row per occurrence, sharing a `series_id`.
- Intervals are half-open: `[start, end)`. Back-to-back events do not overlap.
- Fields are flat scalars, so a row maps one-to-one onto a SQLite column and
  onto a tool schema without nesting.
- Ids are opaque and stable, because the model will cite them.
"""

from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from typing import Annotated, Any, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

DEFAULT_TIMEZONE = "America/New_York"

SEED_SOURCE = "src_seed"
"""Source id for hand-written records, so lineage is never null."""


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            "timestamps must be timezone-aware; build them with "
            "ZoneInfo(...) or use the from_local helpers"
        )
    return value.astimezone(UTC)


def _known_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"unknown IANA timezone: {value!r}") from exc
    return value


UTCDatetime = Annotated[datetime, AfterValidator(_to_utc)]
TimezoneName = Annotated[str, AfterValidator(_known_timezone)]
EventId = Annotated[str, Field(pattern=r"^evt_[a-z0-9_]+$")]
TaskId = Annotated[str, Field(pattern=r"^task_[a-z0-9_]+$")]


class EventStatus(StrEnum):
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class Record(BaseModel):
    """Shared identity and lineage for everything in the store."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    source_id: str = SEED_SOURCE
    provider_id: str | None = None
    """Identity of this record in its origin system, e.g. an iCalendar UID.

    Together with `source_id` this is the upsert key for a re-sync. Events add
    `recurrence_id`, because a whole series shares a single UID.
    """


class CalendarEvent(Record):
    id: EventId
    title: str = Field(min_length=1, max_length=300)
    start: UTCDatetime
    end: UTCDatetime
    timezone: TimezoneName = DEFAULT_TIMEZONE
    all_day: bool = False
    status: EventStatus = EventStatus.CONFIRMED
    busy: bool = True
    """Whether this occupies the calendar. A `busy=False` event cannot conflict."""
    location: str | None = None
    description: str | None = None
    series_id: str | None = None
    recurrence_id: UTCDatetime | None = None
    """The originally scheduled start of this occurrence, RFC 5545 RECURRENCE-ID.

    Every occurrence of a series carries the same provider UID, so this is what
    keeps the upsert key unique. It stays pinned to the original start even
    when the occurrence is later moved, which is how a re-sync recognizes a
    rescheduled instance instead of writing a second row for it.
    """
    recurrence_rule: str | None = None
    """RFC 5545 RRULE of the series this occurrence came from, kept for display."""

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        if self.recurrence_id is not None and self.series_id is None:
            raise ValueError(f"{self.id}: recurrence_id set without a series_id")
        if self.end < self.start:
            raise ValueError(f"{self.id}: end {self.end} precedes start {self.start}")
        if self.all_day:
            if self.end == self.start:
                raise ValueError(f"{self.id}: an all-day event must span at least one day")
            midnights = (self.local_start.time(), self.local_end.time())
            if midnights != (time.min, time.min):
                raise ValueError(
                    f"{self.id}: an all-day event must run midnight to midnight "
                    f"in {self.timezone}, got {midnights}"
                )
        return self

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    @property
    def local_start(self) -> datetime:
        return self.start.astimezone(ZoneInfo(self.timezone))

    @property
    def local_end(self) -> datetime:
        return self.end.astimezone(ZoneInfo(self.timezone))

    @property
    def local_date(self) -> date:
        return self.local_start.date()

    @classmethod
    def from_local(
        cls,
        *,
        id: str,
        title: str,
        start: datetime,
        end: datetime,
        timezone: str = DEFAULT_TIMEZONE,
        **fields: Any,
    ) -> Self:
        """Build from naive wall-clock times in `timezone`.

        Writing fixtures in UTC is unreadable and a reliable source of
        off-by-an-hour mistakes, so local wall time is the input and the
        conversion happens once, here.
        """
        zone = ZoneInfo(timezone)
        return cls(
            id=id,
            title=title,
            start=start.replace(tzinfo=zone),
            end=end.replace(tzinfo=zone),
            timezone=timezone,
            **fields,
        )

    @classmethod
    def all_day_on(
        cls,
        *,
        id: str,
        title: str,
        day: date,
        days: int = 1,
        timezone: str = DEFAULT_TIMEZONE,
        **fields: Any,
    ) -> Self:
        """Build an all-day event as the half-open span of `days` local days."""
        return cls.from_local(
            id=id,
            title=title,
            start=datetime.combine(day, time.min),
            end=datetime.combine(day + timedelta(days=days), time.min),
            timezone=timezone,
            all_day=True,
            **fields,
        )


class Task(Record):
    id: TaskId
    title: str = Field(min_length=1, max_length=300)
    status: TaskStatus = TaskStatus.TODO
    priority: Priority = Priority.NORMAL
    due: UTCDatetime | None = None
    due_all_day: bool = False
    """True when the source gave a due date with no time, e.g. `due: 2026-09-11`.

    `due` still holds an instant — the end of that local day — so every
    comparison stays a timestamp comparison.
    """
    timezone: TimezoneName = DEFAULT_TIMEZONE
    estimated_minutes: int | None = Field(default=None, gt=0)
    completed_at: UTCDatetime | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        if self.due_all_day and self.due is None:
            raise ValueError(f"{self.id}: due_all_day set without a due date")
        if self.completed_at is not None and self.status is not TaskStatus.DONE:
            raise ValueError(f"{self.id}: completed_at set on a {self.status} task")
        return self

    @property
    def local_due(self) -> datetime | None:
        if self.due is None:
            return None
        return self.due.astimezone(ZoneInfo(self.timezone))

    @property
    def due_date(self) -> date | None:
        """The calendar date a human would call the deadline.

        A date-only due is stored as the exclusive end of its local day, so the
        raw instant falls on the following date and must be stepped back.
        """
        local = self.local_due
        if local is None:
            return None
        return (local - timedelta(microseconds=1)).date() if self.due_all_day else local.date()

    @classmethod
    def due_local(
        cls,
        *,
        id: str,
        title: str,
        due: datetime,
        timezone: str = DEFAULT_TIMEZONE,
        **fields: Any,
    ) -> Self:
        """Build with a naive wall-clock due time in `timezone`."""
        return cls(
            id=id,
            title=title,
            due=due.replace(tzinfo=ZoneInfo(timezone)),
            timezone=timezone,
            **fields,
        )

    @classmethod
    def due_on(
        cls,
        *,
        id: str,
        title: str,
        day: date,
        timezone: str = DEFAULT_TIMEZONE,
        **fields: Any,
    ) -> Self:
        """Build with a date-only due date, anchored to the end of that local day."""
        return cls.due_local(
            id=id,
            title=title,
            due=datetime.combine(day + timedelta(days=1), time.min),
            timezone=timezone,
            due_all_day=True,
            **fields,
        )
