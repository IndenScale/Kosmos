#!/bin/bash
# Wrapper script to run the chunking trigger with the correct environment.
cd /home/hxdi/Kosmos
export PYTHONPATH=$(pwd)
exec /home/hxdi/Kosmos/.venv/bin/python -u -m backend.app.tasks.chunking.trigger
