"""Policy Parser worker — text -> list[PolicyStatement]."""

from pydantic import BaseModel, Field

from complyagent.agents.llm_client import get_chat_model
from complyagent.prompts.parser import PARSER_PROMPT
from complyagent.schemas.enums import StatementCategory
from complyagent.schemas.policy import PolicyStatement

# Minimum input length below which we skip the LLM entirely.
MIN_INPUT_CHARS = 5


# LLM-facing variant of PolicyStatement: no statement_id (Python assigns it).
# Defined here rather than in schemas/ because it's an internal Parser concern,
# not a domain type other workers should know about.
class _ParsedStatement(BaseModel):
    text: str = Field(..., min_length=1)
    category: StatementCategory
    source_span: str | None = None


# Wrapper schema — with_structured_output binds one schema, not a list.
class _PolicyStatementList(BaseModel):
    statements: list[_ParsedStatement]


def parse_policy(policy_text: str) -> list[PolicyStatement]:
    """Extract atomic policy statements from raw privacy-policy text.

    Returns [] for empty or near-empty input without calling the LLM.
    """
    if len(policy_text.strip()) < MIN_INPUT_CHARS:
        return []

    model = get_chat_model()
    structured = model.with_structured_output(_PolicyStatementList)
    chain = PARSER_PROMPT | structured

    result: _PolicyStatementList = chain.invoke({"policy_text": policy_text})

    # Assign stable IDs in document order. Done in Python (not LLM) for
    # determinism — same input always yields stmt-001, stmt-002, ...
    return [
        PolicyStatement(
            statement_id=f"stmt-{i:03d}",
            text=parsed.text,
            category=parsed.category,
            source_span=parsed.source_span,
        )
        for i, parsed in enumerate(result.statements, start=1)
    ]