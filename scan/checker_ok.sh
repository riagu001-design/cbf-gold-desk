#!/bin/bash
# Prints RUNNING if loop.sh is alive (its pid file points at a live loop.sh), else STOPPED.
P=/home/user/gold-desk/scan_loop.pid
if [ -f "$P" ] && kill -0 "$(cat "$P")" 2>/dev/null && grep -q loop.sh "/proc/$(cat "$P")/cmdline" 2>/dev/null; then echo RUNNING; else echo STOPPED; fi
