#!/usr/bin/env bash
# Generate self-signed TLS certificates for development/staging
set -euo pipefail

CERTS_DIR="$(dirname "$0")/../docker/nginx/certs"
mkdir -p "$CERTS_DIR"

openssl req -x509 -nodes -days 365 -newkey rsa:4096 \
  -keyout "$CERTS_DIR/server.key" \
  -out "$CERTS_DIR/server.crt" \
  -subj "/CN=barekat.local/O=BAREKAT Health/C=IR" \
  -addext "subjectAltName=DNS:api.barekat.local,DNS:dashboard.barekat.local,DNS:minio.barekat.local,DNS:localhost"

chmod 600 "$CERTS_DIR/server.key"
echo "TLS certificates created in $CERTS_DIR"
echo "Add to /etc/hosts:"
echo "  127.0.0.1 api.barekat.local dashboard.barekat.local minio.barekat.local"
