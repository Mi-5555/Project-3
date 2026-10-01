"""HITL routing with stratified sampling and confidence calibration.

The routing layer is deliberately deterministic: the decision for each extraction is
a pure function of (extractor confidence, reviewer agreement, integration findings).
The model's self-rated confidence is one of three inputs, not the sole gate.
"""
from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from policy_extractor.records import PolicyExtraction
from policy_extractor.reviewer import IntegrationFinding, ReviewResult

DEFAULT_CONFIDENCE_THRESHOLD = 0.90

Decision = Literal["auto_approve", "human_review", "spot_check"]


@dataclass
class RoutingDecision:
    policy_id: str
    policy_type: str
    decision: Decision
    reason: str
    fields_below_threshold: list[str]
    reviewer_disagreements: list[str]
    integration_failures: list[str]
    confidence_summary: dict[str, float]


def route_extraction(
    *,
    extraction: PolicyExtraction,
    review: ReviewResult,
    integration_findings: Sequence[IntegrationFinding],
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> RoutingDecision:
    """Classify a single extraction as auto_approve or human_review."""
    # 1. Fields below confidence threshold
    fields_below = sorted(
        [
            field_name
            for field_name, conf in extraction.confidence.items()
            if conf < threshold
        ]
    )

    # 2. Reviewer disagreements
    disagreements = sorted(
        [
            field_name
            for field_name, agreement in review.agreements.items()
            if agreement.agreement == "disagree"
        ]
    )

    # 3. Integration failures
    integration_failures = sorted(
        [
            finding.check_name
            for finding in integration_findings
            if finding.status == "fail"
        ]
    )

    confidence_summary = dict(extraction.confidence)

    # Decision rule: any trigger requires human review
    if fields_below or disagreements or integration_failures:
        decision: Decision = "human_review"
        reasons = []
        if fields_below:
            reasons.append(f"fields_below_threshold={fields_below}")
        if disagreements:
            reasons.append(f"reviewer_disagreement={disagreements}")
        if integration_failures:
            reasons.append(f"integration_failure={integration_failures}")
        reason = "; ".join(reasons)
    else:
        decision = "auto_approve"
        reason = "all confidence at/above threshold, reviewer agrees, integration clean"

    return RoutingDecision(
        policy_id=extraction.policy_id,
        policy_type=extraction.policy_type,
        decision=decision,
        reason=reason,
        fields_below_threshold=fields_below,
        reviewer_disagreements=disagreements,
        integration_failures=integration_failures,
        confidence_summary=confidence_summary,
    )


def apply_stratified_spot_check(
    decisions: Sequence[RoutingDecision],
    *,
    sample_pct: float,
    seed: int | None = None,
) -> list[RoutingDecision]:
    """Promote a stratified sample of auto_approve decisions to spot_check."""
    rng = random.Random(seed)
    
    # Bucket auto_approve decisions by policy_type with their indices
    strata: dict[str, list[int]] = defaultdict(list)
    for idx, d in enumerate(decisions):
        if d.decision == "auto_approve":
            strata[d.policy_type].append(idx)

    promoted_indices: set[int] = set()
    for policy_type, indices in strata.items():
        n = len(indices)
        k = max(1, math.ceil(sample_pct * n))
        k = min(k, n)
        promoted_indices.update(rng.sample(indices, k))

    # Rebuild output list
    output: list[RoutingDecision] = []
    for idx, d in enumerate(decisions):
        if idx in promoted_indices:
            output.append(
                RoutingDecision(
                    policy_id=d.policy_id,
                    policy_type=d.policy_type,
                    decision="spot_check",
                    reason="stratified drift-detection sample",
                    fields_below_threshold=d.fields_below_threshold,
                    reviewer_disagreements=d.reviewer_disagreements,
                    integration_failures=d.integration_failures,
                    confidence_summary=d.confidence_summary,
                )
            )
        else:
            output.append(d)

    return output


def write_routing_decisions(
    decisions: Iterable[RoutingDecision],
    path: Path,
) -> None:
    """Write routing decisions to a single JSON file."""
    payload = [asdict(d) for d in decisions]
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


# ---------- Calibration ----------


@dataclass(frozen=True)
class CalibrationLabel:
    policy_id: str
    policy_type: str
    field: str
    predicted_confidence: float
    correct: bool


@dataclass
class CalibrationCell:
    policy_type: str
    field: str
    samples: int
    mean_predicted_confidence: float
    observed_accuracy: float
    brier_score: float


@dataclass
class CalibrationReport:
    cells: dict[tuple[str, str], CalibrationCell] = field(default_factory=dict)
    overall_brier: float = 0.0


def calibration_report(labels: Sequence[CalibrationLabel]) -> CalibrationReport:
    """Produce a (policy_type x field) sliced reliability report."""
    if not labels:
        return CalibrationReport()

    buckets: dict[tuple[str, str], list[CalibrationLabel]] = defaultdict(list)
    for label in labels:
        buckets[(label.policy_type, label.field)].append(label)

    cells: dict[tuple[str, str], CalibrationCell] = {}
    for key, bucket in buckets.items():
        n = len(bucket)
        mean_conf = sum(b.predicted_confidence for b in bucket) / n
        obs_acc = sum(1 for b in bucket if b.correct) / n
        brier = sum(
            (b.predicted_confidence - (1.0 if b.correct else 0.0)) ** 2 for b in bucket
        ) / n
        cells[key] = CalibrationCell(
            policy_type=key[0],
            field=key[1],
            samples=n,
            mean_predicted_confidence=mean_conf,
            observed_accuracy=obs_acc,
            brier_score=brier,
        )

    overall_brier = sum(
        (b.predicted_confidence - (1.0 if b.correct else 0.0)) ** 2 for b in labels
    ) / len(labels)

    return CalibrationReport(cells=cells, overall_brier=overall_brier)