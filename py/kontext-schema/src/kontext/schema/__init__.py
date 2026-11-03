"""Kontext schema models generated from the shared Zod contract.

Generated modules live in :mod:`kontext.schema._generated` and are rewritten by
``pnpm run generate:models``. This module and :mod:`kontext.schema.base` are
hand-written and survive regeneration.
"""

from ._generated import *  # noqa: F403
from ._generated import __all__ as _generated_all
from .base import SchemaModel

__all__ = [*_generated_all, "SchemaModel"]  # pyright: ignore[reportUnsupportedDunderAll]
