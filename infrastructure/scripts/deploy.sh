#!/usr/bin/env bash
# =============================================================================
# Aegis — Deployment Script
# =============================================================================
# Decrypts SOPS secrets, validates .env, builds and starts all services,
# runs health checks.
#
# Usage: ./infrastructure/scripts/deploy.sh [--prod]
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILES="-f $PROJECT_DIR/docker-compose.yml"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Parse arguments
PROD=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --prod) PROD=true; shift ;;
        -h|--help)
            echo "Usage: $0 [--prod]"
            echo "  --prod    Include production overrides"
            exit 0
            ;;
        *) log_error "Unknown option: $1"; exit 1 ;;
    esac
done

if $PROD; then
    COMPOSE_FILES="$COMPOSE_FILES -f $PROJECT_DIR/docker-compose.prod.yml"
    log_info "Production mode enabled"
fi

# --- Step 1: Decrypt SOPS secrets ---
log_info "Decrypting SOPS secrets..."
if command -v sops &>/dev/null; then
    for enc_file in "$PROJECT_DIR"/secrets/*.enc.yaml; do
        [ -f "$enc_file" ] || continue
        out_file="${enc_file%.enc.yaml}.yaml"
        sops -d "$enc_file" > "$out_file"
        chmod 600 "$out_file"
        log_info "  Decrypted: $(basename "$enc_file")"
    done
else
    log_warn "sops not found — skipping secret decryption"
fi

# --- Step 1b: Ensure OpenClaw gateway repo ---
OPENCLAW_DIR="$PROJECT_DIR/openclaw"
if [[ ! -d "$OPENCLAW_DIR" ]]; then
    log_info "Cloning OpenClaw gateway..."
    git clone --depth 1 https://github.com/openclaw/openclaw.git "$OPENCLAW_DIR"
else
    log_info "OpenClaw directory exists"
fi

# --- Step 2: Validate .env ---
log_info "Validating .env..."
ENV_FILE="$PROJECT_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    log_error ".env file not found at $ENV_FILE"
    log_error "Copy .env.example to .env and fill in values"
    exit 1
fi

REQUIRED_VARS=(POSTGRES_PASSWORD REDIS_PASSWORD JWT_SECRET ENCRYPTION_MASTER_KEY MINIO_ROOT_PASSWORD)
for var in "${REQUIRED_VARS[@]}"; do
    val=$(grep -E "^${var}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)
    if [[ -z "$val" ]]; then
        log_error "Required variable $var is not set in .env"
        exit 1
    fi
done
log_info ".env validated"

# --- Step 3: Build and start ---
log_info "Building and starting services..."
cd "$PROJECT_DIR"
docker compose $COMPOSE_FILES up -d --build

# --- Step 4: Wait for health checks ---
log_info "Waiting for services to become healthy..."
SERVICES=(postgres redis qdrant minio traefik api console)
MAX_WAIT=120
ELAPSED=0

for svc in "${SERVICES[@]}"; do
    while true; do
        STATUS=$(docker compose $COMPOSE_FILES ps --format json "$svc" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
if isinstance(data, list):
    data = data[0] if data else {}
print(data.get('Health', data.get('health', 'unknown')))
" 2>/dev/null || echo "unknown")

        if [[ "$STATUS" == "healthy" ]]; then
            log_info "  $svc: healthy"
            break
        fi

        if [[ $ELAPSED -ge $MAX_WAIT ]]; then
            log_error "  $svc: timed out waiting for healthy status"
            docker compose $COMPOSE_FILES logs --tail=20 "$svc"
            exit 1
        fi

        sleep 5
        ELAPSED=$((ELAPSED + 5))
    done
done

log_info "All services healthy. Deployment complete."
