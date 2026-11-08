# AtsCore Backend

Distributed high-throughput backend engine for Master Sheet data and telecom bot operations.

---

## Tech Stack

- **Backend:** Flask, Gunicorn
- **Database:** PostgreSQL 16
- **Cache:** DragonflyDB v2.1 (Redis wire-compatible)
- **Containerization:** Docker & Docker Compose

---

## Quick Start (Docker)

Start all services (PostgreSQL, DragonflyDB, and Flask Backend):

```bash
docker compose up -d --build
```

Check service status:

```bash
docker compose ps
```

Health check:

```bash
curl http://localhost:8000/health
```

Stop services:

```bash
docker compose down
```

---

## Configuration

Copy `.env.example` to `.env` and adjust settings as needed:

```ini
PORT=8000
HOST=0.0.0.0
FLASK_ENV=production
SECRET_KEY=ats_enterprise_secret_key_secure_2026

# PostgreSQL
PG_HOST=127.0.0.1
PG_PORT=5433
PG_DATABASE=ats_recovery_db
PG_USER=postgres
PG_PASSWORD=ats_enterprise_pg_pass_2026

# DragonflyDB
DRAGONFLY_HOST=127.0.0.1
DRAGONFLY_PORT=6380
DRAGONFLY_DB=0
DRAGONFLY_POOL_DB=1
```

*Note: When running with Docker, host ports are mapped to `5433` (Postgres) and `6380` (DragonflyDB) to avoid conflicts.*

---

## Project Structure

```text
AtsCore/
├── app/
│   ├── cache/          # DragonflyDB cache client and distributed locks
│   ├── database/       # PostgreSQL connection pool and schema
│   ├── routes/         # API blueprints (sheets, rows, cells, dispatch, dashboard)
│   ├── services/       # Business logic (row, sheet, dispatch, dashboard)
│   ├── config.py       # Application configuration
│   └── __init__.py     # Flask app factory
├── scripts/            # Database migration and connection test scripts
├── docker-compose.yml  # Multi-container orchestration
├── Dockerfile          # Container build definition
├── manage.py           # CLI management entrypoint
└── requirements.txt    # Python dependencies
```

---

## Management CLI

Run CLI commands directly or inside Docker:

```bash
# Inside Docker container
docker compose exec backend python manage.py test-connections
docker compose exec backend python manage.py init-db

# Locally
python manage.py runserver
python manage.py test-connections
python manage.py init-db
python manage.py migrate-sqlite "path/to/source.db"
```

---

## Core API Endpoints

### System & Health
- `GET /health` - System health and database/cache latency
- `GET /api/dragonfly_status` - DragonflyDB cache telemetry
- `GET /api/benchmark` - Cache pipeline benchmark

### Dashboard & Analytics
- `GET /api/dashboard_stats` - Master stock summary, KPI cards, and operator breakdown
- `GET /api/sheet_xray?sheet_id=1` - Category and operator breakdown for a sheet

### Sheets & Rows
- `GET /api/sheets` - Metadata for all sheets
- `GET /api/rows?sheet_id=1&offset=0&limit=1000` - Paginated row records and cell styles
- `POST /api/update_cell` - Update a single cell value
- `POST /api/batch_update_cells` - Batch cell update
- `POST /api/update_styles` - Update cell background color and styles

### Telecom Bot Dispatch
- `GET /api_dispatch.php?action=pool_counts_quick` - Available number counts
- `GET /api_dispatch.php?action=fetch_pool&circle=<circle>&carrier=<carrier>` - Lease numbers
- `POST /api_dispatch.php?action=report_outcome` - Report bot execution outcome
