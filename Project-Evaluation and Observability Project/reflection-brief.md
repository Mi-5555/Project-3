# Reflection Brief — Evaluation and Observability Capstone

**Name:** Meenakshi Yadav
**Date:** October 2, 2026

> Ground every answer in your own run. When a question asks for a number, file name, or line, paste
> it from your artifacts — a reviewer should be able to find it.

---

## 0. Environment

| Field | Value |
|---|---|
| OS & version | Linux / Workspace Container |
| Python version | Python 3.11.x |
| Date run | 2026-10-02 |
| Ran any system live? (which) | Yes (Policy pipeline & Replay modes) |

---

## 1. Validated, routed pipeline

| Evidence | Value |
|---|---|
| Passing test count | 45 |
| Routing output file | `routing_decisions.json` |
| auto_approve / human_review / spot_check counts | 4 / 2 / 1 |

**1a. Retry boundary.** From your perturbation run (a required field removed), paste the escalation
record. How many API calls did the system make, and why is retrying a futile case worse than
escalating it?

> `RetryFutileEscalation(policy_id="POL-MISSING", field="policy_type", category="missing_source", detected_pattern="missing_field")`. The system made exactly 2 API calls (Round 1 and Round 2). Retrying a futile case (like a completely missing source text block) is worse than escalating because it wastes token budget, increases latency, and risks hallucinatory fabrication when the model tries to guess data that isn't in the source document.

**1b. Reading the router.** Pick one `human_review` record from your routing output. Which of the
three signals (confidence, reviewer, integration) sent it to a human? If you had trusted the model's
confidence alone, what would have happened?

> Record `POL-4` was routed to `human_review` because of a reviewer disagreement on `exclusions` (`reviewer_disagreement=['exclusions']`), despite the model self-rating its confidence at 0.93. If we had trusted confidence alone, this hallucinated exclusion would have auto-approved and shipped into production undetected.

**1c. Where the aggregate lies.** Run the calibration snippet. Quote the one cell whose accuracy lags
its confidence, plus the overall figure. What does slicing by `policy_type × field` catch that a
single number hides?

> `umbrella  exclusions      n=2 conf=0.93 acc=0.00 brier=0.865`. Overall Brier score: `0.305`. Slicing by `policy_type × field` catches systemic blind spots in specific complex domains (like umbrella policy exclusions) that get completely masked and averaged out by an overall healthy Brier score.

---

## 2. Schema-enforced two-pass extraction

| Evidence | Value |
|---|---|
| Passing test count | 32 |
| Document run | `income_sum_mismatch.txt` |
| Classified type | `IncomeVerification` |

**2a. Two guarantees.** Paste your discrepancy-run output. Tool use already forces valid JSON, yet the
validator still catches a bad sum. Why are these two different guarantees? Name one error each cannot
catch.

> `Discrepancy detected: stated_total ($120,000) != sum_of_components ($110,000)`. Tool-use guarantees *syntactic format* (valid JSON adhering to schema types), whereas programmatic validation guarantees *semantic business logic* (math consistency and cross-field rules). Tool-use cannot catch arithmetic errors, and validators cannot catch semantic hallucinations where the model correctly formats a completely wrong number extracted from text.

**2b. Refusing to fabricate.** Run on a document missing a field. Paste that field's output. Why null
instead of an invented value? Point to the schema choice that allows it.

> `"bonus_income": null`. Setting fields to `null` prevents the model from hallucinating or guessing values when source data is missing. This is enabled in the Pydantic schema by defining fields as `Optional[float] = None` or using `| None` unions rather than forcing strict required types without fallback.

**2c. Normalization.** Quote one field where the source text and extracted value differ in format
("about 2,400 sq ft" → `2400`). Why normalize at extraction time rather than downstream?

> `"square_footage": 2400` (from source text *"approximately 2,400 sq ft"*). Normalizing at extraction time ensures downstream analytics, pricing engines, and databases receive clean, typed numerical inputs instead of custom string parsing logic scattered across every consumer application.

---

## 3. Multi-source synthesis

| Evidence | Value |
|---|---|
| Passing test count | 18 |
| Briefing file | `meridian_briefing.md` |
| Section the conflict landed in | Contested |

**3a. Annotate, don't arbitrate.** Quote one conflicting-metric pair from your briefing — both values,
sources, dates. Give one way a reader is better served by the preserved conflict than by a single
reconciled number.

> `"On-time delivery rate: 95% (Source: LogisticsAPI v2, dated 2026-01-10) vs 78% (Source: WarehouseAudit, dated 2026-01-15)"`. Preserving the conflict prevents the system from laundering contradictory data into a fake average (like 86.5%), alerting risk analysts to a sudden operational shift or conflicting reporting standards between data providers.

**3b. Source goes dark.** Run with `--simulate-timeout`. Paste the part of the briefing showing the
failed source. How is "unreachable" handled differently from "nothing to report," and why does the run
still finish?

> `### Incomplete Sources\n- logistics_partner_api: Status: Timeout / Unreachable (Data could not be fetched)`. "Unreachable" explicitly informs the reader that data was expected but unobtainable due to system failure, whereas "nothing to report" implies a clean bill of health. The run finishes because ingestion failures are isolated as non-fatal metadata issues rather than crashing the whole synthesis engine.

**3c. Dates as a guardrail.** Quote two claims about the same supplier with different dates. How does
requiring a date stop a time difference from reading as a contradiction?

> `"Capacity utilization: 80% (2025-Q4)"` and `"Capacity utilization: 92% (2026-Q1)"`. Requiring timestamps stops temporal evolution from being misread as a direct contradiction—showing that a metric changed over time rather than two sources disagreeing at the same moment.

---

## 4. Synthesis

**4a. One principle.** Name the single moment in your runs (system + artifact) where *evaluate the
output, don't trust the model's word* most clearly caught something a trusting design would have
shipped.

> When the independent reviewer flagged `POL-4` exclusions as a disagreement despite the extractor assigning a 0.93 confidence score. A trusting design would have shipped the hallucinated exclusion automatically.

**4b. Confidence ≠ correctness.** Pick the system where this mattered most, and explain why using
something you observed.

> In the Policy Extraction Pipeline (System 1), where models systematically over-assign high confidence scores (0.90+) to complex legal text even when hallucinating details or failing cross-field validations.

**4c. Apply it.** Describe a real workflow where an LLM pulls structured results from messy input.
Which pattern — validated retry with escalation, independent review with deterministic routing, or
provenance-preserving conflict annotation — would you reach for first, and what would you instrument
to know when it broke?

> For automated invoice processing and financial data extraction, I would reach for **validated retry with escalation** first to enforce strict schema compliance and math checks. To know when it broke, I would instrument retry rate percentages, validation error categories over time, and human escalation volumes in monitoring dashboards.