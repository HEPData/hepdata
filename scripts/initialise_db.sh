#!/usr/bin/env bash
hepdata db drop
hepdata db init
hepdata db create

# Now create the roles
hepdata roles create coordinator
hepdata roles create admin

# Next, create the users
hepdata users create eamonnmag@gmail.com --password hello1 -a

# Finally, add the roles to the user
hepdata roles add eamonnmag@gmail.com coordinator
hepdata roles add eamonnmag@gmail.com admin

# now populate the database with some records. NOTE:
# Celery needs to be running.
hepdata populate
