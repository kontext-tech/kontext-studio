"""
Decorators for defining Python jobs with type-safe parameters.

The @job decorator provides a clean, declarative way to define job metadata
while associating a Pydantic parameter model for automatic validation.
"""

from typing import Any, get_type_hints

from pydantic.fields import FieldInfo

from kontext.jobs.base import BaseJobParams
from kontext.schema import (
    JobCategory,
    JobExecutionRuntime,
    JobParameterType,
    UnifiedJobParameterModel,
    UnifiedJobTypeModel,
)


def _python_type_to_job_param_type(python_type: type) -> JobParameterType:
    """Map Python types to JobParameterType enum values."""
    # Handle Optional types (Union with None)
    origin = getattr(python_type, "__origin__", None)
    if origin is type(None):
        return JobParameterType.STRING

    # For Union types (like str | None), get the non-None type
    if origin is not None:
        args = getattr(python_type, "__args__", ())
        non_none_args = [a for a in args if a is not type(None)]
        if non_none_args:
            python_type = non_none_args[0]

    # Map basic types (only String, Integer, Boolean are supported)
    if python_type is str:
        return JobParameterType.STRING
    elif python_type is int:
        return JobParameterType.INTEGER
    elif python_type is bool:
        return JobParameterType.BOOLEAN
    else:
        # Default to string for all other types (float, dict, list, etc.)
        return JobParameterType.STRING


def _field_to_job_parameter(
    name: str, field_info: FieldInfo, python_type: type
) -> UnifiedJobParameterModel:
    """Convert a Pydantic field to UnifiedJobParameterModel."""
    # Determine if required (no default value)
    is_required = field_info.default is None and field_info.default_factory is None

    # Handle PydanticUndefined
    from pydantic_core import PydanticUndefined

    if field_info.default is PydanticUndefined:
        is_required = True
        default_value = None
    else:
        default_value = field_info.default

    # Check if the type is Optional (Union with None)
    origin = getattr(python_type, "__origin__", None)
    if origin is not None:
        args = getattr(python_type, "__args__", ())
        if type(None) in args:
            # It's Optional, so not required even without default
            is_required = False

    # Get max_length from field metadata if present
    max_length = None
    if hasattr(field_info, "metadata"):
        for meta in field_info.metadata:
            if hasattr(meta, "max_length"):
                max_length = meta.max_length

    # Get possible values from Literal types or enum constraints
    possible_values: list[str] = []
    # TODO: Extract from Literal types or enum fields if needed

    return UnifiedJobParameterModel(
        name=name,
        type=_python_type_to_job_param_type(python_type),
        required=is_required,
        description=field_info.description,
        default_value=default_value if default_value is not None else None,
        possible_values=possible_values,
        max_length=max_length,
    )


def params_model_to_job_params(
    params_model: type[BaseJobParams],
) -> list[UnifiedJobParameterModel]:
    """Convert a Pydantic model to a list of UnifiedJobParameterModel."""
    parameters: list[UnifiedJobParameterModel] = []

    # Get type hints for the model
    type_hints = get_type_hints(params_model)

    # Iterate over model fields
    for field_name, field_info in params_model.model_fields.items():
        python_type = type_hints.get(field_name, str)
        param = _field_to_job_parameter(field_name, field_info, python_type)
        parameters.append(param)

    return parameters


def job[TParams: BaseJobParams](
    job_type: str,
    name: str,
    description: str,
    category: JobCategory,
    params_model: type[TParams],
    required_permissions: list[str],
    display_parameter: str | None = None,
    is_system_job: bool = False,
    icon: str | None = None,
) -> Any:
    """
    Decorator to define job metadata with a Pydantic parameter model.

    This decorator attaches metadata and parameter validation to a job class.
    The params_model is used to:
    1. Generate UnifiedJobParameterModel list for job registration
    2. Validate and parse parameters before job execution
    3. Provide type hints for execute_job method

    Args:
        job_type: Unique job type identifier (e.g., 'python.jobs.ExecuteQueryJob')
        name: Human-readable job name
        description: Job description
        category: Job category from JobCategory enum
        params_model: Pydantic model class for job parameters
        required_permissions: List of permission claim strings required to execute
        display_parameter: Optional parameter name surfaced as a short run summary
            (e.g. the SQL column for query jobs). Used by the API to build a
            human-readable job-run summary without hardcoding job types.
        is_system_job: Whether this is a system/internal job
        icon: Optional icon identifier for UI

    Example:
        @job(
            job_type="python.jobs.ExecuteQueryJob",
            name="Execute Query",
            description="Executes SQL queries in DuckDB sessions",
            category=JobCategory.DATAPROCESSING,
            params_model=ExecuteQueryParams,
            required_permissions=JobRequiredPermissions.QUERY_EXECUTE,
            is_system_job=True)
        class ExecuteQueryJob(BasePythonJob):
            async def execute_job(
                self, context: JobContext, params: ExecuteQueryParams
            ) -> JobResult:
                # params is now a validated Pydantic model
                sql = params.sql  # Type-safe access
    """

    def decorator(cls: type) -> type:
        # Store metadata on the class
        cls.JOB_TYPE = job_type
        cls.PARAMS_MODEL = params_model
        cls.DISPLAY_PARAMETER = display_parameter

        # Generate the UnifiedJobTypeModel
        cls.METADATA = UnifiedJobTypeModel(
            type=job_type,
            name=name,
            description=description,
            category=category,
            runtime=JobExecutionRuntime.PYTHON,
            parameters=params_model_to_job_params(params_model),
            required_permissions=required_permissions,
            is_system_job=is_system_job,
            icon=icon,
        )

        # Add class methods for accessing metadata
        @classmethod
        def get_job_metadata(cls_inner) -> UnifiedJobTypeModel:
            return cls.METADATA

        @classmethod
        def get_params_model(cls_inner) -> type[BaseJobParams]:
            return cls.PARAMS_MODEL

        @classmethod
        def get_job_type(cls_inner) -> str:
            return cls.JOB_TYPE

        # Attach methods to the class
        cls.get_job_metadata = get_job_metadata
        cls.get_params_model = get_params_model
        cls.get_job_type = get_job_type

        return cls

    return decorator
