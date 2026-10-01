"""Two-pass extraction pipeline: classify, then extract.

The classification pass uses ``tool_choice={"type":"tool","name":...}`` — the
model is forced to call the classifier and cannot return free text. The
extraction pass uses ``tool_choice={"type":"any"}`` against a small set of
doc-type-specific tools (a primary extractor plus a ``flag_for_review`` escape
hatch). ``"any"`` rather than ``"auto"`` because ``"auto"`` would permit a
conversational text fallback; ``"any"`` guarantees a ``tool_use`` block.

This pattern mirrors the Architect's Playbook "broad-then-pinpoint" exploration
recipe: classify the document first, then drill into the doc-type-specific
extractor with a fallback for unrecoverable cases.
"""
from __future__ import annotations
from mortgage_extractor.config import DEFAULT_MODEL, DEFAULT_MAX_TOKENS

from typing import Any
from mortgage_extractor.client import RecordingClient
from mortgage_extractor.errors import (
    ExtractionError,
    FlaggedForReviewError,
    UnsupportedDocumentTypeError,
)
from mortgage_extractor.models import Classification, DocumentType, MortgageExtraction
from mortgage_extractor import prompts, tools


def _single_tool_use_block(response: Any, expected_name: str | None = None) -> Any:
    """Extract the single tool use content block from an Anthropic response.

    Raises ExtractionError if the response has no tool use blocks, multiple
    tool use blocks, or (when expected_name is given) a block whose name
    doesn't match expected_name.
    """
    tool_blocks = [block for block in response.content if block.type == "tool_use"]
    if not tool_blocks:
        raise ExtractionError("Response contained no tool use blocks")
    if len(tool_blocks) > 1:
        raise ExtractionError(f"Expected 1 tool use block, got {len(tool_blocks)}")
    block = tool_blocks[0]
    if expected_name and block.name != expected_name:
        raise ExtractionError(f"Expected tool '{expected_name}', got '{block.name}'")
    return block


class Pipeline:
    """Orchestrates the two-pass classify-then-extract mortgage pipeline."""
    from mortgage_extractor.config import DEFAULT_MODEL, DEFAULT_MAX_TOKENS

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        client: RecordingClient | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self.model = model
        self.client = client or RecordingClient()
        self.max_tokens = max_tokens

    def run(self, document_text: str) -> MortgageExtraction:
        """Classify, then extract. Short-circuit on DocumentType.OTHER."""
        classification = self.classify_document(document_text)
        if classification.document_type == DocumentType.OTHER:
            raise UnsupportedDocumentTypeError(classification.reason)
        return self.extract(document_text, classification.document_type)

    def classify_document(self, document_text: str) -> Classification:
        """Pass 1: forced classifier call.

        Force the model to call the classifier tool exactly once via
        ``tool_choice={"type": "tool", "name": <classifier name>}``. This pass
        must produce a routing decision, not free text.
        """
        classifier_tool = tools.classify_document()
        response = self.client.call(
            model=self.model,
            max_tokens=self.max_tokens,
            system=prompts.classifier_system_prompt(),
            tools=[classifier_tool],
            tool_choice={"type": "tool", "name": classifier_tool["name"]},
            messages=[{"role": "user", "content": document_text}],
        )
        block = _single_tool_use_block(response, expected_name=classifier_tool["name"])
        return Classification.model_validate(block.input)

    def extract(
        self,
        document_text: str,
        doc_type: DocumentType,
    ) -> MortgageExtraction:
        """Pass 2: tool_choice="any" extraction.

        Register the doc-type-specific extractor alongside ``flag_for_review``
        and let the model choose. ``"any"`` is what makes that choice
        meaningful — with a single tool registered, the API would behave the
        same as forced.
        """
        if doc_type == DocumentType.OTHER:
            raise UnsupportedDocumentTypeError(
                "extract() should not be called for DocumentType.OTHER (short-circuits at classify time)"
            )

        extractor_tool = tools.doc_type_extractor(doc_type)
        review_tool = tools.flag_for_review()
        tools_list = [extractor_tool, review_tool]

        response = self.client.call(
            model=self.model,
            max_tokens=self.max_tokens,
            system=prompts.extractor_system_prompt(doc_type),
            tools=tools_list,
            tool_choice={"type": "any"},
            messages=[{"role": "user", "content": document_text}],
        )

        block = _single_tool_use_block(response)

        if block.name == review_tool["name"]:
            raise FlaggedForReviewError(block.input.get("reason", "Flagged for manual review"))
        elif block.name == extractor_tool["name"]:
            return MortgageExtraction.model_validate(block.input)
        else:
            raise ExtractionError(f"Unexpected tool called: {block.name}")