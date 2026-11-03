"""OKF markdown + YAML frontmatter serialization.

An OKF concept file is::

    ---
    type: Metric
    title: ...
    description: ...
    tags: [...]
    status: stable
    generated: {by: human:jane, at: 2026-06-30T14:00:00Z}
    verified: [{by: process:ci, at: 2026-07-01T00:00:00Z}]
    stale_after: 2026-12-31T00:00:00Z
    sources: [...]
    ...
    ---
    <markdown body>

Every timestamp-valued key is an ISO 8601 datetime with an explicit UTC offset
(OKF §5). This module converts between :class:`OkfConcept` and that text shape.
It leans on Pydantic's own validation (``model_validate``) for nested fields and
uses PyYAML only for the frontmatter block itself, keeping the body verbatim.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import yaml

from .concept import OkfConcept

#: OKF frontmatter is delimited by ``---`` lines.
_FRONTMATTER_DELIMITER = "---"


def _iso_timestamp(value: date | datetime) -> str:
    """Render a date/datetime as an ISO 8601 datetime with an explicit offset.

    OKF v0.2 (Aug 2026 revision) requires every timestamp-valued key
    (``stale_after``, ``sources[].last_modified``, ``generated.at``,
    ``verified[].at``) to be an ISO 8601 datetime carrying a UTC offset. Our
    model types some of these as plain ``date``; promote them to midnight UTC
    so the emitted bundle stays conformant. Naive datetimes are assumed UTC.
    """
    if isinstance(value, datetime):
        moment = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    else:
        moment = datetime(value.year, value.month, value.day, tzinfo=UTC)
    # Prefer the ``Z`` suffix for UTC to match the spec's canonical examples.
    return moment.isoformat().replace("+00:00", "Z")


def _normalize_yaml_value(value: Any) -> Any:
    """Recursively render free-form YAML values with spec-conformant timestamps.

    Free-form fields (``usage_window`` and other producer extensions) may hold
    nested date/datetime objects after YAML parsing. PyYAML would dump those in
    its own non-ISO 8601 shape (``2026-06-01 00:00:00+00:00``); OKF §5 requires
    ISO 8601 datetimes with an explicit offset, so convert them. Lists and
    mappings are normalized in place; other scalars pass through untouched.
    """
    if isinstance(value, datetime | date):
        return _iso_timestamp(value)
    if isinstance(value, dict):
        return {key: _normalize_yaml_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_yaml_value(item) for item in value]
    return value


def concept_to_frontmatter(concept: OkfConcept) -> str:
    """Serialize an :class:`OkfConcept` to a full OKF markdown file string."""
    frontmatter = _concept_to_frontmatter_dict(concept)
    yaml_block = yaml.safe_dump(
        frontmatter, sort_keys=False, allow_unicode=True, default_flow_style=False
    ).strip()
    body = concept.body.strip()
    if body:
        return f"{_FRONTMATTER_DELIMITER}\n{yaml_block}\n{_FRONTMATTER_DELIMITER}\n{body}\n"
    return f"{_FRONTMATTER_DELIMITER}\n{yaml_block}\n{_FRONTMATTER_DELIMITER}\n"


def concept_from_frontmatter(text: str) -> OkfConcept:
    """Parse an OKF markdown file string into an :class:`OkfConcept`.

    Raises ``ValueError`` if the frontmatter block is missing or malformed.
    """
    frontmatter, body = _split_frontmatter(text)
    data = _parse_yaml(frontmatter)
    return _concept_from_mapping(data, body)


# ---------------------------------------------------------------------------
# Dump (concept -> dict)
# ---------------------------------------------------------------------------


def _concept_to_frontmatter_dict(concept: OkfConcept) -> dict[str, Any]:
    """Build the YAML frontmatter mapping for a concept.

    Core fields are always present; optional fields are omitted entirely when
    unset (so a minimal concept produces minimal frontmatter). Unknown
    frontmatter keys preserved on load (``additional_properties``) are written
    back verbatim, per OKF §4.1 ("consumers MUST preserve unknown keys").
    """
    data: dict[str, Any] = {
        "type": concept.type,
    }
    if concept.id is not None:
        data["id"] = concept.id
    if concept.title is not None:
        data["title"] = concept.title
    if concept.description is not None:
        data["description"] = concept.description
    if concept.resource is not None:
        data["resource"] = concept.resource
    if concept.tags:
        data["tags"] = list(concept.tags)
    if concept.status is not None:
        data["status"] = concept.status
    if concept.timestamp is not None:
        data["timestamp"] = _iso_timestamp(concept.timestamp)

    att = concept.attestation
    if att is not None:
        if att.generated is not None:
            generated: dict[str, Any] = {"by": att.generated.by}
            if att.generated.at is not None:
                generated["at"] = _iso_timestamp(att.generated.at)
            data["generated"] = generated
        if att.verified:
            data["verified"] = [_actor_to_frontmatter(actor) for actor in att.verified]
        if att.stale_after is not None:
            data["stale_after"] = _iso_timestamp(att.stale_after)
        if att.sources:
            # snake_case keys (``last_modified`` / ``usage_count``) per OKF; the
            # generated models alias these to camelCase for the HTTP API only.
            data["sources"] = [_source_to_frontmatter(src) for src in att.sources]
        if att.usage_window is not None:
            data["usage_window"] = _normalize_yaml_value(dict(att.usage_window))
        if att.runtime is not None:
            data["runtime"] = att.runtime
        if att.parameters:
            data["parameters"] = _normalize_yaml_value(list(att.parameters))
        if att.computation is not None:
            data["computation"] = att.computation
        if att.executor is not None:
            data["executor"] = _normalize_yaml_value(dict(att.executor))
        if att.attester is not None:
            data["attester"] = _normalize_yaml_value(dict(att.attester))

    if concept.metadata:
        data["metadata"] = _normalize_yaml_value(dict(concept.metadata))

    # Preserve unknown keys verbatim so a round-trip is lossless.
    for key, value in (concept.additional_properties or {}).items():
        if key not in data:
            data[key] = _normalize_yaml_value(value)
    return data


def _actor_to_frontmatter(actor: Any) -> dict[str, Any]:
    """Serialize an ``OkfProvenanceActor``; omit an unset ``at`` (§5.2)."""
    data: dict[str, Any] = {"by": actor.by}
    if actor.at is not None:
        data["at"] = _iso_timestamp(actor.at)
    return data


def _source_to_frontmatter(source: Any) -> dict[str, Any]:
    """Serialize an ``OkfSource`` with OKF snake_case keys and ISO datetime.

    ``id`` and the credibility signals are optional (OKF §5.1), so they are
    omitted when unset rather than emitted as ``null``.
    """
    data = source.model_dump(exclude_none=True)
    if data.get("last_modified") is not None:
        data["last_modified"] = _iso_timestamp(data["last_modified"])
    if data.get("usage_window") is not None:
        data["usage_window"] = _normalize_yaml_value(data["usage_window"])
    return data


# ---------------------------------------------------------------------------
# Load (dict -> concept)
# ---------------------------------------------------------------------------


def _split_frontmatter(text: str) -> tuple[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
        raise ValueError("OKF concept must start with a '---' frontmatter delimiter")
    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_DELIMITER:
            end_index = index
            break
    if end_index is None:
        raise ValueError("OKF frontmatter is not closed with a '---' delimiter")
    frontmatter = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :]).strip()
    return frontmatter, body


def _parse_yaml(frontmatter: str) -> dict[str, Any]:
    if not frontmatter.strip():
        return {}
    data = yaml.safe_load(frontmatter)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("OKF frontmatter must be a YAML mapping")
    return data


_ATTESTATION_KEYS = {
    "generated",
    "verified",
    "stale_after",
    "sources",
    "runtime",
    "parameters",
    "computation",
    "executor",
    "attester",
    "usage_window",
}


def _concept_from_mapping(data: dict[str, Any], body: str) -> OkfConcept:
    # OKF §9: the only required frontmatter field is a non-empty ``type``.
    if not data.get("type"):
        raise ValueError("OKF frontmatter is missing the required 'type' field")

    mapping = dict(data)
    attestation_data = {
        k: mapping.pop(k) for k in _ATTESTATION_KEYS if k in mapping and mapping[k] is not None
    }

    if "stale_after" in attestation_data:
        val = attestation_data["stale_after"]
        if isinstance(val, date | datetime):
            attestation_data["stale_after"] = val.isoformat()

    if "generated" in attestation_data and isinstance(attestation_data["generated"], dict):
        gen = dict(attestation_data["generated"])
        if isinstance(gen.get("at"), date | datetime):
            gen["at"] = gen["at"].isoformat()
        attestation_data["generated"] = gen

    # OKF v0.2 defines ``verified`` as a list. Accept a single mapping too
    # (v0.1-style) by wrapping it, so older bundles stay readable.
    verified = attestation_data.get("verified")
    if isinstance(verified, dict):
        verified = [verified]
    if isinstance(verified, list):
        cleaned_verified = []
        for actor in verified:
            if isinstance(actor, dict):
                actor_dict = dict(actor)
                if isinstance(actor_dict.get("at"), date | datetime):
                    actor_dict["at"] = actor_dict["at"].isoformat()
                cleaned_verified.append(actor_dict)
        attestation_data["verified"] = cleaned_verified

    if "sources" in attestation_data and isinstance(attestation_data["sources"], list):
        cleaned_sources = []
        for src in attestation_data["sources"]:
            if isinstance(src, dict):
                src_dict = dict(src)
                if isinstance(src_dict.get("last_modified"), date | datetime):
                    src_dict["last_modified"] = src_dict["last_modified"].isoformat()
                cleaned_sources.append(src_dict)
        attestation_data["sources"] = cleaned_sources

    if attestation_data:
        mapping["attestation"] = attestation_data

    # Everything not explicitly modeled is a producer extension. ``OkfConcept``
    # is an open model (``extra="allow"``), so unknown keys left on the mapping
    # survive validation and a round-trip (OKF §4.1).
    mapping["body"] = body

    try:
        return OkfConcept.model_validate(mapping)
    except Exception as exc:
        raise ValueError(f"Failed to parse OKF concept frontmatter: {exc}") from exc
