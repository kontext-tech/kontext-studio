"""Derive short, human-readable summaries for job runs.

The value surfaced for a run is declared by each job through the ``@job``
decorator's ``display_parameter`` argument, so this module never hardcodes job
type strings. It parses the stored run parameters with the job's own Pydantic
params model and returns the requested field as a string.
"""

from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from kontext.jobs.job_registry import get_job_registry
from kontext.schema import JobRunModel

logger = logging.getLogger(__name__)


def build_display_summary(
    job_type: str | None,
    parameters_json: str | None,
) -> str | None:
    """Build a short, type-specific summary for a run's parameters.

    Args:
        job_type: Registered job type (e.g. ``python.jobs.ExecuteQueryJob``).
        parameters_json: Serialized run parameters, or the job's own defaults.

    Returns:
        The display parameter rendered as a string, or ``None`` when the type
        is unknown, has no display parameter, or the value is missing.
    """
    if not job_type or not parameters_json:
        return None

    job_class = get_job_registry().get_job_class(job_type)
    if job_class is None:
        return None

    display_parameter = job_class.get_display_parameter()
    if not display_parameter:
        return None

    try:
        raw_parameters = json.loads(parameters_json)
    except (TypeError, ValueError):
        return None

    if not isinstance(raw_parameters, dict):
        return None

    params_model = job_class.get_params_model()
    try:
        parameters = params_model.model_validate(raw_parameters)
    except ValidationError:
        logger.debug(
            "Could not parse parameters for job type %s into %s",
            job_type,
            params_model.__name__,
        )
        return None

    value = getattr(parameters, display_parameter, None)
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def enrich_job_run_display_summary(run: JobRunModel) -> JobRunModel:
    """Populate ``display_summary`` on a job run in place when it is unset."""
    if run.display_summary:
        return run

    job_type = run.job.type if run.job else None
    parameters_json = run.parameters or (run.job.parameters if run.job else None)
    run.display_summary = build_display_summary(job_type, parameters_json)
    return run


__all__ = ["build_display_summary", "enrich_job_run_display_summary"]
