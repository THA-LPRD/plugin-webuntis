# WebUntis Plugin

LPRD plugin that fetches timetable data from WebUntis and pushes it to the LPRD app with slot-based TTL scheduling.

## Architecture

Based on the [plugin-template](../plugin-template), using a Boost.MSM-inspired state machine for lifecycle management.

### Machine Hierarchy

```
core (BOOT | RUNNING | EXIT)
├── BOOT
│   ├── boot: LOAD_CONFIG → BOOTSTRAP → VERIFY_AUTH → CREATE_TEMPLATE → FETCH_SITES → READY
│   └── boot_error: OK | BOOTSTRAP_FAILED | AUTH_FAILED | TEMPLATE_FAILED
└── RUNNING
    ├── running: IDLE → FETCHING → PUSHING → IDLE (per-room, deferred ticks)
    └── running_error: OK | FETCH_FAILED | PUSH_FAILED
```

### WebUntis Integration

- Anonymous auth via internal JSONRPC endpoint (no API credentials needed)
- Pydantic models for API response validation (`UntisPeriod`, `UntisElement`)
- Timetable transformation: merge continuous lessons, insert free-period breaks, group by weekday

### Per-Room Scheduling

Each room gets its own scheduler job. After each push, the job is rescheduled to fire at the current slot's end time. This ensures data is refreshed exactly when the displayed lesson changes.

### Templates

Display templates live in `templates/`:

```
templates/
  room-timetable/
    metadata.json
    template.html
    sample_data.json
```

## Endpoints

- `GET /health` — Health check (machine snapshot)
- `GET /config/schema` — Configuration JSON Schema
- `POST /config` — Update runtime config

## CLI

```bash
uv run python fetch.py rooms                         # List all rooms
uv run python fetch.py fetch M1.02                    # Fetch current week
uv run python fetch.py fetch M1.02 -d 2026-03-16     # Specific week
uv run python fetch.py fetch M1.02 -o output.json    # Save to file
```

## Development

- `poe run` — Start plugin server on port 8001
- `poe format` — Format code with isort and Black
- `poe lint` — Check isort, Black, ty, and Ruff

## Configuration

Set environment variables in `.env`:

```env
LOG_LEVEL=INFO
CORE_URL=http://localhost:3000
WORKOS_AUTHKIT_DOMAIN=https://your-authkit-domain.authkit.app
CLIENT_ID=client_...
CLIENT_SECRET=secret_...
DATABASE_URL=sqlite+aiosqlite:///data/plugin.db
PLUGIN_BASE_URL=http://localhost:8001
SYNC_INTERVAL_MINUTES=60
HEALTH_CHECK_INTERVAL_MS=30000
TEMPLATE_DIR=templates

# WebUntis
UNTIS_SERVER=https://tha.webuntis.com
UNTIS_SCHOOL=tha
UNTIS_ROOMS=E5.01,M1.02,C1.22
```
