# Plugin Template

LPRD plugin template with a built-in event-driven state machine for managing plugin lifecycle (registration, authentication, data sync).

## Architecture

The template uses a Boost.MSM-inspired state machine library (`app/statemachine/`) with decorator-based handler registration and FastAPI-style dependency injection.

### Machine Hierarchy

```
core (BOOT | RUNNING | EXIT)
├── BOOT
│   ├── boot: LOAD_CONFIG → REGISTER → STORE_CREDENTIALS → VERIFY_AUTH → READY
│   └── boot_error: OK | REGISTRATION_FAILED | STORAGE_FAILED | AUTH_FAILED
└── RUNNING
    ├── running: IDLE → FETCHING → PUSHING → IDLE
    └── running_error: OK | FETCH_FAILED | PUSH_FAILED
```

### Key Concepts

- **Events carry data** — no shared mutable state between handlers
- **Decorator API** — `@region.on(EventType, source="S", target="T")` registers handlers
- **DI via `Depends`** — handlers declare dependencies with `Annotated[T, Depends(callable)]`
- **Forwarded events** — handler returns chain transitions (e.g. return `("TARGET", SomeEvent(...))`)
- **Error recovery** — `SubregionError` bubbles up to core, which handles retries (boot) or recovery (operate)

## Endpoints

- `GET /health` — Health check (machine snapshot)
- `GET /config/schema` — Configuration JSON Schema
- `POST /config` — Update runtime config (e.g. reschedule interval)

## Development

- `poe run` — Start plugin server on port 8001
- `poe format` — Format code with black and isort
- `poe lint` — Lint code with black, isort, ty, and ruff

## Configuration

Set environment variables in `.env`:

```env
LOG_LEVEL=INFO
PLUGIN_NAME=lprd-plugin-v1
REGISTRY_URL=https://your-lprd-instance.example.com
PLUGIN_BASE_URL=http://localhost:8001
REGISTRATION_KEY=your-registration-key
SYNC_INTERVAL_MINUTES=60
DATABASE_URL=sqlite+aiosqlite:///data/plugin.db
```
