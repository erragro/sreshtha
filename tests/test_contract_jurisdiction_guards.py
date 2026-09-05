"""Regression tests for state-specific legal references in Contract Reader."""

from app.contracts.stage2 import _remove_inapplicable_state_citations
from app.contracts.stage3 import _rule_applies_in_jurisdiction


def test_stage2_removes_rajasthan_citation_for_maharashtra_contract():
    annotations = [{
        "clause_id": "c-1",
        "citation": {
            "name": "Rajasthan Platform Based Gig Workers (Registration and Welfare) Act, 2023",
            "section": "Section 3",
            "url": "https://labour.rajasthan.gov.in",
        },
        "note": "This is a reference.",
    }]

    _remove_inapplicable_state_citations(annotations, "Maharashtra")

    assert annotations[0]["citation"] == {"name": None, "section": None, "url": None}
    assert "omitted" in annotations[0]["note"]


def test_stage2_keeps_matching_state_citation():
    annotations = [{
        "clause_id": "c-1",
        "citation": {
            "name": "Rajasthan Platform Based Gig Workers (Registration and Welfare) Act, 2023",
            "section": "Section 3",
            "url": "https://labour.rajasthan.gov.in",
        },
        "note": "This is a reference.",
    }]

    _remove_inapplicable_state_citations(annotations, "Rajasthan")

    assert annotations[0]["citation"]["name"].startswith("Rajasthan")


def test_stage3_does_not_apply_state_rule_outside_its_jurisdiction():
    rule = {
        "citation": {
            "name": "Karnataka Platform-Based Gig Workers (Social Security and Welfare) Ordinance, 2024",
        },
    }

    assert not _rule_applies_in_jurisdiction(rule, {"jurisdiction": "Maharashtra"})
    assert _rule_applies_in_jurisdiction(rule, {"jurisdiction": "Karnataka"})
    assert _rule_applies_in_jurisdiction(
        {"citation": {"name": "Code on Social Security, 2020"}},
        {"jurisdiction": "Maharashtra"},
    )
