"""Compliance Analyst worker — (PolicyStatement, list[RegulationChunk]) -> Finding."""

from pydantic import BaseModel, Field

from complyagent.agents.llm_client import get_chat_model
from complyagent.prompts.analyst import ANALYST_PROMPT
from complyagent.schemas.enums import VerdictType
from complyagent.schemas.findings import Finding
from complyagent.schemas.policy import PolicyStatement
from complyagent.schemas.regulation import RegulationChunk
from complyagent.agents._retry import with_llm_retry


# LLM-facing schema: no statement_id (Python sets it from the input statement,
# since the LLM has no business inventing or re-stating it).
class _AnalystOutput(BaseModel):
    verdict: VerdictType
    rationale: str = Field(..., min_length=10)
    citations: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)


# Fixed Finding returned when called with no retrieved chunks. Semantically
# correct: without evidence, no judgment is possible.
_EMPTY_CHUNKS_RATIONALE = "No relevant GDPR provisions were retrieved for evaluation."


def _format_chunks(chunks: list[RegulationChunk]) -> str:
    """Render chunks as readable bullet list for the prompt."""
    return "\n".join(
        f"  - {chunk.chunk_id}: {chunk.text}" for chunk in chunks
    )


def analyze_statement(
    statement: PolicyStatement,
    retrieved_chunks: list[RegulationChunk],
) -> Finding:
    """Produce a compliance verdict for one policy statement against retrieved GDPR chunks."""

    # Short-circuit: degenerate input, no LLM call.
    if not retrieved_chunks:
        return Finding(
            statement_id=statement.statement_id,
            verdict=VerdictType.UNCLEAR,
            rationale=_EMPTY_CHUNKS_RATIONALE,
            citations=[],
            confidence=0.0,
        )

    model = get_chat_model()
    structured = model.with_structured_output(_AnalystOutput)
    chain = with_llm_retry(ANALYST_PROMPT | structured)

    result: _AnalystOutput = chain.invoke({
        "statement_id": statement.statement_id,
        "statement_text": statement.text,
        "category": statement.category.value,
        "retrieved_chunks": _format_chunks(retrieved_chunks),
    })

    # Subset enforcement: drop any cited chunk_id the LLM invented or typo'd.
    # We silently filter rather than raise — better to keep the verdict with
    # valid citations than fail the whole audit pipeline over a citation typo.
    valid_chunk_ids = {chunk.chunk_id for chunk in retrieved_chunks}
    filtered_citations = [cid for cid in result.citations if cid in valid_chunk_ids]

    return Finding(
        statement_id=statement.statement_id,
        verdict=result.verdict,
        rationale=result.rationale,
        citations=filtered_citations,
        confidence=result.confidence,
    )