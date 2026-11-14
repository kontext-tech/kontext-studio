"""Python job registry for discovering and managing Python job implementations."""

import importlib
import inspect
import json
import logging
import os
import pkgutil

from kontext.jobs.base import IPythonJob, PythonJobRegistration
from kontext.jobs.validation_constants import JobValidationConstants
from kontext.schema import JobParameterType, UnifiedJobParameterModel

# Type alias for readability
JobParameterDefinition = UnifiedJobParameterModel


class JobValidationError(Exception):
    """Exception raised when job validation fails"""

    pass


class JobValidationHelpers:
    """Helper methods for validating job definitions"""

    @staticmethod
    def is_valid_json(data: str) -> bool:
        """Validates that the string is valid JSON"""
        if not data or not data.strip():
            return True
        try:
            json.loads(data)
            return True
        except (json.JSONDecodeError, TypeError):
            return False

    @staticmethod
    def validate_job_registration(metadata: PythonJobRegistration) -> None:
        """
        Validates job registration metadata according to Kontext standards

        Raises:
            JobValidationError: If validation fails
        """
        errors = []

        # Validate job name
        if not metadata.name:
            errors.append("Job name is required")
        elif len(str(metadata.name)) > JobValidationConstants.MAX_JOB_NAME_LENGTH:
            errors.append(
                f"Job name cannot exceed {JobValidationConstants.MAX_JOB_NAME_LENGTH} characters"
            )
        elif not JobValidationConstants.JOB_NAME_PATTERN.match(str(metadata.name)):
            errors.append(
                "Job name can only contain letters, numbers, spaces, "
                "hyphens, underscores, and periods"
            )

        # Validate job type
        if not metadata.type:
            errors.append("Job type is required")
        elif len(str(metadata.type)) > JobValidationConstants.MAX_JOB_TYPE_LENGTH:
            errors.append(
                f"Job type cannot exceed {JobValidationConstants.MAX_JOB_TYPE_LENGTH} characters"
            )
        elif not JobValidationConstants.JOB_TYPE_PATTERN.match(str(metadata.type)):
            errors.append("Job type must be a valid class name format")

        # Validate description
        if (
            metadata.description
            and len(str(metadata.description)) > JobValidationConstants.MAX_JOB_DESCRIPTION_LENGTH
        ):
            errors.append(
                f"Job description cannot exceed "
                f"{JobValidationConstants.MAX_JOB_DESCRIPTION_LENGTH} characters"
            )

        # Validate category
        if not metadata.category:
            errors.append("Job category is required")
        elif len(str(metadata.category)) > JobValidationConstants.MAX_JOB_CATEGORY_LENGTH:
            errors.append(
                f"Job category cannot exceed "
                f"{JobValidationConstants.MAX_JOB_CATEGORY_LENGTH} characters"
            )

        # Validate parameters
        if metadata.parameters:
            for i, param in enumerate(metadata.parameters):
                JobValidationHelpers._validate_job_parameter(param, i, errors)

        if errors:
            raise JobValidationError(f"Job validation failed: {', '.join(errors)}")

    @staticmethod
    def _validate_job_parameter(
        param: JobParameterDefinition, index: int, errors: list[str]
    ) -> None:
        """Validates a single job parameter definition"""
        param_prefix = f"Parameter {index + 1}"

        # Validate parameter name
        if not param.name:
            errors.append(f"{param_prefix}: Parameter name is required")
        elif len(str(param.name)) > JobValidationConstants.MAX_PARAMETER_NAME_LENGTH:
            errors.append(
                f"{param_prefix}: Parameter name cannot exceed "
                f"{JobValidationConstants.MAX_PARAMETER_NAME_LENGTH} characters"
            )
        elif not JobValidationConstants.PARAMETER_NAME_PATTERN.match(str(param.name)):
            errors.append(
                f"{param_prefix}: Parameter name must be a valid identifier "
                f"(letters, numbers, underscores, starting with letter or underscore)"
            )

        # Validate description
        if (
            param.description
            and len(str(param.description))
            > JobValidationConstants.MAX_PARAMETER_DESCRIPTION_LENGTH
        ):
            errors.append(
                f"{param_prefix}: Parameter description cannot exceed "
                f"{JobValidationConstants.MAX_PARAMETER_DESCRIPTION_LENGTH} characters"
            )

        # Validate max_length for string parameters
        if param.type == JobParameterType.STRING.value and param.max_length is not None:
            if param.max_length <= 0:
                errors.append(
                    f"{param_prefix}: max_length must be greater than 0 for string parameters"
                )
            elif param.max_length > JobValidationConstants.MAX_STRING_PARAMETER_LENGTH:
                errors.append(
                    f"{param_prefix}: max_length cannot exceed "
                    f"{JobValidationConstants.MAX_STRING_PARAMETER_LENGTH} "
                    f"for string parameters"
                )

        # Validate default value type consistency
        if param.default_value is not None:
            JobValidationHelpers._validate_parameter_value_type(
                param, param.default_value, f"{param_prefix} default_value", errors
            )

    @staticmethod
    def _validate_parameter_value_type(
        param: JobParameterDefinition, value, context: str, errors: list[str]
    ) -> None:
        """Validates that a parameter value matches the expected type"""
        param_type_str = str(param.type) if param.type else ""
        if param_type_str == JobParameterType.STRING.value and not isinstance(value, str):
            errors.append(f"{context}: Expected string value for STRING parameter")
        elif param_type_str == JobParameterType.INTEGER.value and not isinstance(value, int):
            errors.append(f"{context}: Expected integer value for INTEGER parameter")
        elif param_type_str == JobParameterType.BOOLEAN.value and not isinstance(value, bool):
            errors.append(f"{context}: Expected boolean value for BOOLEAN parameter")

        # Validate string length if max_length is specified
        if (
            param_type_str == JobParameterType.STRING.value
            and param.max_length is not None
            and isinstance(value, str)
        ) and len(value) > param.max_length:
            errors.append(f"{context}: String value exceeds max_length of {param.max_length}")


