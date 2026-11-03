"""
Job definitions for Kontext.

Each job module contains:
- A Pydantic params class (inheriting from BaseJobParams)
- A job class decorated with @job

Example:
    from kontext.jobs.base import BaseJobParams

    class MyJobParams(BaseJobParams):
        name: str = Field(..., description="Name parameter")

    @job(job_type="python.jobs.MyJob", params_model=MyJobParams, ...)
    class MyJob(BasePythonJob[MyJobParams]):
        async def execute_job(self, context, parameters: MyJobParams):
            ...
"""

# Job modules are auto-discovered by the job registry (pkgutil.iter_modules).
# Do NOT add eager imports here — that would pull in every job's dependencies
# (including optional ones like vector-search backends) at import time,
# breaking some environments.
# Import directly from the owning domain package if you need a class outside the
# registry.
__all__: list[str] = []
