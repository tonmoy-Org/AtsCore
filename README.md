# ⚡ AtsCore — Enterprise Backend

High-throughput, distributed backend engine for Master Sheet & Telecom Verification Operations.

---

## 🏗 Architecture & Technology Stack

| Layer | Technology | Role & Capability |
| :--- | :--- | :--- |
| **Main Database** | **PostgreSQL 16** | Persistent ACID storage for sheets metadata, 8.9M+ cell styles, dynamic sheet tables, and audit logs. |
| **Cache Database** | **DragonflyDB v2.0+** | Sub-millisecond L1 JSON cache, atomic distributed locks (`SET NX PX` + Lua), and auto-pipelining. |
| **Backend Engine** | **Flask + Gunicorn** | Modular Blueprints, connection pooling (`ThreadedConnectionPool`), and high-concurrency API routes. |
| **Deployment** | **Docker & Compose** | Containerized multi-service orchestration with healthchecks and persistent volumes. |

---

## 📁 Directory Structure

```
E:\Biraz Ali\AtsCore\
├── docker-compose.yml          # Multi-container orchestration (PostgreSQL 16 + DragonflyDB + Flask)
├── Dockerfile                  # Production container image with Gunicorn
├── requirements.txt            # Python dependencies
├── .env.example / .env         # Configuration variables
├── manage.py                   # Unified CLI management entrypoint
│
├── app/
│   ├── __init__.py             # Application factory & CORS
│   ├── config.py               # Environment configuration
│   ├── database/
│   │   ├── connection.py       # ThreadedConnectionPool for PostgreSQL
│   │   ├── schema.py           # Enterprise DDL & dynamic sheet table generator
│   │   └── migrator.py         # Fast batched SQLite -> PostgreSQL ETL engine
│   ├── cache/
│   │   └── dragonfly.py        # DragonflyDB client, distributed locks, scan+unlink
│   ├── services/
│   │   ├── sheet_service.py    # Sheet metadata, duplication, freeze, merges
│   │   ├── row_service.py      # Pagination, batch updates, styling, sorting
│   │   ├── dispatch_service.py # Telecom bot pool leasing & outcome reporting
│   │   ├── operator_resolver.py# State & Telecom operator prefix rules
│   │   └── dashboard_service.py# Live inventory ledger & sheet x-ray
│   └── routes/
│       ├── sheets.py           # /api/sheets, /api/add_sheet, /api/rename_sheet...
│       ├── rows.py             # /api/rows, /api/insert_row, /api/delete_rows...
│       ├── cells.py            # /api/update_cell, /api/batch_update_cells...
│       ├── dispatch.py         # /api_dispatch.php, /telecom_pool_api...
│       ├── dashboard.py        # /health, /api/dashboard_stats, /api/sheet_xray...
│       └── export.py           # /api/export_tsv, /api/export_csv...
│
└── scripts/
    ├── migrate_from_sqlite.py  # Standalone SQLite to PostgreSQL migration script
    └── test_backend_connections.py # Connection health & pipeline benchmark tool
```

---

## 🚀 Quick Start with Docker (Recommended)

To run the entire stack (PostgreSQL + DragonflyDB + Flask Backend) in Docker:

```bash
cd "E:\Biraz Ali\AtsCore"
docker compose up -d --build
```

Check the health of all containers:
```bash
docker compose ps
curl http://localhost:8000/health
```

---

## 💻 Local Development Setup (Without Docker)

### 1. Install Dependencies
```bash
cd "E:\Biraz Ali\AtsCore"
pip install -r requirements.txt
```

### 2. Configure Environment
Update `.env` with your PostgreSQL and DragonflyDB credentials:
```ini
PG_HOST=127.0.0.1
PG_PORT=5432
PG_DATABASE=ats_recovery_db
PG_USER=postgres
PG_PASSWORD=your_postgres_password

DRAGONFLY_HOST=127.0.0.1
DRAGONFLY_PORT=6379
```

### 3. Initialize Database Schema
```bash
python manage.py init-db
```

### 4. Migrate Data from SQLite (`Fast_Excel_Sheet.db`)
Migrates all 62 sheets, metadata, styles, and inventory ledger:
```bash
python manage.py migrate-sqlite "E:\master_sheet\Fast_Excel_Sheet.db"
```

### 5. Start Backend Server
```bash
python manage.py runserver
```
The server will start on `http://127.0.0.1:8000`.

---

## 🌐 Core API Endpoints

### Health & Telemetry
- `GET /health` — Full system status (PostgreSQL latency + DragonflyDB telemetry)
- `GET /api/dragonfly_status` — DragonflyDB v2.0+ engine stats, memory, hit rate
- `GET /api/benchmark` — 100-op sub-millisecond pipeline benchmark

### Sheets & Rows
- `GET /api/sheets` — All sheets metadata (cached in Dragonfly L1)
- `GET /api/rows?sheet_id=1&offset=0&limit=1000` — Paginated rows + styles
- `POST /api/update_cell` — Update a single cell value
- `POST /api/batch_update_cells` — High-speed batch updates
- `POST /api/update_styles` — Update formatting / cell background colors

### Telecom Bot Pool Dispatch
- `GET /api_dispatch.php?action=pool_counts_quick` — Available uncolored stock
- `GET /api_dispatch.php?action=fetch_pool&circle=delhi&carrier=airtel` — Atomically lease numbers
- `POST /api_dispatch.php?action=report_outcome` — Report result (recovered/failed)

