"""Regulation Researcher worker — PolicyStatement -> list[RegulationChunk].

Unlike the other workers, this one uses bound tools: the LLM autonomously
formulates a search query and invokes retrieve() via a tool call, rather than
us extracting a query string and calling retrieve() deterministically.

Built on LangChain's create_agent (langchain 1.0+), the canonical built-in
for tool-calling agents. The agent loop is capped at one tool call.
"""

from langchain.agents import create_agent
from langchain_core.tools import tool

from complyagent.agents.llm_client import get_chat_model
from complyagent.prompts.researcher import SYSTEM_PROMPT
from complyagent.retrieval.retrieve import retrieve as _retrieve_fn
from complyagent.schemas.policy import PolicyStatement
from complyagent.schemas.regulation import RegulationChunk
from complyagent.agents._retry import with_llm_retry


# Module-level state: the most recent retrieve() result. The agent's final
# message is natural language ("here are the chunks..."), not the chunk objects
# themselves — we need to capture the actual list[RegulationChunk] when the
# tool runs. A module-level capture is the simplest extraction pattern that
# doesn't require parsing the agent's message history.
_last_retrieve_result: list[RegulationChunk] = []


@tool
def retrieve_gdpr_chunks(query: str) -> str:
    """Search the GDPR corpus for the most relevant provisions.

    Args:
        query: A search query using GDPR-native legal terminology.

    Returns:
        A summary of retrieved chunks (the actual chunk objects are captured separately).
    """
    global _last_retrieve_result
    chunks = _retrieve_fn(query)
    _last_retrieve_result = chunks

    # The LLM gets a readable summary; the structured objects are captured above.
    if not chunks:
        return "No relevant GDPR provisions found."
    return "\n".join(
        f"- {c.chunk_id}: {c.text[:200]}..." if len(c.text) > 200 else f"- {c.chunk_id}: {c.text}"
        for c in chunks
    )


def research_statement(statement: PolicyStatement) -> list[RegulationChunk]:
    """Retrieve GDPR provisions relevant to one policy statement.

    The LLM formulates a search query (translating company-speak into GDPR-native
    legal terminology) and invokes retrieve() exactly once. If the LLM fails to
    call the tool, we defensively fall back to retrieve(statement.text) so the
    downstream pipeline always receives non-empty chunks.
    """
    global _last_retrieve_result
    _last_retrieve_result = []  # Reset before each call.

    model = get_chat_model()

    # create_agent returns a compiled LangGraph runnable. Passing tools=[...]
    # binds them; the agent loop will call them as the LLM decides.
    agent = with_llm_retry(create_agent(
        model=model,
        tools=[retrieve_gdpr_chunks],
        system_prompt=SYSTEM_PROMPT,
    ))

    user_message = (
        "Find the GDPR provisions most relevant to this policy statement.\n\n"
        f"STATEMENT:\n"
        f"  text: {statement.text}\n"
        f"  category: {statement.category.value}"
    )

    # recursion_limit caps the total agent steps (LLM call + tool call counts
    # as ~2 steps). Setting it tight enforces the "one tool call" rule at the
    # framework level, in addition to the prompt-level instruction.
    agent.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config={"recursion_limit": 5},
    )

    # Defensive fallback: if the LLM didn't call retrieve() at all (e.g. decided
    # it could answer without it, hit a content filter, etc.), fall back to a
    # deterministic retrieve(statement.text). Guarantees the contract holds.
    if not _last_retrieve_result:
        return _retrieve_fn(statement.text)

    return _last_retrieve_result