"""
Phase 3 smoke test: verify get_chat_model() + with_structured_output()
works end-to-end against the live Groq API (openai/gpt-oss-120b).

Run from repo root:
    uv run python scripts/smoke_test_llm.py
"""

from pydantic import BaseModel, Field
from complyagent.agents.llm_client import get_chat_model


class SmokeTestSchema(BaseModel):
    """Trivial schema, just to prove structured output round-trips."""
    answer: str = Field(description="A short answer to the question")
    confidence: float = Field(description="Confidence score between 0 and 1")


def main():
    print("Building chat model via get_chat_model()...")
    llm = get_chat_model()
    print(f"Model object: {llm}")

    print("\nBinding structured output schema...")
    structured_llm = llm.with_structured_output(SmokeTestSchema)

    print("\nInvoking with a trivial prompt...")
    result = structured_llm.invoke(
        "What is the capital of France? Answer briefly and give your confidence."
    )

    print("\n--- RESULT ---")
    print(f"Type: {type(result)}")
    print(f"Is SmokeTestSchema instance: {isinstance(result, SmokeTestSchema)}")
    print(result)

    assert isinstance(result, SmokeTestSchema), (
        "structured output did not return the expected Pydantic type "
        f"(got {type(result)} instead)"
    )
    assert result.answer, "answer field was empty"
    assert 0.0 <= result.confidence <= 1.0, f"confidence out of range: {result.confidence}"

    print("\n[PASS] get_chat_model() + with_structured_output() works end-to-end.")


if __name__ == "__main__":
    main()