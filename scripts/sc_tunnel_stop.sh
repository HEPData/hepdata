#!/bin/sh

if [[ -z ${SAUCE_USERNAME} || -z ${SAUCE_ACCESS_KEY} ]]; then
    exit 0
else
    echo "Stopping Sauce Connect."
fi

if [ -f ~/sauce_pidfile ]; then
    echo "Killing sauce connect tunnel..."
    kill `cat ~/sauce_pidfile`
    while [ -f ~/sauce_pidfile ];
    do
	sleep 1
    done
    echo "Process complete."
else
    echo "No pidfile at ~/sauce_pidfile - assume sauce connect not running."
fi
