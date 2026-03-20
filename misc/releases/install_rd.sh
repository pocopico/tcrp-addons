#!/bin/sh

echo "Starting ttyd, listening on port: 7681"
cp lrz /usr/sbin/rz
cp lsz /usr/sbin/sz
chmod +x ttyd
chmod +x tcrp-discover
./ttyd login > /dev/null 2>&1 &
./tcrp-discover > /dev/null 2>&1 &
