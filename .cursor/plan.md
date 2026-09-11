# Personal assistant — plan

The product is a **custom personal assistant**: conversation, search, planning across local facts, and confirmed control of a few applications.

## Source of truth

| Question | Canonical doc |
|---|---|
| Project vision | This file |
| Retired Roadmap | [roadmap](roadmap.md) |
| Learning roadmap | [build roadmap](build-roadmap.md) |
| Sample architectural plan (not being implemented) | [agent plan](./plans/bifrost_agentic_assistant_72142ad7.plan.md) | 

## Goal

A desktop assistant that can:

- discuss tasks, calendar, ingested information, and goals in conversation.
- search local structured records (later files), deterministically ingest online sources.
- propose a daily plan with citations to source records.
- take a small set of reversible, confirmed actions (create a time block, complete a task, open an app)
- manipulate a desktop for display and UI, structured around widgets which are created in a structured format.

It does **not** fetch or parse provider JSON inside the model loop. It does **not** use RAG as the source of calendar, task, or other structured truth.

## Agent loop

Every capability uses: observe local state → reason over scoped context → propose a tool call or plan → permission check → execute a deterministic tool → read back and verify → persist an audit event.

| Class | Examples | Default policy |
|---|---|---|
| Read | `search_records`, `get_agenda`, `get_source_health`, `get_goals` | Automatic |
| Derived write | `propose_daily_plan`, save a note | Audited; reversible |
| External action | create event, complete task, open app, edit file | Confirm; allowlisted; idempotent where possible |

SQL, raw JSON, and secrets never enter the prompt. Ingested documents and web content are untrusted.

## First useful version

- Conversation about today’s obligations, conflicts, and goals
- Five or fewer read tools
- A proposed daily plan with citations
- No unapproved changes
- Ability to manipulate a set of 2-5 prebuilt widgets.