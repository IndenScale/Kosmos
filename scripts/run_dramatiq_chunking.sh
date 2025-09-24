#!/bin/bash
# Wrapper script to run the chunking dramatiq worker with the correct environment.
cd /home/hxdi/Kosmos
export PYTHONPATH=$(pwd)
exec env DRAMATIQ_SKIP_PROMETHEUS=1 /home/hxdi/Kosmos/.venv/bin/dramatiq backend.app.tasks.broker:broker --queues chunking -p 1 -t 1