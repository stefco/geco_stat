#!/bin/bash

# Configure a virtualenv for this project.

# Safety first, then teamwork
set -o errexit
set -o nounset
set -o noclobber

cat <<__EOF__

Configuring a virtual environment for python...

__EOF__

# Install a virtualenv to allow for local development and usage.
# Requires virtualenv if env/ directory does not exist already.
if ! [ -e "./env" ]
then
    virtualenv env
fi

# Install some stuff required for pip packaging and development
env/bin/pip install -U "pip>=1.4" "setuptools>=0.9" "wheel>=0.21" twine

# Install required packages
env/bin/pip install -U "numpy" "matplotlib" "h5py"

# Install required packages into the virtualenv
if [ -e "requirements.txt" ]
then
    printf "Installing packages from requirements.txt...\n"
    env/bin/pip install -r requirements.txt
else
    printf "No requirements.txt file found, moving on...\n"
fi

cat <<__EOF__

Done setting up! Run

    source env/bin/activate

to start working in this virtual environment, and run

    deactivate

when finished to return to your normal setup.

For nice documentation on virtualenv, visit:
https://www.dabapps.com/blog/introduction-to-pip-and-virtualenv-python/
__EOF__
