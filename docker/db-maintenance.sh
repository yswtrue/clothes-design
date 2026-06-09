#!/bin/sh
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
PGHOST="${PGHOST:-postgres}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-clothes_design}"
WAIT_TIMEOUT_SECONDS="${WAIT_TIMEOUT_SECONDS:-60}"

usage() {
  cat <<'EOF'
Database maintenance commands:
  backup [name]        Create a custom-format PostgreSQL dump in /backups.
                       If name is omitted, a timestamped file is used.
  restore <file|latest>
                       Restore a dump from /backups. Requires CONFIRM_RESTORE=yes.
  list                 List files in /backups.
  help                 Show this help.

Examples:
  docker compose run --rm db-maintenance backup
  docker compose run --rm db-maintenance backup before-release.dump
  docker compose run --rm -e CONFIRM_RESTORE=yes db-maintenance restore latest
EOF
}

wait_for_postgres() {
  echo "Waiting for PostgreSQL at ${PGHOST}:${PGPORT}..."
  elapsed=0
  until pg_isready -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" >/dev/null 2>&1; do
    if [ "${elapsed}" -ge "${WAIT_TIMEOUT_SECONDS}" ]; then
      echo "Timed out waiting for PostgreSQL after ${WAIT_TIMEOUT_SECONDS}s" >&2
      exit 1
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
}

ensure_backup_dir() {
  mkdir -p "${BACKUP_DIR}"
}

normalize_backup_name() {
  name="$1"
  case "${name}" in
    */*)
      echo "Backup names must not contain '/': ${name}" >&2
      exit 1
      ;;
  esac

  case "${name}" in
    *.dump) printf '%s\n' "${name}" ;;
    *) printf '%s.dump\n' "${name}" ;;
  esac
}

backup_database() {
  ensure_backup_dir

  if [ "${1:-}" = "" ]; then
    file="${BACKUP_DIR}/${PGDATABASE}-$(date -u +%Y%m%dT%H%M%SZ).dump"
  else
    file="${BACKUP_DIR}/$(normalize_backup_name "$1")"
  fi

  if [ -e "${file}" ]; then
    echo "Backup already exists: ${file}" >&2
    exit 1
  fi

  wait_for_postgres
  echo "Creating backup: ${file}"
  pg_dump \
    --host "${PGHOST}" \
    --port "${PGPORT}" \
    --username "${PGUSER}" \
    --dbname "${PGDATABASE}" \
    --format custom \
    --no-owner \
    --no-privileges \
    --file "${file}"
  echo "Backup complete: ${file}"
}

resolve_restore_file() {
  target="$1"
  if [ "${target}" = "latest" ]; then
    latest_file="$(find "${BACKUP_DIR}" -maxdepth 1 -type f -name '*.dump' -exec ls -t {} + 2>/dev/null | sed -n '1p' || true)"
    if [ "${latest_file}" = "" ]; then
      echo "No .dump files found in ${BACKUP_DIR}" >&2
      exit 1
    fi
    printf '%s\n' "${latest_file}"
    return
  fi

  case "${target}" in
    /*) printf '%s\n' "${target}" ;;
    *) printf '%s\n' "${BACKUP_DIR}/$(normalize_backup_name "${target}")" ;;
  esac
}

restore_database() {
  ensure_backup_dir

  if [ "${1:-}" = "" ]; then
    echo "Missing restore file. Use: restore <file|latest>" >&2
    exit 1
  fi

  if [ "${CONFIRM_RESTORE:-}" != "yes" ]; then
    echo "Restore is destructive. Re-run with CONFIRM_RESTORE=yes to continue." >&2
    exit 1
  fi

  file="$(resolve_restore_file "$1")"
  if [ ! -f "${file}" ]; then
    echo "Restore file not found: ${file}" >&2
    exit 1
  fi

  wait_for_postgres
  echo "Restoring ${file} into database ${PGDATABASE}..."
  pg_restore \
    --host "${PGHOST}" \
    --port "${PGPORT}" \
    --username "${PGUSER}" \
    --dbname "${PGDATABASE}" \
    --clean \
    --if-exists \
    --single-transaction \
    --exit-on-error \
    --no-owner \
    --no-privileges \
    "${file}"
  echo "Restore complete: ${file}"
}

list_backups() {
  ensure_backup_dir
  find "${BACKUP_DIR}" -maxdepth 1 -type f -name '*.dump' -print | sort
}

case "${1:-help}" in
  backup)
    shift
    backup_database "${1:-}"
    ;;
  restore)
    shift
    restore_database "${1:-}"
    ;;
  list)
    list_backups
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    echo "Unknown command: $1" >&2
    usage >&2
    exit 1
    ;;
esac
