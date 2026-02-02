#!/usr/bin/env sh
set -eu

mkdir -p /letsencrypt
if [ ! -f /letsencrypt/acme.json ]; then
  touch /letsencrypt/acme.json
fi
chmod 600 /letsencrypt/acme.json || true

exec traefik "$@"
