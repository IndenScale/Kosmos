# backend/app/services/jobs/exceptions.py

class JobError(Exception):
    """Base exception for job-related errors."""
    pass

class JobNotFoundError(JobError):
    """Raised when a job cannot be found in the database."""
    pass
