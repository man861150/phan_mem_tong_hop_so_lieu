#!/usr/bin/env bash
# Guarded localhost database reset. The seed command is deliberately separate.
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: ./scripts/reset_localhost_db.sh --yes

Backs up the verified local PostgreSQL database, drops it, and recreates it
with the project owner, UTF8 encoding, and en_US.UTF-8 locale. It refuses to
touch any non-local host, database, user, port, or a process with DEBUG=false.

The backup is written outside the repository. Passwords are never printed.
EOF
}

if [ "${1:-}" != "--yes" ]; then
    usage
    exit 1
fi

SOLIEU_DIR="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$SOLIEU_DIR"

if ! command -v uv >/dev/null 2>&1; then
    echo "Lỗi: không tìm thấy uv trong PATH." >&2
    exit 1
fi

TARGET="$(
    uv run python - <<'PY'
from urllib.parse import urlparse

import environ
from pathlib import Path

env = environ.Env()
environ.Env.read_env(Path(".env"))
url = env("DATABASE_URL", default="")
parsed = urlparse(url)
host = parsed.hostname or ""
port = str(parsed.port or "")
name = (parsed.path or "").lstrip("/")
user = parsed.username or ""
debug = env.bool("DJANGO_DEBUG", default=False)

errors = []
if parsed.scheme not in ("postgres", "postgresql"):
    errors.append("scheme phải là postgres/postgresql")
if host not in ("127.0.0.1", "localhost"):
    errors.append(f"host {host!r} không phải localhost")
if port != "5432":
    errors.append(f"port {port!r} không phải 5432")
if name != "solieu":
    errors.append(f"database {name!r} không phải 'solieu'")
if user != "solieu":
    errors.append(f"user {user!r} không phải 'solieu'")
if not debug:
    errors.append("DJANGO_DEBUG phải là true")
if errors:
    raise SystemExit("Từ chối reset: " + "; ".join(errors))

print(f"{host}|{port}|{name}|{user}|{debug}")
PY
)" || exit 1

IFS='|' read -r DB_HOST DB_PORT DB_NAME DB_USER DB_DEBUG <<< "$TARGET"
echo "Đã xác minh database localhost:"
echo "  host=$DB_HOST port=$DB_PORT database=$DB_NAME user=$DB_USER debug=$DB_DEBUG"

DATABASE_URL="$(
    uv run python - <<'PY'
import environ
from pathlib import Path

env = environ.Env()
environ.Env.read_env(Path(".env"))
print(env("DATABASE_URL"))
PY
)"

ADMIN_URL="$(
    uv run python - <<'PY'
from urllib.parse import urlparse, urlunparse

import environ
from pathlib import Path

env = environ.Env()
environ.Env.read_env(Path(".env"))
url = env("DATABASE_URL")
parsed = urlparse(url)
print(urlunparse(parsed._replace(path="/postgres")))
PY
)"

find_pg() {
    local name="$1"
    local directory
    for directory in \
        /opt/homebrew/opt/postgresql@17/bin \
        /opt/homebrew/opt/postgresql@16/bin \
        /usr/local/opt/postgresql@17/bin \
        /usr/local/opt/postgresql@16/bin; do
        if [ -x "$directory/$name" ]; then
            echo "$directory/$name"
            return 0
        fi
    done
    command -v "$name" || true
}

PG_DUMP="$(find_pg pg_dump)"
PSQL="$(find_pg psql)"
PG_RESTORE="$(find_pg pg_restore)"
if [ -z "$PG_DUMP" ] || [ -z "$PSQL" ]; then
    echo "Lỗi: không tìm thấy pg_dump/psql. Cài PostgreSQL hoặc đặt chúng trong PATH." >&2
    exit 1
fi

BACKUP_DIR="${SIHUB_BACKUP_DIR:-$HOME/sihub-db-backups}"
mkdir -p "$BACKUP_DIR"
BACKUP_REAL="$(cd "$BACKUP_DIR" && pwd -P)"
REPO_REAL="$(cd "$SOLIEU_DIR" && pwd -P)"
case "$BACKUP_REAL/" in
    "$REPO_REAL/"*)
        echo "Lỗi: thư mục backup nằm trong repository. Chọn thư mục khác." >&2
        exit 1
        ;;
esac

BACKUP="$BACKUP_DIR/solieu-$(date +%Y%m%d-%H%M%S).dump"
echo "Đang sao lưu database ra: $BACKUP"
"$PG_DUMP" --format=custom --no-owner --no-privileges \
    --file "$BACKUP" "$DATABASE_URL"
if [ ! -s "$BACKUP" ]; then
    echo "Lỗi: file backup rỗng. Không xóa database." >&2
    exit 1
fi
if [ -n "$PG_RESTORE" ]; then
    "$PG_RESTORE" --list "$BACKUP" >/dev/null
fi
echo "Backup hợp lệ: $BACKUP"

echo "Đang dừng kết nối và tạo lại database $DB_NAME..."
"$PSQL" "$ADMIN_URL" -v ON_ERROR_STOP=1 \
    -c "DROP DATABASE IF EXISTS \"$DB_NAME\" WITH (FORCE);"
"$PSQL" "$ADMIN_URL" -v ON_ERROR_STOP=1 \
    -c "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\" ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0;"

cat <<EOF
Đã tạo lại database $DB_NAME (owner=$DB_USER, UTF8, en_US.UTF-8).
Backup: $BACKUP

Bước tiếp theo:
  cd $SOLIEU_DIR
  uv run python manage.py migrate
  uv run python manage.py seed_demo_data
EOF