class PythonJobRegistry:
    """Registry for discovering and managing Python job implementations"""

    def __init__(self):
        self._jobs: dict[str, type[IPythonJob]] = {}
        self._metadata: dict[str, PythonJobRegistration] = {}
        self.logger = logging.getLogger(__name__)

        # Auto-discover jobs on initialization
        self._discover_jobs()

    def register_job(self, job_class: type[IPythonJob]) -> None:
        """
        Register a Python job class with validation

        Args:
            job_class: Class implementing IPythonJob interface

        Raises:
            ValueError: If job class doesn't implement IPythonJob or has
                invalid metadata
            JobValidationError: If job metadata fails validation
        """
        if not issubclass(job_class, IPythonJob):
            raise ValueError(f"Job class {job_class} must implement IPythonJob")

        metadata = job_class.get_job_metadata()
        if metadata is None or not hasattr(metadata, "type") or not metadata.type:
            raise ValueError(f"Job class {job_class} returned invalid metadata")

        # Validate the job metadata
        try:
            JobValidationHelpers.validate_job_registration(metadata)
        except JobValidationError as e:
            self.logger.error(f"Job validation failed for {job_class.__name__}: {e}")
            raise

        # Check for duplicate job types
        if metadata.type in self._jobs:
            existing_class = self._jobs[metadata.type]
            raise ValueError(
                f"Job type '{metadata.type}' is already registered by {existing_class}"
            )

        self._jobs[metadata.type] = job_class
        self._metadata[metadata.type] = metadata
        self.logger.info(f"Registered Python job: {metadata.type} ({job_class.__name__})")

    def get_all_jobs(self) -> list[PythonJobRegistration]:
        """Get all registered Python jobs metadata"""
        return list(self._metadata.values())

    def get_job_metadata(self, job_type: str) -> PythonJobRegistration | None:
        """Get metadata for a specific job type"""
        return self._metadata.get(job_type)

    def get_job_class(self, job_type: str) -> type[IPythonJob] | None:
        """Get the registered job class for a job type"""
        return self._jobs.get(job_type)

    def create_job_instance(self, job_type: str) -> IPythonJob | None:
        """Create an instance of the specified job type"""
        job_class = self._jobs.get(job_type)
        if job_class:
            return job_class()
        return None

    def is_job_registered(self, job_type: str) -> bool:
        """Check if a job type is registered"""
        return job_type in self._jobs

    def _discover_jobs(self) -> None:
        """Auto-discover job implementations from domain-owned packages."""
        for package_name in self._get_discovery_packages():
            try:
                package = importlib.import_module(package_name)
            except ModuleNotFoundError:
                self.logger.debug("Job discovery package %s is not installed", package_name)
                continue
            except Exception as e:
                self.logger.warning(
                    "Failed to import job discovery package %s: %s",
                    package_name,
                    e,
                )
                continue

            package_paths = getattr(package, "__path__", None)
            if not package_paths:
                self.logger.warning(
                    "Could not determine package path for job discovery package %s",
                    package_name,
                )
                continue

            for module_info in pkgutil.iter_modules(package_paths):
                if module_info.name.startswith("_"):
                    continue

                module_name = f"{package_name}.{module_info.name}"
                try:
                    self._discover_jobs_in_module(module_name)
                except Exception as e:
                    self.logger.warning(
                        "Failed to discover jobs in %s: %s",
                        module_name,
                        e,
                    )

    @staticmethod
    def _get_discovery_packages() -> list[str]:
        """Return the ordered list of packages scanned for job definitions."""
        default_packages = [
            "kontext.jobs.definitions",
            "kontext.query.jobs",
            "kontext.catalog.jobs",
            "kontext.file.jobs",
            "kontext.project.jobs",
        ]
        env_packages = [
            package.strip()
            for package in os.getenv("KONTEXT_JOB_DISCOVERY_PACKAGES", "").split(",")
            if package.strip()
        ]

        ordered_packages: list[str] = []
        for package_name in [*default_packages, *env_packages]:
            if package_name not in ordered_packages:
                ordered_packages.append(package_name)
        return ordered_packages

    def _discover_jobs_in_module(self, module_name: str) -> None:
        """Discover jobs in a specific module"""
        try:
            module = importlib.import_module(module_name)

            # Find all classes that implement IPythonJob
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    obj.__module__ == module_name  # Only classes defined in this module
                    and issubclass(obj, IPythonJob)
                    and obj != IPythonJob  # Exclude the interface itself
                    and not inspect.isabstract(obj)  # Exclude abstract classes
                    and hasattr(obj, "get_job_metadata")
                ):
                    # Validate that get_job_metadata returns valid data
                    try:
                        metadata = obj.get_job_metadata()
                        if metadata is None or not hasattr(metadata, "type") or not metadata.type:
                            self.logger.warning(
                                f"Skipping {name} from {module_name}: "
                                f"get_job_metadata() returned invalid data"
                            )
                            continue

                        # Register the job (this will validate the metadata)
                        self.register_job(obj)
                        self.logger.info(f"Successfully registered job: {name} ({metadata.type})")

                    except JobValidationError as e:
                        self.logger.warning(
                            f"Skipping {name} from {module_name}: Job validation failed: {e}"
                        )
                        continue
                    except Exception as e:
                        self.logger.warning(
                            f"Skipping {name} from {module_name}: Registration failed: {e}"
                        )
                        continue

        except ImportError as e:
            self.logger.debug(f"Could not import module {module_name}: {e}")
        except Exception as e:
            self.logger.warning(f"Error discovering jobs in {module_name}: {e}")


# Global registry instance
_registry = None


def get_job_registry() -> PythonJobRegistry:
    """Get the global job registry instance"""
    global _registry
    if _registry is None:
        _registry = PythonJobRegistry()
    return _registry


def register_job(job_class: type[IPythonJob]) -> None:
    """Register a job with the global registry"""
    get_job_registry().register_job(job_class)
