# Perturbation Log

For each system, make one deliberate change to an input or configuration, predict the outcome, run
it, and record what actually happened.

---

### System 1 — validated, routed pipeline

- **Change I made (file + what I changed):** In `policy_extractor/extractor.py`, forced a required field (`policy_type`) to return empty/null during extraction.
- **Command I ran:** `.venv/bin/pytest tests/test_01_retry.py -v`
- **What I predicted:** The pipeline would detect a `missing_source` validation failure, execute the single allowed retry round, and ultimately trigger a `RetryFutileEscalation`.
- **What actually happened (paste the key output line):** `FAILED tests/test_01_retry.py::test_missing_required_field_escalates - AssertionError: Expected RetryFutileEscalation but got PolicyExtraction` (prior to implementation, which then correctly resolved to passing escalation after the error feedback loop was built).
- **How this differs from the unperturbed run:** An unperturbed valid document satisfies schema constraints on the first pass and results in a clean `PolicyExtraction` record with zero retries.

---

### System 2 — schema-enforced two-pass extraction

- **Change I made (file + what I changed):** Compared `income_sum_mismatch.txt` where the component line items do not sum up to the stated total income against a clean income statement.
- **Command I ran:** `.venv/bin/mortgage-extract fixtures/documents/income_sum_mismatch.txt --mode replay`
- **What I predicted:** The JSON output would successfully form via tool use, but the programmatic validator would catch the math inconsistency and flag it.
- **What actually happened (paste the key output line):** `ValueError: Integration check failed: sum of income components does not match total stated income.`
- **How this differs from the unperturbed run:** Clean documents like `appraisal_informal_sqft.txt` pass validation cleanly after normalization, whereas consistency mismatches halt processing or route to human review.

---

### System 3 — multi-source synthesis

- **Change I made (file + what I changed):** Ran the supply-chain investigation simulation while forcing a service timeout using the `--simulate-timeout` flag.
- **Command I ran:** `.venv/bin/supply-chain-investigate meridian --offline --simulate-timeout`
- **What I predicted:** The pipeline would crash due to the missing source payload.
- **What actually happened (paste the key output line):** `[WARNING] Source 'logistics_partner_api' timed out. Categorized under 'Incomplete'. Synthesis completed successfully.`
- **How this differs from the unperturbed run:** A standard run (`--offline`) synthesizes all sources into Well-Established, Contested, and Incomplete sections, whereas the timeout run cleanly segregates the dark source into Incomplete without terminating the broader report.