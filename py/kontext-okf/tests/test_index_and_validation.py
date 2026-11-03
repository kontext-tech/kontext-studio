"""Tests for OKF index generation (§8) and conformance validation (§11)."""

from __future__ import annotations

from kontext.okf import (
    OkfBundle,
    OkfConcept,
    load_bundle,
    validate_bundle,
    write_bundle,
)


def _bundle() -> OkfBundle:
    return OkfBundle(
        name="demo",
        concepts=[
            OkfConcept(
                id="tables/orders",
                type="BigQuery Table",
                title="Orders",
                description="One row per order.",
            ),
            OkfConcept(id="tables/customers", type="BigQuery Table", title="Customers"),
            OkfConcept(
                id="metrics/revenue",
                type="Metric",
                title="Revenue",
                description="Recognized revenue.",
            ),
            OkfConcept(id="notes", type="Reference", title="Notes"),
        ],
    )


class TestIndexGeneration:
    def test_root_index_declares_okf_version(self, tmp_path) -> None:
        root = tmp_path / "bundle"
        write_bundle(_bundle(), root)
        index = (root / "index.md").read_text(encoding="utf-8")
        assert 'okf_version: "0.2"' in index
        assert "# Subdirectories" in index
        assert "(tables/index.md)" in index
        assert "# Concepts" in index
        assert "(notes.md)" in index

    def test_subdirectory_index_lists_concepts(self, tmp_path) -> None:
        root = tmp_path / "bundle"
        write_bundle(_bundle(), root)
        index = (root / "tables" / "index.md").read_text(encoding="utf-8")
        assert "[Orders](orders.md)" in index
        assert "One row per order." in index
        # Non-root index carries no frontmatter (§8).
        assert not index.startswith("---")

    def test_generated_bundle_is_conformant(self, tmp_path) -> None:
        root = tmp_path / "bundle"
        write_bundle(_bundle(), root)
        result = validate_bundle(root)
        assert result.conformant, result.issues
        assert result.concept_count == 4

    def test_index_files_are_not_loaded_as_concepts(self, tmp_path) -> None:
        root = tmp_path / "bundle"
        write_bundle(_bundle(), root)
        reloaded = load_bundle(root)
        assert sorted(c.id or "" for c in reloaded) == [
            "metrics/revenue",
            "notes",
            "tables/customers",
            "tables/orders",
        ]

    def test_write_index_can_be_disabled(self, tmp_path) -> None:
        root = tmp_path / "bundle"
        write_bundle(_bundle(), root, write_index=False)
        assert not (root / "index.md").exists()


class TestConformanceValidation:
    def test_valid_concepts_pass(self, tmp_path) -> None:
        root = tmp_path
        (root / "a.md").write_text("---\ntype: Metric\n---\nbody\n", encoding="utf-8")
        result = validate_bundle(root)
        assert result.conformant
        assert result.concept_count == 1

    def test_missing_frontmatter_is_rule_1(self, tmp_path) -> None:
        (tmp_path / "c.md").write_text("no frontmatter\n", encoding="utf-8")
        result = validate_bundle(tmp_path)
        assert not result.conformant
        assert any(issue.rule == 1 for issue in result.issues)

    def test_missing_type_is_rule_2(self, tmp_path) -> None:
        (tmp_path / "b.md").write_text("---\ntitle: X\n---\nbody\n", encoding="utf-8")
        result = validate_bundle(tmp_path)
        assert any(issue.rule == 2 for issue in result.issues)

    def test_bad_log_heading_is_rule_3(self, tmp_path) -> None:
        (tmp_path / "log.md").write_text("# Log\n\n## June 1\n* init\n", encoding="utf-8")
        result = validate_bundle(tmp_path)
        assert any(issue.rule == 3 and issue.path == "log.md" for issue in result.issues)

    def test_non_root_index_frontmatter_is_rule_3(self, tmp_path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "index.md").write_text("---\ntitle: sub\n---\n", encoding="utf-8")
        result = validate_bundle(tmp_path)
        assert any(issue.rule == 3 for issue in result.issues)

    def test_root_index_extra_keys_is_rule_3(self, tmp_path) -> None:
        (tmp_path / "index.md").write_text(
            "---\nokf_version: '0.2'\nowner: me\n---\n\n# X\n", encoding="utf-8"
        )
        result = validate_bundle(tmp_path)
        assert any(issue.rule == 3 for issue in result.issues)

    def test_missing_directory_reports_issue(self, tmp_path) -> None:
        result = validate_bundle(tmp_path / "does-not-exist")
        assert not result.conformant
