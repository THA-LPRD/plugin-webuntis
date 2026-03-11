# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LPRD WebUntis plugin. Fetches timetable data from WebUntis via anonymous auth and pushes it to the LPRD registry per configured room with slot-based TTL scheduling.

## Technology Stack

- **Python**: 3.14+ (managed with uv)
- **Framework**: FastAPI
- **State Machine**: Custom Boost.MSM-inspired library (`app/statemachine/`)
- **DI**: FastAPI-style `Annotated[T, Depends(callable)]` for handler injection
- **Database**: SQLAlchemy async with SQLite
- **Configuration**: Pydantic Settings with .env file support
- **Logging**: Loguru
- **Scheduler**: APScheduler (per-room jobs)
- **WebUntis**: Custom async HTTP client with anonymous JSONRPC auth (`app/untis/client.py`)
- **Containerization**: Docker & Docker Compose

## Development Commands

- `poe run` - Start plugin server on port 8001 [Note: Don't use this unless otherwise told to]
- `poe format` - Format code with black and isort
- `poe lint` - Lint code with black --check, isort --check, ty check, and ruff check
- `uv run python fetch.py rooms` - List all WebUntis rooms
- `uv run python fetch.py fetch <ROOM> [-d YYYY-MM-DD] [-o file.json]` - Fetch timetable for a room

**Do not run:** `poe run` (assume already running)

## Architecture

### State Machine Library (`app/statemachine/`)

Boost.MSM-inspired event-driven state machine. Core concepts:

- **Region**: The machine itself. Holds states, rows (transitions), and submachines. Definition via decorators (`@region.on()`, `region.route()`, `region.defer()`).
- **Event**: Base class. Subclass with `__init__` fields for typed data. Events carry all data forward — no shared mutable state.
- **Row**: Internal transition record (source, event type, target, action, guard).
- **State**: Frozen model with name and optional deferred event types.
- **Depends**: DI framework. Handlers declare dependencies via `Annotated[T, Depends(callable)]`. Resolved by `resolve_and_call()` at runtime.
- **SubregionComplete / SubregionError**: Library events for submachine lifecycle.
- **MachineError**: Wraps handler exceptions, carries `trigger` (the event being processed when the error occurred).

**Action return semantics:**
- `None` — use Row's fixed target, no forwarded event
- `"TARGET"` — dynamic target override
- `SomeEvent(...)` — use Row's target, forward event after transition
- `("TARGET", SomeEvent(...))` — dynamic target + forwarded event

### Machine Hierarchy (`app/machines/`)

```
core (Region: BOOT | RUNNING | EXIT)
├── BOOT (submachine)
│   ├── boot (Region: LOAD_CONFIG → REGISTER → STORE_CREDENTIALS → VERIFY_AUTH → CREATE_TEMPLATE → READY)
│   └── boot_error (Region: OK | REGISTRATION_FAILED | STORAGE_FAILED | AUTH_FAILED | TEMPLATE_FAILED)
└── RUNNING (submachine)
    ├── running (Region: IDLE → FETCHING → PUSHING → IDLE)
    └── running_error (Region: OK | FETCH_FAILED | PUSH_FAILED)
```

- **PluginMachine** (`plugin_machine.py`): Thin async facade. Owns the event queue and per-room schedulers. No domain logic.
- **Core** (`core/machine.py`): Top-level region. Wires submachines, handles `SubregionError` for both boot (with retry) and operate (with recovery to IDLE).
- **Boot** (`core/boot/`): Registration + auth + template creation flow. Retry count flows through events as `retries_remaining`.
- **Operate** (`core/operate/`): Per-room Tick → Fetch → Push cycle. Ticks are deferred during FETCHING/PUSHING so room ticks queue up.

### WebUntis Integration (`app/untis/`)

- **client.py**: Async HTTP client using anonymous JSONRPC auth (no credentials needed, fixed OTP `100170`)
- **models.py**: Pydantic models for WebUntis API responses (`UntisPeriod`, `UntisElement`, etc.)
- **timetable.py**: Transforms `UntisPeriod` lists into room payloads — merges continuous lessons, inserts free-period breaks, computes current slot and TTL

### Per-Room Scheduling

Each configured room gets its own APScheduler job (`sync_<room>`). After each push:
1. Compute seconds until the current slot ends for that room
2. Reschedule that room's job to fire at the slot boundary
3. On wake: re-fetch from WebUntis, determine new current slot, push with new TTL

### Template Registration (`templates/`)

During boot, the plugin scans `TEMPLATE_DIR` (default: `templates/`) for subdirectories. Each subdirectory is a template:

```
templates/
  <template-name>/
    metadata.json      ← name, description, version, variants, preferred_variant_index
    template.html      ← Jinja/Nunjucks HTML template
    sample_data.json   ← (optional) sample data for preview
```

### Key Design Principles

1. **All transitions are event-driven** — no auto/anonymous transitions
2. **Events carry data** — no shared mutable state between handlers
3. **Data flows forward** — each handler passes relevant data to the next event
4. **Retry via events** — `retries_remaining` field on boot events, preserved across error boundary via `MachineError.trigger` → `SubregionError.trigger`
5. **Dependencies defined where used** — `Annotated` type aliases next to the handlers that use them
6. **No code in `__init__.py`** beyond re-exports
7. **Internal machines not exposed** — only `core`, `MachineSnapshot`, and `snapshot()` exported from `core/`

### Plugin Protocol Endpoints

- `GET /health` - Health check (returns machine snapshot)
- `GET /config/schema` - Configuration JSON Schema
- `POST /config` - Update runtime config

## Code Style Guidelines

### Comments Policy

- **NEVER use comments that simply restate the code**
- **Use logging instead of comments for explaining flow**
- **Only use comments for**: non-obvious business logic, workarounds, TODOs

## Important Notes

- The project uses `uv` for dependency management instead of pip/poetry
- Never touch internal region state (e.g. `region._current`) — always go through the event-driven API
- WebUntis uses anonymous auth — no API credentials needed
