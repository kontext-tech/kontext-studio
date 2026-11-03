"""Test-support utilities.

These functions exist for route-introspection assertions in tests. Keeping
them out of :mod:`kontext.api.helpers` keeps the production surface free of
test scaffolding while remaining importable as a public testing namespace.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from fastapi import FastAPI
from fastapi.routing import APIRoute


def iter_effective_api_routes(app: FastAPI) -> Iterator[Any]:
    """Yield the effective :class:`~fastapi.routing.RouteContext` for every API route.

    FastAPI 0.137+ keeps routers included via ``include_router`` as a tree of
    ``_IncludedRouter`` nodes instead of flattening each path operation into
    ``router.routes``. Use ``iter_route_contexts`` to walk that tree and yield
    each route with its mounted ``path`` (including any ``include_router``
    prefix) and resolved ``methods`` -- what the OpenAPI schema and request
    router actually use.
    """
    from fastapi.routing import iter_route_contexts

    for context in iter_route_contexts(app.router.routes):
        if isinstance(context.original_route, APIRoute):
            yield context
