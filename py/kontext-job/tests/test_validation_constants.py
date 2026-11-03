"""Guards for the shared job-parameter validation constants.

The Python execution jobs accept a `code` string parameter whose cap must stay
within the generic string-parameter cap, otherwise the job fails registry
validation at import time instead of executing.
"""

from __future__ import annotations

from kontext.common.constants import MAX_PYTHON_CODE_CHARS
from kontext.jobs.validation_constants import JobValidationConstants


def test_string_parameter_cap_accommodates_python_code() -> None:
    assert JobValidationConstants.MAX_STRING_PARAMETER_LENGTH >= MAX_PYTHON_CODE_CHARS, (
        "MAX_STRING_PARAMETER_LENGTH must stay >= MAX_PYTHON_CODE_CHARS or "
        "ExecutePythonScriptJob/ExecuteNotebookPythonJob fail registry validation"
    )
