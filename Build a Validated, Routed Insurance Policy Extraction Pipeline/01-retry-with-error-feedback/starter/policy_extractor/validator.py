"""Validates extracted policy records and categorises failures.

The validator only handles semantic and consistency errors. JSON-syntax errors
are eliminated upstream by tool_choice-forced structured tool calls — the SDK
enforces the schema before this validator runs.
"""
from __future__ import annotations

from typing import Any

from policy_extractor.records import ValidationError


def validate_extraction(extraction: dict[str, Any]) -> ValidationError | None:
    """Return the first ValidationError found, or None if extraction is clean."""
    if (err := _check_required_present(extraction)) is not None:
        return err
    if (err := _check_numeric_ranges(extraction)) is not None:
        return err
    if (err := _check_premium_components_consistency(extraction)) is not None:
        return err
    return None


_REQUIRED_FIELDS = ("premium_amount", "deductible", "coverage_limit", "endorsements", "exclusions")


def _check_required_present(extraction: dict[str, Any]) -> ValidationError | None:
    """Return missing_source ValidationError for the first null required field, else None."""
    for field in _REQUIRED_FIELDS:
        if extraction.get(field) is None:
            return ValidationError(
                field=field,
                category="missing_source",
                detected_pattern=f"{field}_absent",
                observed_value=None,
                message=f"Required field '{field}' is absent from the source document.",
            )
    return None


def _check_numeric_ranges(extraction: dict[str, Any]) -> ValidationError | None:
    """Return format ValidationError for any negative numeric field, else None."""
    numeric_checks = [
        ("premium_amount", "negative_premium"),
        ("deductible", "negative_deductible"),
        ("coverage_limit", "negative_coverage_limit"),
    ]
    for field, pattern in numeric_checks:
        val = extraction.get(field)
        if val is not None and isinstance(val, (int, float)) and val < 0:
            return ValidationError(
                field=field,
                category="format",
                detected_pattern=pattern,
                observed_value=val,
                message=f"Field '{field}' has negative value {val}, which is invalid.",
            )
    return None


def _check_premium_components_consistency(
    extraction: dict[str, Any],
) -> ValidationError | None:
    """Return consistency ValidationError when stated premium ≠ sum(components), else None."""
    components = extraction.get("premium_components")
    premium_amount = extraction.get("premium_amount")

    if components and isinstance(components, list) and isinstance(premium_amount, (int, float)):
        total_components = sum(c.get("amount", 0) for c in components if isinstance(c, dict) and "amount" in c)
        delta = round(total_components - premium_amount, 2)
        if abs(delta) > 0.01:
            return ValidationError(
                field="premium_amount",
                category="consistency",
                detected_pattern="premium_does_not_match_components",
                observed_value=premium_amount,
                message=f"Stated premium amount ({premium_amount}) does not match sum of components ({total_components}).",
            )
    return None