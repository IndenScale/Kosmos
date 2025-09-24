#!/bin/bash
# Wrapper script to run the event_relay service with the correct environment.
cd /home/hxdi/Kosmos
export PYTHONPATH=$(pwd)
exec /home/hxdi/Kosmos/.venv/bin/python -u -m backend.app.tasks.event_relay
