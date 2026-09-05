"""Unit tests for the idiom library detector + placeholder flow.

Uses the real DB seeds from migration 007 so we exercise the full
load path — automaton construction, translation lookup, cache reset.
No Mayura calls: the tests verify substitute → placeholders → restore
without leaving the pure-Python layer.
"""

from __future__ import annotations

import pytest

from app.translate import idioms


@pytest.fixture(autouse=True)
def _reset_cache_between_tests():
    idioms.reset_cache()
    yield
    idioms.reset_cache()


# ---------------------------------------------------------------------------
# Basic substitution
# ---------------------------------------------------------------------------


def test_substitute_finds_idiom_and_swaps_placeholder():
    text = "You must act in good faith."
    subbed, subs = idioms.substitute(text, target_language="hi")

    assert len(subs) == 1
    assert subs[0].source_phrase.lower() == "in good faith"
    assert subs[0].target_translation == "अच्छी नीयत से"
    assert subs[0].placeholder in subbed
    # The idiom is out; the surrounding English is intact.
    assert "in good faith" not in subbed
    assert subbed.startswith("You must act ")
    assert subbed.endswith(".")


def test_restore_swaps_placeholder_for_target():
    text = "Act in good faith today."
    subbed, subs = idioms.substitute(text, target_language="hi")

    # Simulate Mayura returning the text with placeholders preserved.
    translated_from_mayura = subbed.replace(
        "You must act", "आपको काम"
    )  # trivial rewrite for the test; placeholder stays
    restored = idioms.restore(translated_from_mayura, subs)

    assert "[[IDM_" not in restored
    assert "अच्छी नीयत से" in restored


def test_restore_accepts_mayura_single_bracket_placeholder():
    """Mayura can reduce [[IDM_1]] to [IDM_1] during translation."""
    _, subs = idioms.substitute("Act in good faith today.", target_language="hi")

    restored = idioms.restore("आपको [IDM_1] काम करना है।", subs)

    assert "[IDM_1]" not in restored
    assert "अच्छी नीयत से" in restored


@pytest.mark.parametrize(
    ("language", "expected_translation"),
    [
        ("hi", "देखा जाए तो"),
        ("bn", "সব মিলিয়ে দেখলে"),
        ("ta", "இறுதியில் பார்த்தால்"),
    ],
)
def test_restore_single_bracket_marker_in_supported_indic_languages(
    language: str, expected_translation: str,
):
    """The Mayura marker-normalisation fix works across all supported scripts."""
    subbed, subs = idioms.substitute(
        "Payment reconciliation happens at the end of the day.",
        target_language=language,
    )
    assert len(subs) == 1

    mayura_style_output = subbed.replace("[[IDM_1]]", "[IDM_1]")
    restored = idioms.restore(mayura_style_output, subs)

    assert "IDM_1" not in restored
    assert expected_translation in restored


# ---------------------------------------------------------------------------
# Case-insensitive matching
# ---------------------------------------------------------------------------


def test_matches_case_insensitively():
    text = "In Good Faith, we will proceed."
    _, subs = idioms.substitute(text, target_language="hi")

    assert len(subs) == 1
    # The captured source_phrase preserves the ORIGINAL casing so
    # future admin tooling can show the match verbatim.
    assert subs[0].source_phrase == "In Good Faith"


# ---------------------------------------------------------------------------
# Word boundary respected
# ---------------------------------------------------------------------------


def test_does_not_match_inside_longer_word():
    # "in good faith" as a substring of "unhindered" — clearly no idiom.
    # Use a synthetic tight case: 'faith' inside 'faithful'.
    text = "Act with faithfulness always."
    _, subs = idioms.substitute(text, target_language="hi")
    # 'faithful' is not an idiom, and 'in good faith' isn't in this text.
    assert len(subs) == 0


def test_matches_at_string_edges():
    # Boundary check must handle start-of-string and end-of-string.
    _, subs = idioms.substitute("in good faith", target_language="hi")
    assert len(subs) == 1


# ---------------------------------------------------------------------------
# Multiple hits + overlap resolution
# ---------------------------------------------------------------------------


def test_multiple_idioms_in_same_text():
    text = "Act in good faith and put in writing what you agree to."
    subbed, subs = idioms.substitute(text, target_language="hi")

    assert len(subs) == 2
    phrases = {s.source_phrase.lower() for s in subs}
    assert phrases == {"in good faith", "put in writing"}
    # Each got a unique placeholder.
    placeholders = {s.placeholder for s in subs}
    assert len(placeholders) == 2


# ---------------------------------------------------------------------------
# Target language routing
# ---------------------------------------------------------------------------


def test_uses_the_requested_target_language():
    text = "This applies at your own risk."
    _, hi_subs = idioms.substitute(text, target_language="hi")
    _, bn_subs = idioms.substitute(text, target_language="bn")

    assert hi_subs[0].target_translation == "अपनी ज़िम्मेदारी पर"
    assert bn_subs[0].target_translation == "নিজের ঝুঁকিতে"


def test_english_target_is_noop():
    text = "Act in good faith."
    subbed, subs = idioms.substitute(text, target_language="en")
    assert subbed == text
    assert subs == []


# ---------------------------------------------------------------------------
# Missing translation for target language
# ---------------------------------------------------------------------------


def test_missing_target_translation_passes_through():
    # Telugu 'te' is in our language whitelist but the seed doesn't
    # include Telugu translations, so any idiom detected for target=te
    # should fall through untranslated. This is the graceful degrade
    # path for languages the admin hasn't populated yet.
    text = "Act in good faith."
    subbed, subs = idioms.substitute(text, target_language="te")
    assert subbed == text
    assert subs == []


# ---------------------------------------------------------------------------
# Restore edge cases
# ---------------------------------------------------------------------------


def test_restore_handles_missing_placeholder_gracefully():
    # Simulate Mayura dropping one of the two placeholders.
    text = "Act in good faith and put in writing."
    subbed, subs = idioms.substitute(text, target_language="hi")
    assert len(subs) == 2

    # Strip one placeholder from the "translated" text — as if Mayura lost it.
    mangled = subbed.replace(subs[0].placeholder, "")
    restored = idioms.restore(mangled, subs)

    # The surviving placeholder should still be translated; the dropped
    # one is just gone — no crash, no leaked "[[IDM_" token.
    assert subs[1].target_translation in restored
    assert "[[IDM_" not in restored


def test_restore_strips_stray_placeholder_tokens():
    # Even if the automaton finds no idioms, any leaked [[IDM_n]] in
    # the translated text should be cleaned rather than left visible.
    stray = "Some text with [[IDM_42]] in the middle."
    restored = idioms.restore(stray, [])
    assert "[[IDM_" not in restored


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def test_reset_cache_forces_reload():
    # Prime cache
    idioms.substitute("act in good faith", target_language="hi")
    # Grab the current library instance
    from app.translate import idioms as idm
    cached = idm._cache
    assert cached is not None

    idioms.reset_cache()
    assert idm._cache is None

    # Next call rebuilds — different instance, same detection behavior.
    _, subs = idioms.substitute("act in good faith", target_language="hi")
    assert len(subs) == 1
    assert idm._cache is not None and idm._cache is not cached
