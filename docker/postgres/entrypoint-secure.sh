#!/bin/sh
# Load Docker Secret into POSTGRES_PASSWORD for official postgres image
if [ -f /run/secrets/postgres_password ]; then
  export POSTGRES_PASSWORD="$(cat /run/secrets/postgres_password)"
fi
exec /usr/local/bin/docker-entrypoint.sh "$@"
