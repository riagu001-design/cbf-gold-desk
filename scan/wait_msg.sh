#!/bin/bash
# Session background task: exits (waking the session) as soon as an unsent setup is waiting in scan_msg.txt.
G=/home/user/gold-desk
until [ -f "$G/scan_msg.txt" ]; do sleep 5; done
echo "SETUP WAITING TO BE SENT:"; cat "$G/scan_msg.txt"
