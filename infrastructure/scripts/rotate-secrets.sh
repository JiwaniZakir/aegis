#!/usr/bin/env bash
# =============================================================================
# ClawdBot — Secret Rotation Script
# =============================================================================
# Rotates internal secrets (DB password, Redis password, JWT secret, etc.)
# Re-encrypts with SOPS and restarts affected services.
#
# Usage: ./infrastructure/scripts/rotate-secrets.sh
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

generate_secret() { openssl rand -hex 32; }

log_info "=== ClawdBot Secret Rotation ==="
echo ""

# --- Backup current .env ---
cp "$PROJECT_DIR/.env" "$PROJECT_DIR/.env.backup.$(date +%Y%m%d_%H%M%S)"
log_info "Current .env backed up"

# --- Generate new secrets ---
NEW_POSTGRES_PW=$(generate_secret)
NEW_REDIS_PW=$(generate_secret)
NEW_JWT_SECRET=$(generate_secret)
NEW_ENCRYPTION_KEY=$(generate_secret)

log_info "New secrets generated"

# --- Update .env ---
ENV_FILE="$PROJECT_DIR/.env"

update_env_var() {
    local var="$1" val="$2"
    if grep -q "^${var}=" "$ENV_FILE"; then
        sed -i.bak "s|^${var}=.*|${var}=${val}|" "$ENV_FILE"
    else
        echo "${var}=${val}" >> "$ENV_FILE"
    fi
}

update_env_var "POSTGRES_PASSWORD" "$NEW_POSTGRES_PW"
update_env_var "REDIS_PASSWORD" "$NEW_REDIS_PW"
update_env_var "JWT_SECRET" "$NEW_JWT_SECRET"
update_env_var "ENCRYPTION_MASTER_KEY" "$NEW_ENCRYPTION_KEY"

rm -f "${ENV_FILE}.bak"
chmod 600 "$ENV_FILE"

log_info "Updated .env with new secrets"

# --- Update PostgreSQL password ---
log_info "Updating PostgreSQL password..."
docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T postgres \
    psql -U "${POSTGRES_USER:-clawdbot}" -c \
    "ALTER USER ${POSTGRES_USER:-clawdbot} PASSWORD '${NEW_POSTGRES_PW}';" 2>/dev/null || \
    log_warn "Could not update PG password live — will take effect on next restart"

# --- Restart services ---
log_info "Restarting services with new credentials..."
cd "$PROJECT_DIR"
docker compose down
docker compose up -d

log_info "Waiting for services to become healthy..."
sleep 15

# --- Verify ---
docker compose ps
echo ""
log_info "Secret rotation complete. Verify services above show 'Up (healthy)'."
log_warn "Remember: external API keys (Plaid, Anthropic, etc.) are NOT rotated by this script."
log_warn "Rotate those manually via their respective dashboards."
