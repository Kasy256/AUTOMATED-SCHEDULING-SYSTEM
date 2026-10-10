#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v owner_password="$CARTLYF_OWNER_PASSWORD" \
  -v app_password="$CARTLYF_APP_PASSWORD" \
  -f /cartlyf-db/roles.sql
