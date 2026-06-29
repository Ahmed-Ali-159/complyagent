"""Shared retry configuration for LLM chains.

Workers apply .with_retry() to their composed chains (prompt | structured_llm)
to handle rate-limit (429) and transient errors with exponential backoff.

Applied at the chain level rather than at the model factory because
RunnableRetry doesn't forward attribute access like .with_structured_output()
or .bind() — wrapping the chain (which is already a plain Runnable) is the
clean LangChain idiom.
"""

from langchain_core.runnables import Runnable


def with_llm_retry(chain: Runnable) -> Runnable:
    """Wrap an LCEL chain with retry/backoff for rate-limit and transient errors.

    5 attempts ≈ ~30s of total wait budget with exponential jitter spreading
    retries so parallel fanned-out invocations don't synchronize their retries.
    """
    return chain.with_retry(
        stop_after_attempt=5,
        wait_exponential_jitter=True,
        retry_if_exception_type=(Exception,),
    )