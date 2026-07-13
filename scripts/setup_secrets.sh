#!/usr/bin/env bash
# Generate Docker Secrets files for secure deployment
set -euo pipefail

SECRETS_DIR="$(dirname "$0")/../secrets"
mkdir -p "$SECRETS_DIR"

gen_secret() {
  local name="$1"
  local file="$SECRETS_DIR/$name"
  if [ -f "$file" ]; then
    echo "  [skip] $name already exists"
  else
    openssl rand -base64 32 | tr -d '/+=' | head -c 40 > "$file"
    echo "  [created] $name"
  fi
}

echo "Generating secrets in $SECRETS_DIR ..."
gen_secret jwt_secret
gen_secret postgres_password
gen_secret minio_secret_key
gen_secret phi_encryption_key
gen_secret pseudonymization_salt

chmod 600 "$SECRETS_DIR"/*
echo ""
echo "Done. NEVER commit secrets/ to git."
echo "Deploy: docker compose -f docker-compose.prod.yml -f docker-compose.secure.yml up -d"
