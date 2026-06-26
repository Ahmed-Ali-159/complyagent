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

## Retrieval Evaluation

Evaluated against 90 ground-truth-verified queries from the [ClaimRAG-LAW](https://huggingface.co/datasets/SNTSVV/ClaimRAG-LAW)
benchmark (SNTSVV, HuggingFace). Since this benchmark's ground truth labels only
ever reference GDPR Articles (never Recitals), we report Recall@5/MRR with
retrieval restricted to Articles for a fair comparison:

| Metric | Value |
|---|---|
| Recall@5 | 0.71 |
| Recall@10 | 0.79 |
| MRR | 0.59 |

In production, ComplyAgent's retrieval also returns Recitals — manual inspection
confirmed several "failed" queries under article-only ground truth were in fact
correctly answered by a highly relevant Recital instead (e.g. a purpose-limitation
scenario question was best answered by Recital 50, not the terser Article 5(1)(b)
principle statement). Recitals are kept in production retrieval because they
provide this kind of interpretive value the bare article text often lacks, even
though it means this benchmark — which has no mechanism to credit a correct
recital-only answer — slightly understates real-world answer quality.

Full methodology and diagnostic findings: [docs/eval_notes.md](docs/eval_notes.md)

More to come.