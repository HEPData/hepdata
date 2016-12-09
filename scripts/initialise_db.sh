#!/usr/bin/env bash

if [ $# -ne 2 ]; then
    echo "Usage: $0 your@email.com password"
    exit 1
fi

hepdata db drop
hepdata db init
hepdata db create

# Now create the roles
hepdata roles create coordinator
hepdata roles create admin

# Next, create the users
hepdata users create $1 --password $2 -a

# Finally, add the roles to the user
hepdata roles add $1 coordinator
hepdata roles add $1 admin

# now populate the database with some records. NOTE:
# Celery needs to be running.
hepdata migrator populate
