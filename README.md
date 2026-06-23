# ComplyAgent

Multi-agent GDPR compliance auditor. Built with LangGraph (supervisor-worker topology), hybrid RAG over the EU GDPR, and Groq-hosted Llama 3.3.

## Status

🚧 Under construction. Currently: Phase 0 (setup).

## Quickstart

```powershell
uv sync
uv run python -c "from complyagent.config import settings; print(settings.llm.supervisor_model)"
```

## Architecture

A supervisor agent dynamically routes audit tasks to six specialist workers:

1. **Policy Parser** — atomizes policy text into factual claims
2. **Regulation Researcher** — hybrid RAG over GDPR articles
3. **Compliance Analyst** — verdicts each claim against retrieved articles
4. **Gap Hunter** — finds mandatory GDPR requirements the policy misses
5. **Remediation Drafter** — writes fixes for violations and gaps
6. **Report Writer** — assembles the final audit report

More to come.