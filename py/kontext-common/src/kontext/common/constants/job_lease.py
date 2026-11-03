"""Job-run claim-lease configuration shared by claim, renewal, and reclaim.

A claimed run holds a lease — the local analogue of a queue visibility
timeout. The claiming worker stamps a lease and renews it while alive and
healthy (fenced on its worker identity); a periodic reaper reclaims runs
whose lease lapsed (worker crashed) back to ``Queued``, or dead-letters them
after the reclaim cap.
"""

import os

from .env_vars import JobLeaseEnvVars

# Default lease: long enough to ride out a stalled host or GC pause, short
# enough that a crashed worker's runs are recovered in minutes, not hours.
# The worker renews at lease/3, so the effective stall tolerance before a
# false reclaim is ~lease seconds.
DEFAULT_JOB_RUN_LEASE_SECONDS = 300

# Reclaim cap: a run that keeps outliving its lease is crash-looping (e.g. a
# job that wedges the worker) and should not be retried forever.
DEFAULT_JOB_RUN_MAX_LEASE_RECLAIMS = 5


def job_run_lease_seconds() -> int:
    """Resolve the job-run lease duration (seconds) from the environment."""
    raw = os.getenv(JobLeaseEnvVars.LEASE_SECONDS)
    if not raw:
        return DEFAULT_JOB_RUN_LEASE_SECONDS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_JOB_RUN_LEASE_SECONDS
    return value if value >= 1 else DEFAULT_JOB_RUN_LEASE_SECONDS


def job_run_max_lease_reclaims() -> int:
    """Resolve how many lease reclaims a run may survive before dead-lettering."""
    raw = os.getenv(JobLeaseEnvVars.MAX_RECLAIMS)
    if not raw:
        return DEFAULT_JOB_RUN_MAX_LEASE_RECLAIMS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_JOB_RUN_MAX_LEASE_RECLAIMS
    return value if value >= 0 else DEFAULT_JOB_RUN_MAX_LEASE_RECLAIMS
