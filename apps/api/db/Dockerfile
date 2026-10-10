# Local dev Postgres with the Cartlyf roles baked in (no bind mounts, so it works on any Docker host).
FROM postgres:16-alpine
COPY roles.sql /cartlyf-db/roles.sql
COPY docker-init.sh /docker-entrypoint-initdb.d/10-cartlyf-roles.sh
