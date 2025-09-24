#!/bin/bash
# Wrapper script to run the asset_analysis trigger with the correct environment.
cd /home/hxdi/Kosmos
export PYTHONPATH=$(pwd)
exec /home/hxdi/Kosmos/.venv/bin/python -u -m backend.app.tasks.asset_analysis.trigger
