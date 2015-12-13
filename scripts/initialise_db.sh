hepdata db drop
hepdata db init
hepdata db create

# Now create the roles
hepdata roles create -n coordinator
hepdata roles create -n admin

# Next, create the users
hepdata users create -e eamonnmag@gmail.com --password hello1 -a

# Finally, add the roles to the user
hepdata roles add -u eamonnmag@gmail.com -r coordinator
hepdata roles add -u eamonnmag@gmail.com -r admin

# now populate the database with some records. NOTE:
# Celery needs to be running.
hepdata populate