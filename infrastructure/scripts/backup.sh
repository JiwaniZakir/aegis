#!/usr/bin/env bash
# =============================================================================
# Aegis — Backup Script
# =============================================================================
# Dumps PostgreSQL, encrypts with age, stores in MinIO.
#
# Usage: ./infrastructure/scripts/backup.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Load environment
if [[ -f "$PROJECT_DIR/.env" ]]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$PROJECT_DIR/backups"
DUMP_FILE="$BACKUP_DIR/aegis_${TIMESTAMP}.sql.gz"
ENCRYPTED_FILE="${DUMP_FILE}.age"

mkdir -p "$BACKUP_DIR"

# --- Step 1: Dump PostgreSQL ---
log_info "Dumping PostgreSQL database..."
docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T postgres \
    pg_dump -U "${POSTGRES_USER:-aegis}" "${POSTGRES_DB:-aegis}" \
    | gzip > "$DUMP_FILE"

DUMP_SIZE=$(du -h "$DUMP_FILE" | cut -f1)
log_info "Dump complete: $DUMP_FILE ($DUMP_SIZE)"

# --- Step 2: Encrypt with age ---
if command -v age &>/dev/null; then
    log_info "Encrypting backup with age..."
    AGE_RECIPIENT="${AGE_PUBLIC_KEY:-}"
    if [[ -z "$AGE_RECIPIENT" ]]; then
        log_warn "AGE_PUBLIC_KEY not set — using passphrase encryption"
        age -p -o "$ENCRYPTED_FILE" "$DUMP_FILE"
    else
        age -r "$AGE_RECIPIENT" -o "$ENCRYPTED_FILE" "$DUMP_FILE"
    fi
    rm "$DUMP_FILE"
    log_info "Encrypted: $ENCRYPTED_FILE"
else
    log_warn "age not installed — backup stored unencrypted"
    ENCRYPTED_FILE="$DUMP_FILE"
fi

# --- Step 3: Upload to MinIO ---
if command -v mc &>/dev/null; then
    log_info "Uploading to MinIO..."
    mc alias set aegis "${MINIO_URL:-http://localhost:9000}" \
        "${MINIO_ROOT_USER:-aegis}" "${MINIO_ROOT_PASSWORD}" 2>/dev/null

    mc mb --ignore-existing aegis/backups 2>/dev/null
    mc cp "$ENCRYPTED_FILE" "aegis/backups/$(basename "$ENCRYPTED_FILE")"
    log_info "Uploaded to MinIO: backups/$(basename "$ENCRYPTED_FILE")"
else
    log_warn "mc (MinIO client) not installed — backup stored locally only"
fi

# --- Step 4: Clean up old local backups (keep last 7) ---
log_info "Cleaning old local backups..."
ls -t "$BACKUP_DIR"/aegis_*.age "$BACKUP_DIR"/aegis_*.sql.gz 2>/dev/null \
    | tail -n +8 | xargs rm -f 2>/dev/null || true

log_info "Backup complete."
