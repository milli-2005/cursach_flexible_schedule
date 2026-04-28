# Safe Migration: SQLite to PostgreSQL

This project now supports two DB modes:
- `USE_POSTGRES=0` (default): SQLite (`db.sqlite3`)
- `USE_POSTGRES=1`: PostgreSQL

## 1. Pre-checks

1. Create an empty PostgreSQL database.
2. Ensure PostgreSQL user has rights to create tables in this DB.
3. Install dependencies:

```powershell
cd schedule_optimizer
.\venv\Scripts\pip.exe install -r requirements.txt
```

## 2. Run safe migration script

From project root (`cursach_flexible_schedule`):

```powershell
.\tools\migrate_sqlite_to_postgres_safe.ps1 `
  -PostgresDb "schedule_optimizer" `
  -PostgresUser "postgres" `
  -PostgresPassword "YOUR_PASSWORD" `
  -PostgresHost "127.0.0.1" `
  -PostgresPort "5432"
```

What the script does:
1. Creates a backup folder in `backups/sqlite_to_postgres_YYYYMMDD_HHMMSS`.
2. Copies `schedule_optimizer/db.sqlite3`.
3. Creates JSON dumps (full + safe).
4. Applies migrations on PostgreSQL.
5. Loads safe data dump into PostgreSQL.
6. Prints key table counts for quick verification.

## 3. Start app with PostgreSQL

PowerShell example:

```powershell
cd schedule_optimizer
$env:USE_POSTGRES="1"
$env:POSTGRES_DB="schedule_optimizer"
$env:POSTGRES_USER="postgres"
$env:POSTGRES_PASSWORD="YOUR_PASSWORD"
$env:POSTGRES_HOST="127.0.0.1"
$env:POSTGRES_PORT="5432"
.\venv\Scripts\python.exe manage.py runserver
```

## 4. Rollback (if needed)

If anything goes wrong:
1. Stop server.
2. Set `USE_POSTGRES=0` (or remove it from env).
3. Keep using SQLite immediately.
4. If SQLite file was changed unexpectedly, restore `db.sqlite3.backup` from the backup folder.

## 5. DBeaver screenshots

For screenshots in DBeaver after migration:
1. Create a new PostgreSQL connection in DBeaver.
2. Open schema `public`.
3. Capture:
- database navigator tree,
- ER-style table relations or table list,
- one or two populated business tables (`core_schedule`, `core_shiftassignment`, etc.).
