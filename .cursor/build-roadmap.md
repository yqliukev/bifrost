# Bifrost — implementation roadmap

A build order toward the first useful version in [plan.md](plan.md). Each step names what to read, what to type, and how to know you are done. Later steps reuse earlier files; do not skip.

The original [learning roadmap](roadmap.md) is unchanged, for comparison. That document teaches by writing naive code, watching it fail, then adding a constraint. This one is an instruction list for a working product. Constraints from the vision still apply — they are listed as rules below, not as separate “break it first” exercises.

## How to use a step

Every step has the same shape:

1. **Read first** — follow the links and extract the listed facts before writing code. This is the work, not a preface.
2. **Do** — create or change the named files. Code sketches show the shape, not a finished program.
3. **Done when** — a command or check you can actually run.

If you ask an agent to implement a step, paste the whole step (including **Read first**) and tell it not to invent fields, tables, or libraries that the step does not name.

Stay on the [Interactions API](https://ai.google.dev/gemini-api/docs/interactions-overview) (`client.interactions.create`). That is already what `src/bifrost/__init__.py` uses. Do not add LangChain or LangGraph for v1; they are part of the [sample architecture](plans/bifrost_agentic_assistant_72142ad7.plan.md), which [plan.md](plan.md) marks as not being implemented.

## Where the repo already is

| Already true | Consequence |
|---|---|
| `uv` project, Python 3.14, `google-genai`, `pydantic`, `python-dotenv` in `pyproject.toml` | Do not re-init the project. Run code with `uv run`. |
| `src/bifrost/__init__.py` already calls `gemini-3.8-flash` and prints token counts | Step 3 reuses this client. Extract a `print_usage()` helper when you touch it. |
| `GEMINI_API_KEY` loaded from `.env` | Keep secrets out of git (`.gitignore` already lists `.env`). |
| Branch `records` has a fuller schema | Treat it as optional reading *after* step 1. Do not start by copying it. |

## Libraries you will learn, and when

| When | Library | Why it appears |
|---|---|---|
| Step 1 | [Pydantic](https://docs.pydantic.dev/latest/) | Typed records and, later, tool results and widget specs. Already installed. |
| Step 1 | [`datetime` / `zoneinfo`](https://docs.python.org/3/library/datetime.html) | Timezone-aware timestamps. Standard library. |
| Step 3–5 | [`google-genai` Interactions API](https://ai.google.dev/gemini-api/docs/interactions/quickstart) | Model calls, then function calling, then a chat loop. Already installed. |
| Step 6 | [`sqlite3`](https://docs.python.org/3/library/sqlite3.html) | Canonical store. Standard library. |
| Step 9 | Pydantic JSON schema + Gemini [structured output](https://ai.google.dev/gemini-api/docs/structured-output) | Daily plan the code can validate. |
| Step 10 | An iCalendar parser, only inside `sync.py` | Ingest stays outside the model loop. |
| Step 13 | [`hashlib`](https://docs.python.org/3/library/hashlib.html) | Approval binds to a payload, not an intent. |
| Step 14 | [FastAPI](https://fastapi.tiangolo.com/tutorial/first-steps/) | Serve prebuilt widgets. Add the dependency when you reach this step. |

## Rules that hold from step 1

Cheap now, expensive to retrofit. Honor them in every slice.

1. **Never call `datetime.now()` inside logic.** Pass `now` in from the CLI, a seed constant, or a test. This is what makes later checks reproducible.
2. **Give every record a stable opaque id** (`evt_001`, `task_004`, `goal_001`). The model will cite these; citations only work if ids do not move.
3. **Store timestamps in UTC.** Convert at the edges for display. Construct seed data in a local zone, then convert once.
4. **Print token counts and cost after every model call.** Use the `usage` object you already print. Rough cost through 2026-12-31: input $0.75 / million, output (including thinking) $3.75 / million.
5. **Never hand the model a provider blob.** Calendar rows, tool results, and widget specs are Pydantic models serialized with an explicit field list. Raw `.ics`, HTML, API JSON, and database rows stay in your code.
6. **No `from __future__ import annotations`.** Python 3.14 defers annotation evaluation natively.

---

## Step 1 — Learn Pydantic and define the record types

**Goal.** You can explain what a `BaseModel` does, and the project has two small record types the rest of the system will store, query, and show to the model.

Pydantic is a validation library: you declare a class with typed fields, and constructing an instance either succeeds with coerced/checked data or raises `ValidationError`. That is how fake tasks get created — not by stuffing dicts into a prompt, but by constructing models. Serialization (`model_dump`) is how those models become the string the model sees.

### Read first

Read these pages, in order. Do not skim the titles only.

1. [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/) — what `BaseModel` is; `model_validate` vs constructing with keyword args; that extra fields can be forbidden.
2. [Fields](https://docs.pydantic.dev/latest/concepts/fields/) — `Field(min_length=..., pattern=...)`.
3. [Serialization](https://docs.pydantic.dev/latest/concepts/serialization/) — `model_dump()` vs `model_dump_json()`; `mode="json"` (datetimes become ISO strings); `exclude_none=True`.
4. [Validators](https://docs.pydantic.dev/latest/concepts/validators/) — `@model_validator(mode="after")` for checks that involve two fields (e.g. `end` after `start`).
5. Python [aware vs naive datetimes](https://docs.python.org/3/library/datetime.html#aware-and-naive-objects) and [`zoneinfo.ZoneInfo`](https://docs.python.org/3/library/zoneinfo.html).

What you should be able to say after reading, without looking it up:

- A Pydantic model is a class. `CalendarEvent(id="evt_001", ...)` runs validation. A dict is just a dict.
- `model_dump(mode="json")` is the method you will use to put records into a prompt.
- Naive datetimes (`datetime(2026, 9, 11, 9, 15)` with no `tzinfo`) are a bug in this project.

### Do

Create `src/bifrost/records.py` with **only** these types. Do not add recurrence, series, provider ids, or content hashes yet.

```python
from datetime import datetime
from pydantic import BaseModel, Field, model_validator
from typing import Self

class CalendarEvent(BaseModel):
    id: str = Field(pattern=r"^evt_[a-z0-9_]+$")
    title: str = Field(min_length=1, max_length=300)
    start: datetime
    end: datetime
    location: str | None = None
    description: str | None = None

    @model_validator(mode="after")
    def _check_times(self) -> Self:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError(f"{self.id}: start and end must be timezone-aware")
        if self.end <= self.start:
            raise ValueError(f"{self.id}: end must be after start")
        return self

class Task(BaseModel):
    id: str = Field(pattern=r"^task_[a-z0-9_]+$")
    title: str = Field(min_length=1, max_length=300)
    due: datetime | None = None
    status: str = "todo"  # todo | done
    notes: str | None = None

class Goal(BaseModel):
    id: str = Field(pattern=r"^goal_[a-z0-9_]+$")
    title: str = Field(min_length=1, max_length=300)
    status: str = "active"
```

Add a `from_local` classmethod on `CalendarEvent` once you understand `ZoneInfo`: it takes naive wall-clock `start`/`end` plus a timezone name, attaches `ZoneInfo(timezone)`, and constructs the model. That is the helper seed data will use. The records branch does this; you can read it after yours works.

```bash
git show records:src/bifrost/records.py
```

Use that file as a *later* reference for UTC conversion and helpers. Do not copy recurrence fields into v1.

### Done when

```bash
uv run python -c "
from datetime import datetime
from zoneinfo import ZoneInfo
from pydantic import ValidationError
from bifrost.records import CalendarEvent

tz = ZoneInfo('America/New_York')
e = CalendarEvent(
    id='evt_001',
    title='Standup',
    start=datetime(2026, 9, 11, 9, 15, tzinfo=tz),
    end=datetime(2026, 9, 11, 9, 30, tzinfo=tz),
)
print(e.model_dump(mode='json'))

try:
    CalendarEvent(id='nope', title='x', start=datetime(2026, 9, 11, 9, 0, tzinfo=tz), end=datetime(2026, 9, 11, 10, 0, tzinfo=tz))
except ValidationError as err:
    print('bad id rejected')
"
```

You should see an ISO-timestamp dict, then `bad id rejected`. A naive `datetime(2026, 9, 11, 9, 15)` (no `tzinfo`) must also raise.

---

## Step 2 — Seed a frozen day

**Goal.** A Python module holds five events, three tasks, and two goals, all dated against a fixed `now`. This is the “fake tasks” step: you construct Pydantic instances, you do not invent a database yet.

### Read first

- Your own `records.py` from step 1 — you will only call constructors you already wrote.
- [`datetime.combine`](https://docs.python.org/3/library/datetime.html#datetime.datetime.combine) if you want a date-only due date (midnight next day is a reasonable exclusive end; keep it simple and give tasks a due *time* if that is clearer).

### Do

Create `src/bifrost/seed.py`.

1. Pick a timezone (`America/New_York` unless you have a reason not to) and a frozen instant:

   ```python
   from datetime import datetime
   from zoneinfo import ZoneInfo

   SEED_TIMEZONE = "America/New_York"
   TZ = ZoneInfo(SEED_TIMEZONE)
   SEED_NOW = datetime(2026, 9, 11, 8, 30, tzinfo=TZ)  # Friday morning, before standup
   ```

   Every later function that needs “now” takes `now` as an argument. Tests and the CLI pass `SEED_NOW` until you opt into wall-clock time at the edge.

2. Write `SEED_EVENTS`, `SEED_TASKS`, and `SEED_GOALS` as tuples of models. Use ids `evt_001`…`evt_005`, `task_001`…`task_003`, `goal_001`, `goal_002`. Include at least:

   - two events that overlap (needed in step 8)
   - one event tomorrow
   - one task due today, one due later
   - titles a human would recognize in conversation

   Example of *how* to construct one event (write the rest the same way):

   ```python
   from bifrost.records import CalendarEvent

   CalendarEvent(
       id="evt_001",
       title="Engineering standup",
       start=datetime(2026, 9, 11, 9, 15, tzinfo=TZ),
       end=datetime(2026, 9, 11, 9, 30, tzinfo=TZ),
       location="Meet",
   )
   ```

   If you added `CalendarEvent.from_local`, you may use that instead of repeating `tzinfo=TZ`.

### Done when

```bash
uv run python -c "
from bifrost.seed import SEED_EVENTS, SEED_TASKS, SEED_GOALS, SEED_NOW
assert len(SEED_EVENTS) >= 5 and len(SEED_TASKS) >= 3
print('now', SEED_NOW)
print([e.id for e in SEED_EVENTS])
print([t.id for t in SEED_TASKS])
print([g.id for g in SEED_GOALS])
"
```

No model call yet. If construction raises `ValidationError`, fix the seed, not the validator.

Optional: `git show records:src/bifrost/seed.py` after yours runs, to compare. Yours can stay simpler.

---

## Step 3 — First conversation: seed data in the prompt

**Goal.** Ask Gemini “what’s on today?” with the seed serialized into the prompt. This is already a (tiny) assistant: you chose the context, the model answered from it.

### Read first

- [Interactions API quickstart](https://ai.google.dev/gemini-api/docs/interactions/quickstart) sections 1–2, and the `generation_config` / thinking notes in the same guide if present.
- [Pydantic serialization](https://docs.pydantic.dev/latest/concepts/serialization/) again, specifically `mode="json"` and `exclude_none`.
- Your existing `src/bifrost/__init__.py` — reuse `genai.Client()`, `thinking_level`, and the usage fields.

### Do

1. Add `src/bifrost/usage.py` with a function that prints input, thought, output, total tokens, and estimated USD from `interaction.usage`. Call it from everywhere you call the model.

2. Add `src/bifrost/render.py`:

   ```python
   def records_for_prompt(events, tasks, goals) -> str:
       payload = {
           "now": ...,  # ISO string of the injected now
           "timezone": ...,
           "events": [e.model_dump(mode="json", exclude_none=True) for e in events],
           "tasks": [t.model_dump(mode="json", exclude_none=True) for t in tasks],
           "goals": [g.model_dump(mode="json", exclude_none=True) for g in goals],
       }
       return json.dumps(payload, indent=2)
   ```

3. Change the CLI entry (`src/bifrost/__init__.py` `main`, or a new `src/bifrost/cli.py` wired in `pyproject.toml`) so `uv run bifrost` does one call:

   - `system_instruction`: you are a personal assistant; the JSON block is local records; cite ids; do not invent ids.
   - `input`: the rendered JSON plus the user question `"What's on today?"`.
   - `generation_config={"thinking_level": "low"}` for this mechanical question.
   - Print the answer and usage.

Pass `now=SEED_NOW`. Do not read the clock.

### Done when

```bash
uv run bifrost
```

The answer mentions standup (or whatever you titled `evt_001`) and cites `evt_001`. Token counts print. Asking yourself: if there were 500 events, you would not paste all of them — that question is why step 4 exists.

---

## Step 4 — One read tool and a hand-written loop

**Goal.** The model no longer receives the whole calendar in the prompt. It *requests* `get_agenda`, your code runs a Python function, you send the result back. This is the agent loop in [plan.md](plan.md): propose a tool call → execute a deterministic tool.

### Read first

1. [Function calling (Interactions API)](https://ai.google.dev/gemini-api/docs/function-calling) — declarations, `function_call` steps, `function_result` with **both** `call_id` and `name`.
2. [Quickstart §9, “Call your own functions”](https://ai.google.dev/gemini-api/docs/interactions/quickstart) — the `while True` + `previous_interaction_id` pattern. That snippet is the loop you will adapt.
3. [JSON schema from Pydantic](https://docs.pydantic.dev/latest/concepts/json_schema/) — `model_json_schema()`, so you do not hand-write parameter schemas.

Facts to extract:

- The model never runs your function. It emits a `function_call` step. You run Python. You reply with a `function_result`.
- Every result must include `name` and `call_id` (the call’s `step.id`).
- Continue with `previous_interaction_id=interaction.id`.

### Do

1. Add `src/bifrost/views.py` — the **whitelisted** shape the model is allowed to see. Start with a subset of `CalendarEvent` (id, title, start, end, location). A tool returns this, not the ORM row, not a bare dict of whatever SQLite gave you.

2. Add `src/bifrost/tools.py`:

   ```python
   def get_agenda(*, now: datetime, events: list[CalendarEvent]) -> list[AgendaEvent]:
       """Events whose interval intersects [now - 2h, now + 36h]."""
   ```

   Filter in Python. Convert each match to the view model. Serialize with `model_dump(mode="json", exclude_none=True)`.

3. Declare the tool for Gemini. Empty parameter object is fine for v1 (`now` is injected by your code, not by the model):

   ```python
   GET_AGENDA = {
       "type": "function",
       "name": "get_agenda",
       "description": "Return calendar events around the current time. Call this to answer questions about today's schedule.",
       "parameters": {"type": "object", "properties": {}},
   }
   ```

4. Add `src/bifrost/loop.py` following the quickstart while-loop:

   - Call `client.interactions.create(..., tools=[GET_AGENDA], previous_interaction_id=...)`.
   - For each `step.type == "function_call"`, dispatch on `step.name`, run the Python function, append a `function_result`.
   - Cap at ~8 model calls. If the cap hits, stop and tell the user the budget was spent.
   - Print usage after every `create`.

5. System instruction: you have tools; do not invent events; cite ids from tool results only. Do **not** paste the seed JSON into the prompt anymore.

### Done when

```bash
uv run bifrost
```

with question `"What's on today?"` produces a `get_agenda` call in the log, then an answer that cites real ids. A second question `"Do I have lunch plans?"` also goes through the tool, not through memorized prompt context.

---

## Step 5 — A real chat CLI

**Goal.** `uv run bifrost chat` is a multi-turn conversation. This is the surface you will keep through the rest of the roadmap.

### Read first

- [Interactions overview](https://ai.google.dev/gemini-api/docs/interactions-overview) — an interaction is a turn; `previous_interaction_id` chains turns.
- Python [`argparse`](https://docs.python.org/3/library/argparse.html) if you do not already know it.

### Do

1. Split CLI from library code. `pyproject.toml` already has `bifrost = "bifrost:main"`. `main` should parse subcommands.

2. `bifrost chat` :

   - Read lines from stdin until EOF or an empty line / `/quit`.
   - Each user line is one outer turn of the step-4 loop.
   - Thread `previous_interaction_id` across user turns as well as tool turns.
   - Accept `--now 2026-09-11T08:30:00-04:00` (default `SEED_NOW`).
   - Print the assistant text, then usage.

3. Keep `thinking_level="low"` until step 9.

### Done when

You can have this conversation without restarting:

1. “What’s on today?”
2. “Which of those conflicts with lunch?”
3. “What goals am I tracking?” (may be empty or wrong until step 7 — that is expected)

---

## Step 6 — Move records into SQLite

**Goal.** Structured truth lives in a database your tools query. The model still only sees view models.

### Read first

1. [`sqlite3` module](https://docs.python.org/3/library/sqlite3.html) — connections, `execute`, placeholders (`?`), `row_factory = sqlite3.Row`.
2. [SQLite date/time datatypes](https://www.sqlite.org/datatype3.html) — there is no native datetime; store ISO-8601 UTC text.
3. [CREATE TABLE](https://www.sqlite.org/lang_createtable.html) and [CREATE INDEX](https://www.sqlite.org/lang_createindex.html).

### Do

1. Add `src/bifrost/store.py` (or `store/schema.sql` plus a small opener).

   Tables, v1:

   ```sql
   CREATE TABLE IF NOT EXISTS events (
     id TEXT PRIMARY KEY,
     title TEXT NOT NULL,
     start_utc TEXT NOT NULL,
     end_utc TEXT NOT NULL,
     location TEXT,
     description TEXT
   );
   CREATE TABLE IF NOT EXISTS tasks (
     id TEXT PRIMARY KEY,
     title TEXT NOT NULL,
     due_utc TEXT,
     status TEXT NOT NULL,
     notes TEXT
   );
   CREATE TABLE IF NOT EXISTS goals (
     id TEXT PRIMARY KEY,
     title TEXT NOT NULL,
     status TEXT NOT NULL
   );
   ```

2. `open_db(path) -> sqlite3.Connection` with `row_factory = sqlite3.Row`. Default path: `data/bifrost.db` (create `data/`, add `data/` to `.gitignore` except maybe a README).

3. `seed_db(conn)` inserts `SEED_*` using `INSERT OR REPLACE`. Convert `start`/`end`/`due` with `.astimezone(UTC).isoformat()`.

4. Rewrite `get_agenda` to take `conn` and `now`, and run SQL:

   ```sql
   SELECT * FROM events
   WHERE start_utc < ? AND end_utc > ?
   ORDER BY start_utc
   ```

   Bind the ISO strings for `now + 36h` and `now - 2h`. Map rows → `CalendarEvent` (or directly to the view model). Do not `SELECT *` into the prompt; always go through the view.

5. CLI: on startup, open the db, seed if empty, pass `conn` into the tool functions. `now` still comes from `--now`.

### Done when

```bash
uv run python -c "
from datetime import timedelta
from bifrost.store import open_db, seed_db
from bifrost.seed import SEED_NOW
from bifrost.tools import get_agenda
conn = open_db(':memory:')
seed_db(conn)
rows = get_agenda(conn=conn, now=SEED_NOW)
print([r.id for r in rows])
"
```

Ids match the seed events that fall in the window. `uv run bifrost chat` still answers “what’s on today?” but now the tool hits SQLite.

---

## Step 7 — The rest of the read tools (five or fewer)

**Goal.** Match the vision’s first useful version: conversation about obligations, conflicts, and goals, with a small read-tool set. No writes.

### Read first

- [SQLite FTS5](https://www.sqlite.org/fts5.html) — only the intro and a simple `CREATE VIRTUAL TABLE ... USING fts5(title, body)` plus `MATCH`. Skip if you want `LIKE` for v1; FTS5 is the search the vision implies for local records.
- Function-calling docs from step 4, for declaring additional tools.

### Do

Register **at most five** tools. Suggested set, matching [plan.md](plan.md):

| Tool | Returns | Query |
|---|---|---|
| `get_agenda` | events in the time window | already done |
| `get_tasks` | open tasks due within 14 days of `now`, plus any without a due | SQL on `tasks` |
| `get_goals` | active goals | SQL on `goals` |
| `search_records` | mixed hits | FTS5 or `LIKE` on title/description; args: `query: str`, optional `kind: event\|task\|goal` |
| `get_source_health` | stub | Return `[{"source": "seed", "status": "ok", "last_success_at": ...}]` until step 10 |

Declare each with a one-sentence description so the model can choose. Implement handlers that return view models.

For `search_records` parameters, define a Pydantic args model and pass `YourArgs.model_json_schema()` into the tool’s `parameters` (see [JSON schema](https://docs.pydantic.dev/latest/concepts/json_schema/)). Keep the model flat: strings, ints, literals — no nested unions.

Dispatch in the loop with a dict `name -> handler`. Unknown names return a tool error string, not an exception that kills the turn.

### Done when

In one `bifrost chat` session, these questions work without inventing records:

- “What’s on today?” → `get_agenda`
- “What tasks are due?” → `get_tasks`
- “What am I aiming at?” → `get_goals`
- “Search for Priya” (or a word in your seed) → `search_records`

Log the tool names so you can see selection mistakes. Wrong tool choice is normal; do not “fix” it with a paragraph of prompt if a clearer tool description will do.

---

## Step 8 — Conflicts computed in code

**Goal.** Overlap detection is a fact the tool returns, not a judgment the model makes. This is the vision’s “push determinism into tools.”

### Read first

- Interval overlap: two half-open ranges `[a, b)` and `[c, d)` overlap iff `a < d and c < b`.
- Re-read the `get_agenda` SQL and your event view model.

### Do

1. Treat events as half-open `[start, end)`. Back-to-back meetings do not conflict.
2. In `get_agenda` (Python is fine; SQL window functions are optional), compute a `conflicts` list of `{event_id, other_id}` pairs for overlapping events in the window.
3. Add `conflicts` to the **tool result** (a small Pydantic model, e.g. `AgendaResult(events=..., conflicts=...)`), not as a side channel in the system prompt.
4. You already seeded an overlap in step 2. If you did not, add one now and re-seed.

### Done when

Question: “Do I have any conflicts today?”

The tool payload contains the overlapping pair. The model’s answer names both ids. Run it three times — it should not flap, because the overlap is data.

---

## Step 9 — Proposed daily plan with citations

**Goal.** The assistant can propose a plan whose every citation resolves to a real, in-context record. This is an explicit item in the first useful version.

### Read first

1. [Structured outputs](https://ai.google.dev/gemini-api/docs/structured-output) — `response_format` with `schema: YourModel.model_json_schema()`. On the Interactions API you pass the schema dict, not the Pydantic class.
2. Pydantic [validators](https://docs.pydantic.dev/latest/concepts/validators/) again, for the plan checker.
3. Switch this route to `thinking_level="high"` ([thinking levels](https://ai.google.dev/gemini-api/docs/function-calling) / generation_config). Planning is the first task that needs it.

### Do

1. Define `PlanBlock` and `DailyPlan` in `src/bifrost/plan_schema.py`:

   ```python
   class PlanBlock(BaseModel):
       start: datetime
       end: datetime
       title: str
       record_ids: list[str]  # evt_ / task_ / goal_ the block is based on
       rationale: str

   class DailyPlan(BaseModel):
       blocks: list[PlanBlock]
   ```

2. Add a **read** tool `propose_daily_plan` **or** (cleaner) keep planning as: model calls the read tools, then you request a structured final answer. Simplest product path:

   - After the normal tool loop, if the user asked for a plan, make one extra `interactions.create` with `response_format` set to `DailyPlan.model_json_schema()` and `thinking_level="high"`.
   - Parse with `DailyPlan.model_validate_json(interaction.output_text)`.

3. Write `validate_plan(plan, conn, exposed_ids: set[str]) -> list[str]`:

   - Every `record_ids` entry exists in the database.
   - Every cited id was in `exposed_ids` (ids returned by tools this turn — collect them in the loop).
   - Blocks do not overlap each other or busy events (reuse step 8).
   - `end > start`.

   If errors exist, send them back to the model once as text (“block 2 cites evt_999 which does not exist”) and retry structured output. If it still fails, show the plan with invalid citations stripped and a warning.

4. Persist nothing to the calendar. A proposal is data you print (and later store as a proposal row if you want). It is not a write to `events`.

### Done when

“Plan my afternoon” yields blocks that only cite ids you can `SELECT` from the db. Manually breaking a citation in a unit test (no model required):

```bash
uv add --dev pytest
```

```python
# tests/test_validate_plan.py
def test_unknown_id_is_rejected():
    plan = DailyPlan(blocks=[PlanBlock(..., record_ids=["evt_does_not_exist"], ...)])
    errors = validate_plan(plan, conn, exposed_ids={"evt_001"})
    assert errors
```

`uv run pytest` passes. The live chat path also rejects a hallucinated id at least once — if the model never hallucinates in your trials, the unit test still covers the rule.

---

## Step 10 — Ingest outside the model loop

**Goal.** A separate program parses a file into the same record models and upserts SQLite. The agent never sees the file. This is the vision’s “does not fetch or parse provider JSON inside the model loop.”

### Read first

1. [iCalendar primer](https://icalendar.org/iCalendar-RFC-5545/3-6-1-event-component.html) — `VEVENT`, `DTSTART`, `DTEND`, `UID`. Enough to know why this is a wire format, not your store.
2. Pick **one** parser and read its getting-started page. [`icalendar`](https://icalendar.readthedocs.io/en/latest/) is the usual choice. Add it with `uv add icalendar` when you start this step.
3. Your `CalendarEvent` model — the parser’s job is to produce instances of it.

Do not give the model a tool that `Path.read_text()`s the `.ics`.

### Do

1. Add tables `sources` and `sync_runs`:

   ```sql
   CREATE TABLE IF NOT EXISTS sources (
     id TEXT PRIMARY KEY,
     kind TEXT NOT NULL,       -- 'seed' | 'ics' | 'markdown'
     path TEXT,
     trust TEXT NOT NULL       -- 'trusted' | 'untrusted'
   );
   CREATE TABLE IF NOT EXISTS sync_runs (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     source_id TEXT NOT NULL,
     started_at TEXT NOT NULL,
     finished_at TEXT,
     rows_upserted INTEGER,
     error TEXT
   );
   ```

   Seed data’s source id is `src_seed`, `trust='trusted'`.

2. Put a sample calendar at `fixtures/sample.ics` (export from Google/Apple or write a minimal VEVENT by hand). Mark that source `untrusted` if it is an export you do not fully control; a file you authored can be `trusted`.

3. `src/bifrost/sync.py` (import nothing from `loop.py` / `tools.py`):

   - Read the file.
   - Parse VEVENTs into `CalendarEvent` (one occurrence each; skip RRULE expansion in v1, or import only the next occurrence).
   - Upsert by id. Derive ids deterministically, e.g. `evt_` + a slug of the UID, so a re-sync updates the same row.
   - Write a `sync_runs` row, success or failure.

4. CLI: `uv run bifrost sync` runs ingest only. Then `uv run bifrost chat` answers from the updated db.

5. Implement `get_source_health` for real: latest `sync_runs.finished_at` per source. If older than 24h (or never synced), status `stale`. The chat system instruction: if any source is stale, say so before asserting facts from it.

### Done when

```bash
uv run bifrost sync
uv run bifrost chat --now 2026-09-11T08:30:00-04:00
```

A new event from the file appears via `get_agenda`. Killing Gemini and running `sync` still updates the db. `get_source_health` reports the file source.

---

## Step 11 — Audit log and `trace`

**Goal.** You can reconstruct a turn without re-reading chat scrollback. The vision’s loop ends with “persist an audit event.”

### Read first

- [SQLite transactions](https://www.sqlite.org/lang_transaction.html) — one connection, `BEGIN`/`COMMIT` around a turn is enough.
- Your loop: every branch that calls the model, a tool, or the citation validator.

### Do

1. Table `audit_events`:

   ```sql
   CREATE TABLE IF NOT EXISTS audit_events (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     turn_id TEXT NOT NULL,
     step_key TEXT NOT NULL,
     kind TEXT NOT NULL,          -- model_call | tool_call | tool_result | plan_validation | error
     payload_json TEXT NOT NULL,  -- already-redacted view, never secrets
     usage_json TEXT,
     created_at TEXT NOT NULL,
     UNIQUE (turn_id, step_key)
   );
   ```

   The unique pair makes a retried append a no-op.

2. `append_audit(conn, turn_id, step_key, kind, payload, usage=None)`. Generate `turn_id` once per user message (e.g. `uuid4()`).

3. Call it from the loop: before/after model calls, on each tool call and result, on plan validation errors.

4. `uv run bifrost trace <turn_id>` prints the rows in order. List recent turn ids with `uv run bifrost trace --last`.

Keep audit in `bifrost.db`. Do not log API keys, `.env`, or raw `.ics` text.

### Done when

One chat turn, then `bifrost trace` on that turn, shows the `get_agenda` call, its result ids, and the model’s final text (or a hash/length of it). You can answer “which tool ran?” from the log alone.

---

## Step 12 — Confirmed writes

**Goal.** The assistant can create a time block and complete a task, and nothing leaves the machine until you approve the exact payload. First useful version: “no unapproved changes.”

### Read first

- [`hashlib.sha256`](https://docs.python.org/3/library/hashlib.html) and [`json.dumps(..., sort_keys=True)`](https://docs.python.org/3/library/json.html) for a canonical payload hash.
- Your tool dispatch — this is where the gate lives (a wrapper, not a sentence in the system prompt).

### Do

1. Add tools, classed as **external action** even though they write locally:

   - `create_time_block(title, start, end)` → insert an `events` row with a new `evt_…` id.
   - `complete_task(task_id)` → set `status='done'` if the id exists.

2. Before executing either tool:

   - Validate args with a Pydantic model.
   - Print a preview (title, local times, hash).
   - `input("Approve this action? [y/N] ")`.
   - Compute `sha256` of `{"tool": name, "args": normalized_args}`. Store the hash with the preview. On yes, recompute and refuse if it differs (your process did not mutate args; this still documents the rule and will matter if the CLI ever becomes two processes).

3. After a successful write: `SELECT` the row back and assert title/times/status match. Append audit `tool_result` including the new id.

4. Record an inverse in audit or a small `actions` table: deleting that event, or setting the task back to `todo`. `uv run bifrost undo` can wait; having the inverse recorded is enough for this step.

5. Reads stay auto-approved. `propose_daily_plan` does not write `events`.

Do not implement LangGraph `interrupt()` here. A CLI confirm is the v1 gate. Durable pause-across-process-crash is extra machinery, not required for the vision’s first useful version.

### Done when

- “Block 3–4pm for deep work” pauses, shows a preview, and inserts a row only after `y`.
- Answering `n` inserts nothing.
- “Mark task_001 done” updates one row after confirm.
- `get_agenda` / `get_tasks` then reflect the change.
- Audit contains the approval decision.

---

## Step 13 — Widgets (first useful version)

**Goal.** The model arranges a display by emitting a validated spec. A small web page renders 2–5 prebuilt widgets. The model never emits HTML.

### Read first

1. [FastAPI first steps](https://fastapi.tiangolo.com/tutorial/first-steps/) and [HTML Response](https://fastapi.tiangolo.com/advanced/custom-response/#html-response) — enough to serve one page.
2. Pydantic models (you already know these) for `WidgetSpec`.
3. Optional: [MDN template literals / DOM](https://developer.mozilla.org/en-US/docs/Web/API/Document_Object_Model/Introduction) if you write a few lines of JS. Keep the page dependency-free; no Node, no React.

`uv add fastapi uvicorn` at the start of this step.

### Do

1. `src/bifrost/surface.py`:

   ```python
   WidgetType = Literal["agenda_timeline", "task_list", "plan_review"]

   class WidgetSpec(BaseModel):
       type: WidgetType
       title: str
       record_ids: list[str]
   ```

   Three widgets is enough (vision: 2–5). Add `source_health` or `goal_tracker` only if the first three render.

2. Tool `set_surface(widgets: list[WidgetSpec])` — derived write: validate specs, resolve every `record_id` from SQLite in **the renderer**, refuse unknown ids, save JSON to a `surface_state` table (single row, or versioned if you want undo). Confirm like step 12, or auto-run if you treat layout as reversible local state; if you auto-run, still audit.

3. `src/bifrost/api.py`: `GET /` returns HTML. Server-side, load surface state, load records by id, fill a simple template (agenda as a list of time + title, tasks as checkboxes that are display-only). Strings are text-escaped, never inserted as HTML.

4. `uv run bifrost serve` runs uvicorn on loopback. Open the page in a browser.

### Done when

In chat: “Show my afternoon on the board.” After the surface tool runs, refreshing `http://127.0.0.1:8000` shows those events. A fabricated id in the spec never appears as a fake title; the renderer only prints rows it loaded from the db.

---

## Step 14 — One real external action

**Goal.** One allowlisted action that leaves the assistant’s database. Everything around it already exists: confirm, hash, audit, read-back where possible.

### Read first

- WSL launching a Windows app: `cmd.exe /c start "" "path or protocol"` — only if you actually need a Windows binary. Prefer `xdg-open` for a URL or a Linux app under WSLg.
- Your step-12 gate — reuse it, do not add a second permission path.

### Do

1. `open_app(name: str)` with a **literal allowlist** in code, e.g. `{"calendar": "...", "notes": "..."}`. Unknown names deny.

2. Same confirm + hash as writes. Audit the spawn. There is no meaningful read-back for `open_app`; record stdout/returncode.

Skip OAuth calendar providers for v1. A local confirmed insert plus `open_app` satisfies “confirmed control of a few applications.”

### Done when

“Open my notes app” prompts, then launches only if `notes` is allowlisted. “Open /bin/bash” (or any non-allowlisted name) is denied and audited.

---

## Mapping onto the vision

| First useful version ([plan.md](plan.md)) | Steps that create it |
|---|---|
| Conversation about today’s obligations, conflicts, and goals | 3–8 |
| Five or fewer read tools | 4, 7 |
| Proposed daily plan with citations | 9 |
| No unapproved changes | no write tools until 12; confirm + hash there |
| 2–5 prebuilt widgets | 13 |
| Deterministic ingest, not in the model loop | 10 |
| Agent loop with audit | 4–5, 11 |

You have a working product at the end of step 13. Step 14 is the first action that leaves the process.

## Out of scope until the product exists

Do not pull these in because the sample architecture mentions them:

- LangGraph / LangChain / checkpointers
- Hash-chained audit, thought signatures, `allOf` schema lint
- RAG / embeddings for calendar or tasks
- OAuth Google/Outlook connectors
- Prompt-injection red team (worth doing after step 13; untrusted notes from step 10 are the fixture)

If a step feels like it needs a framework, finish the step with the Interactions API loop you already have. The loop in step 4 *is* the agent.
