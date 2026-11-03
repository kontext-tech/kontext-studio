"""
Base classes and interfaces for Python job implementations.

Uses PEP 695 generic syntax for type-safe parameter handling.
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

from kontext.schema import UnifiedJobTypeModel

from .cancellation import JobCancelledError
from .job_context import JobContext
from .job_result import JobResult

# Type alias for better readability
PythonJobRegistration = UnifiedJobTypeModel


class BaseJobParams(BaseModel):
    """
    Base class for all job parameter models.

    All job parameter models should inherit from this class to ensure
    consistent configuration and behavior across all jobs.

    Configuration:
        - extra="forbid": Reject unknown parameters
        - populate_by_name=True: Allow both snake_case and camelCase
        - alias_generator=to_camel: Generate camelCase aliases for API
        - validate_assignment=True: Validate on attribute assignment
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=to_camel,
        validate_assignment=True,
    )


class IPythonJob[TParams: BaseJobParams](ABC):
    """
    Interface that all Python jobs must implement.

    Type parameter TParams specifies the Pydantic model for job parameters.
    """

    @abstractmethod
    async def execute(self, context: JobContext, parameters: dict[str, Any]) -> JobResult:
        """
        Execute the job with given parameters.

        Args:
            context: Job execution context with logging and utilities
            parameters: Job parameters as a dictionary

        Returns:
            JobResult indicating success/failure and any result data
        """
        pass

    @classmethod
    def get_job_metadata(cls) -> PythonJobRegistration:
        """
        Return job metadata for registration.

        This method is provided by the @job decorator.

        Returns:
            PythonJobRegistration with job information and parameters

        Raises:
            NotImplementedError: If @job decorator is not applied
        """
        raise NotImplementedError(f"{cls.__name__} must use the @job decorator")

    @classmethod
    def get_params_model(cls) -> type[TParams]:
        """
        Return the Pydantic parameter model class for this job.

        This method is set by the @job decorator.

        Returns:
            Pydantic model class for job parameters

        Raises:
            ValueError: If @job decorator is not applied
        """
        model = getattr(cls, "PARAMS_MODEL", None)
        if model is None:
            raise ValueError(f"{cls.__name__} must use the @job decorator with params_model")
        return model

    @classmethod
    def get_display_parameter(cls) -> str | None:
        """
        Return the parameter name surfaced as a short job-run summary, if any.

        Set via the @job decorator's ``display_parameter`` argument.

        Returns:
            Parameter name to surface, or None when the job has no summary.
        """
        return getattr(cls, "DISPLAY_PARAMETER", None)


class BasePythonJob[TParams: BaseJobParams](IPythonJob[TParams]):
    """
    Base implementation providing common functionality for Python jobs.

    Subclasses should:
    1. Apply the @job decorator with params_model
    2. Implement execute_job() with the typed parameter model
    """

    async def execute(self, context: JobContext, parameters: dict[str, Any]) -> JobResult:
        """Execute with parameter validation and error handling."""
        try:
            # Validate and parse parameters using Pydantic
            params_model = self.get_params_model()
            try:
                typed_params = params_model.model_validate(parameters)
            except ValidationError as e:
                errors = []
                for error in e.errors():
                    field = ".".join(str(loc) for loc in error["loc"])
                    msg = error["msg"]
                    errors.append(f"Parameter '{field}': {msg}")
                return JobResult.error_result(
                    message=f"Parameter validation failed: {'; '.join(errors)}",
                    error_code="PARAMETER_VALIDATION_ERROR",
                )

            # Execute the actual job
            await context.log_info(f"Starting job execution: {self.__class__.__name__}")

            result = await self.execute_job(context, typed_params)

            await context.log_info(f"Job execution completed: {result.success}")

            return result

        except JobCancelledError:
            # Let cooperative cancellation propagate so the executor records the
            # run as cancelled rather than failed.
            raise
        except Exception as e:
            await context.log_error(f"Job execution failed: {e!s}")
            return JobResult.from_exception(e)

    @abstractmethod
    async def execute_job(self, context: JobContext, parameters: TParams) -> JobResult:
        """
        Implement the actual job logic here.

        Args:
            context: Job execution context
            parameters: Validated Pydantic model instance

        Returns:
            JobResult indicating success/failure
        """
        pass
