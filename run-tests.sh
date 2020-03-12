#!/bin/sh

# This file is part of HEPData.
# Copyright (C) 2020 CERN.
#
# HEPData is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# HEPData is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HEPData; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.


# Sanity checks
if [ "$(command -v elasticsearch)" = "" ]; then echo "Command 'elasticsearch' not installed" && exit 1; fi
if [ "$(command -v pg_ctl)" = "" ]; then echo "Command 'pg_ctl' not installed" && exit 1; fi
if [ "$(command -v psql)" = "" ]; then echo "Command 'psql' not installed" && exit 1; fi


# PostgreSQL initialization variables
PG_TEST_USER="hepdata"
PG_TEST_PASS="hepdata"
PG_TEST_DB_NAME="hepdata_test"
PG_DEFAULT_DATA_PATH="/usr/local/var/postgresql@9.6"
PG_DEFAULT_DB_NAME="postgres"

# PostgreSQL initialization commands
PG_TEST_USER_COMMAND="create user ${PG_TEST_USER} with createdb password '${PG_TEST_PASS}';"
PG_TEST_DB_COMMAND="create database ${PG_TEST_DB_NAME} owner '${PG_TEST_USER}';"

# ElasticSearch initialization variables
ELASTIC_PID_FILE="elastic_pid.txt"


echo "------ Starting PostgreSQL ------"
pg_ctl -D ${PG_DEFAULT_DATA_PATH} -w start

echo "------ Setting up PostgreSQL ------"
psql -c "${PG_TEST_USER_COMMAND}" --dbname ${PG_DEFAULT_DB_NAME}
psql -c "${PG_TEST_DB_COMMAND}" --dbname ${PG_DEFAULT_DB_NAME}

echo "------ Starting ElasticSearch ------"
elasticsearch --daemonize --pidfile ${ELASTIC_PID_FILE}
while [ ! -f ${ELASTIC_PID_FILE} ]; do sleep 1; done


echo "------ Running test suite ------"
if [ "$1" = "omit-selenium" ]
then
    echo "Running tests omitting Selenium"
    py.test -k "not tests/e2e"
else
    echo "Running tests in normal mode"
    py.test tests
fi


echo "------ Stopping ElasticSearch ------"
kill -15 "$(cat ${ELASTIC_PID_FILE})"

echo "------ Stopping PostgreSQL ------"
pg_ctl -D "${PG_DEFAULT_DATA_PATH}" stop
