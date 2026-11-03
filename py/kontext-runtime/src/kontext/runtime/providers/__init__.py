"""Runtime composition providers.

`base` defines the provider contract surface.
`local` composes capabilities that are resolved inside the current Python
process (direct database/storage access), as opposed to delegating over the
API client.
"""

from .local import LocalRuntimeProvider

__all__ = ["LocalRuntimeProvider"]
