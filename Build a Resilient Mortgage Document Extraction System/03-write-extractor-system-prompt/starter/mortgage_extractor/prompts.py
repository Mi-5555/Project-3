"""System prompts, normalization rules, and few-shot examples.

The prompts in this module teach the extractor *how* to handle the cases the
schema alone cannot enforce: when to return null instead of fabricating, how to
normalize informal numerics, and how to record arithmetic discrepancies
verbatim rather than silently correcting them.

The single source of truth for normalization is :data:`NORMALIZATION_RULES`,
which is interpolated into every extractor system prompt and is the canonical
reference for the rules described in the module docstrings of
:mod:`mortgage_extractor.schema` and :mod:`mortgage_extractor.models`.
"""
from __future__ import annotations

from mortgage_extractor.models import DocumentType

NORMALIZATION_RULES = (
    "Normalization rules:\n"
    "- Square footage: extract numeric integer value (e.g. \"about 2,400 sq ft\" -> 2400).\n"
    "- Currency: extract standard decimal or float amount (e.g. \"$485,000\" -> 485000.0).\n"
    "- Percentage: extract decimal fraction representation (e.g. \"6.5%\" -> 0.065)."
)

_CATEGORICAL_CRITERIA = (
    "1. Return null for any field not explicitly stated in the document. Do not infer, default, or fabricate.\n"
    "2. Distinguish base monthly income clearly from bonus, commission, and overtime earnings.\n"
    "3. For categorical fields where no standard option fits, emit 'other' and populate the corresponding _detail field with verbatim text.\n"
    "4. Ensure all numeric fields receive proper numeric types rather than strings."
)

_FEW_SHOT_EXAMPLES = """<example name="clean">
<input>
Paystub: Jordan Chen. Base monthly: $8,500.00. Bonus YTD: $12,000.00. Overtime YTD: $0.00.
</input>
<reasoning>
Every component is explicitly stated in the document, so all values are extracted verbatim with appropriate types.
</reasoning>
<output>
{"borrower": {"full_name": "Jordan Chen"}, "income": {"base_monthly": 8500.0, "bonus_ytd": 12000.0, "overtime_ytd": 0.0}}
</output>
</example>
<example name="missing">
<input>
Paystub: Morgan Smith. Base monthly: $6,200.00. No bonus or overtime mentioned this period.
</input>
<reasoning>
bonus_ytd is null because the document says nothing about bonuses—fabricating a zero would imply zero earned, not zero reported.
</reasoning>
<output>
{"borrower": {"full_name": "Morgan Smith"}, "income": {"base_monthly": 6200.0, "bonus_ytd": null, "overtime_ytd": null}}
</output>
</example>
<example name="informal">
<input>
Appraisal: Property located at 4218 Magnolia St. Living area is about 2,400 sq ft.
</input>
<reasoning>
Informal text like 'about 2,400 sq ft' is normalized to an integer 2400 per the normalization rules.
</reasoning>
<output>
{"property": {"address": "4218 Magnolia St", "living_area_sqft": 2400}}
</output>
</example>
<example name="mismatch">
<input>
Income Verification: Taylor Reed. Base monthly: $5,000. Line items sum differently than stated gross total, but we record verbatim.
</input>
<reasoning>
Discrepancies or arithmetic inconsistencies in the source document are recorded verbatim rather than silently correcting them.
</reasoning>
<output>
{"borrower": {"full_name": "Taylor Reed"}, "income": {"base_monthly": 5000.0}}
</output>
</example>"""


def classifier_system_prompt() -> str:
    """System prompt for the classifier pass."""
    return (
        "You are a document classifier for a mortgage lender. You will receive "
        "the text of a single mortgage-related document and must call the "
        "`classify_document` tool exactly once with the document's type and a "
        "one-sentence reason describing the textual cues that drove the "
        "classification. Use `other` if the document is not one of the listed "
        "types or is too damaged to classify confidently."
    )


def extractor_system_prompt(doc_type: DocumentType) -> str:
    """Return the system prompt for the given document type's extractor."""
    if doc_type == DocumentType.INCOME_VERIFICATION:
        return income_verification_system_prompt()

    intro = (
        f"You are the senior {doc_type.value} data extractor. "
        f"Call extract_{doc_type.value} exactly once with the extracted structured data, "
        "or use `flag_for_review` if the document is unreadable or ambiguous."
    )
    return f"{intro}\n\n{NORMALIZATION_RULES}\n\n{_FEW_SHOT_EXAMPLES}"


def income_verification_system_prompt() -> str:
    """Return the income-verification extractor system prompt."""
    intro = (
        "You are the senior income verification data extractor. "
        "Call extract_income_verification exactly once with the structured data, "
        "or flag_for_review if the document is unreadable."
    )
    return f"{intro}\n\n{_CATEGORICAL_CRITERIA}\n\n{NORMALIZATION_RULES}\n\n{_FEW_SHOT_EXAMPLES}"