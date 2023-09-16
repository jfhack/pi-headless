#!/bin/bash

cd "$(dirname "${BASH_SOURCE[0]}")"

export DEBIAN_FRONTEND=noninteractive

sudo apt-get update
sudo apt-get install dialog apt-utils -y

sudo python3 if.py -a $1

sudo apt-get install -y dnsmasq
sudo python3 dm.py -r $2 -l $3
sudo systemctl enable --now dnsmasq

