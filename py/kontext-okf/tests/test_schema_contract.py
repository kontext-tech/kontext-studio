"""Contract tests for the OKF model surface."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from kontext.okf import OkfAttestation, OkfConcept, OkfProvenanceActor, OkfSource


def test_okf_models_are_exported_from_the_okf_package() -> None:
    concept = OkfConcept(
        id="tables/orders",
        type="table",
        title="Orders",
        description="Customer orders",
        tags=["finance"],
        status="active",
        attestation=OkfAttestation(
            generated=OkfProvenanceActor(
                by="human:test",
                at=datetime(2026, 1, 1, 0, 0, 0),
            ),
            verified=[
                OkfProvenanceActor(
                    by="human:test",
                    at=datetime(2026, 1, 2, 0, 0, 0),
                )
            ],
            sources=[
                OkfSource(
                    id="ref-1",
                    resource="https://example.test/orders",
                )
            ],
        ),
    )

    assert concept.id == "tables/orders"
    assert concept.attestation is not None
    assert concept.attestation.generated is not None
    assert concept.attestation.verified
    assert concept.attestation.sources[0].resource == "https://example.test/orders"


def test_date_like_fields_require_valid_iso_dates() -> None:
    with pytest.raises(ValidationError):
        OkfConcept(
            id="tables/orders",
            type="table",
            title="Orders",
            attestation=OkfAttestation(
                stale_after="not-a-date",  # type: ignore[arg-type]
                sources=[
                    OkfSource(
                        id="ref-1",
                        resource="https://example.test/orders",
                    )
                ],
            ),
        )
