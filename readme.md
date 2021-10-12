# Ubinetic Oracles Contract

## Structure

This project provides the following contracts:

- constants.py: holds constants used throughout the project
- errors.py: acts as a constant error map used throughout the project. Non-project specific errors (i.e. fa2 errors) are covered in the respective files.
- job_scheduler.py: schedules jobs for the datatransmitter.
- generic_oracle.py: shows an implementation that takes the data transmitter price and validates it on-chain.

## Build/Basic Usage

### Dependencies

This project depends only on SmartPy (which depends on python and node), you can install SmartPy by doing a:

```
$ sh <(curl -s https://smartpy.io/releases/20211004-ea717461f93381b75961d6b3456cd114138f42c0/cli/install.sh)
```

You can read more about the installation here: https://smartpy.io/cli/

If you want to compile docs and deploy you also will need a sphinx and pytezos, these are the dependencies:

```
apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends python3-pip libsodium-dev libsecp256k1-dev
pip3 install sphinx pytezos
```

There is a ".devcontainer" which creates a dockerized environment and installs everything needed for you. You can checkout ".devcontainer/Dockerfile" to understand
the dependencies. I.e. VSCode will just ask you to open in container and within 5 minutes you are good to go.

Please note that in order to be able to "find" the Python modules you will have to export "PYTHONPATH" to include the main smartpy folder _and_ this very folder.

```
export PYTHONPATH=/home/node/smartpy-cli/:$(pwd)
```

The command above expects you to be on the root of this project and smartpy-cli to be installed in /home/node/smartpy-cli/. Also while you are at it, might aswell 
export the smartpy PATH.

```
export PATH=$PATH:/home/node/smartpy-cli/
```

## Testing

The tests are easiest to run using 

```
SmartPy.sh test oracles/generic_oracle.py out --html
SmartPy.sh test oracles/job_scheduler.py out --html
```

## Deployment

### Platform

Once you are happy with the local test you can deploy to the network (this will take +-20 minutes)

```
cd oracles
SmartPy.sh compile compiler.py out
python3 deployment.py 
```
