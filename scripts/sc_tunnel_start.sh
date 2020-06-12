#!/bin/bash

if [[ -z ${SAUCE_USERNAME} || -z ${SAUCE_ACCESS_KEY} ]]; then
    echo "SAUCE_USERNAME or SAUCE_ACCESS_KEY environment variables not available."
    echo "Omitting Selenium end-to-end tests running on Sauce Labs."
    exit 0
fi

echo "Setting up Sauce Connect."
tmp_dir=$(mktemp -d -t sc-XXXXXX)
sc_version=4.6.2
cd $tmp_dir

echo "Downloading Sauce Connect..."
curl https://saucelabs.com/downloads/sc-${sc_version}-linux.tar.gz --output sc-${sc_version}-linux.tar.gz
tar -xf sc-${sc_version}-linux.tar.gz

echo "Starting tunnel..."
sc-${sc_version}-linux/bin/sc -i ${TRAVIS_JOB_NUMBER} -f sauce-connect-ready -d ~/sauce_pidfile -l ~/sauce-connect.log -x https://eu-central-1.saucelabs.com/rest/v1 &

echo "Waiting for Sauce Connect to be ready (or exit)..."
pid=$!
while [ ! -f sauce-connect-ready ] && (ps -p $pid > /dev/null)
do
    sleep 1
done

if (ps -p $pid > /dev/null); then
    echo "Sauce Connect is ready"
else
    echo "Sauce Connect failed to start."
    exit 1
fi
