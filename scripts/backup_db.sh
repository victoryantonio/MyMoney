#!/usr/bin/env bash
# MyMoney — PostgreSQL backup script (Supabase managed DB).
#
# Usage:
#   ./scripts/backup_db.sh            # one-shot backup + rotate
#   ./scripts/backup_db.sh --test     # dump to /tmp, discard (connectivity check)
#   ./scripts/backup_db.sh --list     # list existing backups
#
# Output directory: $BACKUP_DIR (default /root/backups/mymoney) — OUTSIDE the
# repo so secrets/backups are never committed. Rotation keeps the 14 newest.
#
# Scheduling (cron, root): run `crontab -e` and add:
#   0 3 * * * /root/project/scripts/backup_db.sh >> /var/log/mymoney-backup.log 2>&1
#
# Restore (if ever needed):
#   pg_restore -h <host> -p 5432 -U <user> -d <db> --no-owner --no-privileges \
#     --clean --if-exists /root/backups/mymoney/<file>.dump

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/root/backups/mymoney}"
KEEP="${KEEP:-14}"

# Load DATABASE_URL from project .env without exporting anything else.
DB_URL="$(grep -E '^DATABASE_URL=' "$PROJECT_DIR/.env" | head -1 | cut -d= -f2-)"
if [[ -z "$DB_URL" ]]; then
  echo "ERROR: DATABASE_URL not found in $PROJECT_DIR/.env" >&2
  exit 1
fi

# Parse URL components (supports postgresql:// and postgresql+psycopg://).
PARSE_OUT="$(DB_URL="$DB_URL" python3 -c '
import os, re
m = re.match(r"postgresql(?:\+psycopg)?://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/(.+)", os.environ["DB_URL"].strip())
if not m:
    print("|||5432|", end=""); raise SystemExit(1)
print("|".join([m.group(1), m.group(2), m.group(3), m.group(4) or "5432", m.group(5)]), end="")
')"
if [[ "$PARSE_OUT" == "|||5432|" ]]; then
  echo "ERROR: cannot parse DATABASE_URL" >&2
  exit 1
fi
IFS='|' read -r DB_USER DB_PASS DB_HOST DB_PORT DB_NAME <<<"$PARSE_OUT"

TS="$(date +%Y%m%d-%H%M%S)"
OUT_FILE="$BACKUP_DIR/mymoney-$TS.dump"

if [[ "${1:-}" == "--list" ]]; then
  ls -lh "$BACKUP_DIR" 2>/dev/null || echo "(no backups yet)"
  exit 0
fi

mkdir -p "$BACKUP_DIR"

if [[ "${1:-}" == "--test" ]]; then
  echo "Connectivity test: dumping to /tmp/mymoney-test.dump ..."
  PGPASSWORD="$DB_PASS" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    --no-owner --no-privileges -Fc -f /tmp/mymoney-test.dump
  echo "OK: $(du -h /tmp/mymoney-test.dump | cut -f1)"
  rm -f /tmp/mymoney-test.dump
  exit 0
fi

echo "[$(date -Is)] Starting backup -> $OUT_FILE"
PGPASSWORD="$DB_PASS" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  --no-owner --no-privileges -Fc -f "$OUT_FILE"
echo "[$(date -Is)] Backup OK: $(du -h "$OUT_FILE" | cut -f1)"

# Rotation: keep only the $KEEP newest backups.
ls -1t "$BACKUP_DIR"/mymoney-*.dump 2>/dev/null | tail -n +"$((KEEP + 1))" | while read -r old; do
  echo "[$(date -Is)] Pruning $old"
  rm -f "$old"
done
