#!/bin/bash
set -e

POSTGRES="psql --username ${POSTGRES_USER}"

echo "Creating database: ${POSTGRES_TEST_DB}"

$POSTGRES <<EOSQL
CREATE DATABASE ${POSTGRES_TEST_DB} OWNER ${POSTGRES_USER};
EOSQL
