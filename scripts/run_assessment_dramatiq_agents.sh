#!/bin/bash
dramatiq assessment_service.app.broker --queues agent_runners --processes 1 --threads 1
