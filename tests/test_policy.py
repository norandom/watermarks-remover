"""Tests for the transform policy value object (task 2.1, Requirement 9).

Includes the drift assertion task 1.1 deliberately deferred to this task:
``tests/conftest.py`` restates ``CleanPolicy``'s field vocabulary for the
harness's benefit, and that restatement must not be allowed to rot.
"""

from __future__ import annotations

import dataclasses

import pytest

from wm_hook.policy import CleanPolicy

from conftest import POLICY_FIELD_DEFAULTS


class TestDocumentedDefaults:
    """Requirement 9.3, 9.4 -- a safe, documented default set."""

    def test_defaults_match_the_field_vocabulary_the_harness_restates(self) -> None:
        """The drift assertion deferred from task 1.1.

        ``conftest.POLICY_FIELD_DEFAULTS`` is a hand-written restatement of
        design.md's Data Models table. If the real value object and that
        restatement disagree, every corpus annotation keyed on a policy flag is
        suspect, so the two must be compared mechanically.
        """
        actual = {f.name: getattr(CleanPolicy.default(), f.name)
                  for f in dataclasses.fields(CleanPolicy)}
        assert actual == dict(POLICY_FIELD_DEFAULTS)

    def test_field_names_cover_every_declared_flag(self) -> None:
        assert set(CleanPolicy.field_names()) == set(POLICY_FIELD_DEFAULTS)

    def test_default_is_equivalent_to_bare_construction(self) -> None:
        assert CleanPolicy.default() == CleanPolicy()

    @pytest.mark.parametrize(
        ("flag", "expected", "requirement"),
        [
            ("strip_private_use", False, "3.5"),
            ("strip_bom", False, "6.5"),
            ("normalize_spaces", True, "4.1"),
        ],
    )
    def test_the_three_requirement_driven_defaults(
        self, flag: str, expected: bool, requirement: str
    ) -> None:
        """These three are the defaults that differ from shipped behaviour.

        Named individually so a future change that flips one fails with the
        requirement number in the test id, not as an anonymous dict mismatch.
        """
        assert getattr(CleanPolicy.default(), flag) is expected, (
            f"default for {flag} is mandated by Requirement {requirement}"
        )


class TestImmutability:
    """A policy is decided once per run and read many times."""

    def test_assignment_is_refused(self) -> None:
        policy = CleanPolicy.default()
        with pytest.raises(dataclasses.FrozenInstanceError):
            policy.normalize_spaces = False  # type: ignore[misc]

    def test_overrides_return_a_new_object_and_leave_the_original_alone(self) -> None:
        original = CleanPolicy.default()
        derived = original.with_overrides(strip_private_use=True)
        assert derived.strip_private_use is True
        assert original.strip_private_use is False
        assert derived is not original

    def test_equal_policies_compare_equal_and_hash_alike(self) -> None:
        assert CleanPolicy.default() == CleanPolicy.default()
        assert hash(CleanPolicy.default()) == hash(CleanPolicy())


class TestOverrideValidation:
    """A typo in a hook argument must fail loudly (Requirement 9.1, 9.2)."""

    def test_unknown_flag_is_rejected_by_name(self) -> None:
        with pytest.raises(ValueError, match="unknown policy flag"):
            CleanPolicy.default().with_overrides(strip_privateuse=True)

    def test_the_rejection_names_the_offending_flag(self) -> None:
        with pytest.raises(ValueError, match="strip_privateuse"):
            CleanPolicy.default().with_overrides(strip_privateuse=True)

    def test_non_boolean_value_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="must be a bool"):
            CleanPolicy.default().with_overrides(normalize_spaces="yes")  # type: ignore[arg-type]

    def test_every_declared_flag_can_actually_be_overridden(self) -> None:
        """Guards against a flag being documented but not wired up."""
        for name in CleanPolicy.field_names():
            flipped = not getattr(CleanPolicy.default(), name)
            derived = CleanPolicy.default().with_overrides(**{name: flipped})
            assert getattr(derived, name) is flipped


class TestPolicyCannotOverrideCorrectness:
    """Requirement 4.1 -- correctness outranks configuration.

    The classifier, not this object, enforces that a space homoglyph at a
    structurally significant position is never replaced. These tests pin the
    *absence* of any flag that would purport to control it, so a later task
    cannot quietly add one and reopen the YAML-corruption defect.
    """

    def test_no_flag_claims_to_govern_structural_positions(self) -> None:
        suspicious = [
            name for name in CleanPolicy.field_names()
            if "structural" in name or "column" in name or "position" in name
        ]
        assert suspicious == []

    def test_the_flag_vocabulary_is_exactly_the_documented_seven(self) -> None:
        """A new flag is a design change and must go through the spec first."""
        assert len(CleanPolicy.field_names()) == 7
