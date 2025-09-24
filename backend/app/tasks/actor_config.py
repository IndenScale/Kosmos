# backend/app/tasks/actor_config.py
"""
Centralized configuration for all background actors in the Kosmos system.

This file defines the properties of each actor, making it easy to manage
and scale the background processing components.
"""

# Actor types
ACTOR_TYPE_PROCESS = "process"  # A standalone Python script running in a loop
ACTOR_TYPE_DRAMATIQ = "dramatiq" # A Dramatiq worker process

ACTORS = {
    "event_relay": {
        "type": ACTOR_TYPE_PROCESS,
        "description": "Polls the database for new domain events and publishes them to Redis.",
        "module": "backend.app.tasks.event_relay",
        "function": "run_relay_polling_loop",
    },
    "content_extraction_trigger": {
        "type": ACTOR_TYPE_PROCESS,
        "description": "Listens to Redis for 'DocumentRegistered' events and creates document processing jobs.",
        "module": "backend.app.tasks.content_extraction.trigger",
        "function": "listen_for_registration_events",
    },
    "main_workers": {
        "type": ACTOR_TYPE_DRAMATIQ,
        "description": "The main pool of Dramatiq workers that execute core, CPU-bound tasks.",
        "broker": "backend.app.tasks.broker:broker",
        "queues": ["default", "content_extraction", "document_processing", "chunking", "indexing"],
        "processes": 4, # Default number of processes
        "threads": 2,   # Default number of threads per process
    },
    "asset_analysis_worker": {
        "type": ACTOR_TYPE_DRAMATIQ,
        "description": "A dedicated, single-threaded worker for processing VLM-intensive asset analysis tasks serially.",
        "broker": "backend.app.tasks.broker:broker",
        "queues": ["asset_analysis"],
        "processes": 1,
        "threads": 1,
    },
    # TODO: Add other triggers as they are created (e.g., chunking_trigger)
}
