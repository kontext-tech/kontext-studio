"""Schema profiler package for detecting and analyzing data schemas in files.

Files are read through DuckDB from a resolved storage path; only local
filesystem access is implemented today.
"""

from .models import ProfilerParameters, SchemaProfilingError, SchemaProfilingResult
from .profiler_base import SchemaProfilerBase
from .profilers import create_profiler

__all__ = [
    "ProfilerParameters",
    "SchemaProfilerBase",
    "SchemaProfilingError",
    "SchemaProfilingResult",
    "create_profiler",
]
