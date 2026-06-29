# ComplyAgent

Multi-agent GDPR compliance auditor. Built with LangGraph (supervisor-worker topology), hybrid RAG over the EU GDPR, and Groq-hosted `openai/gpt-oss-120b`.

## Status

**Phase 4 complete.** End-to-end audit pipeline validated against synthetic Policy C (8/8 documented violations caught). Currently moving to Phase 6 (Streamlit demo). Phase 5 (formal eval) deferred — see Deferred Work below.

| Phase | Status |
|---|---|
| 1 — Schemas + synthetic policies + GDPR chunker | Complete |
| 2 — Hybrid retrieval (BM25 + dense + RRF + reranker) | Complete |
| 3 — Six worker agents | Complete (46 unit tests) |
| 4 — Supervisor + LangGraph orchestration | Complete (12 unit tests + Policy C integration) |
| 5 — Evaluation (verdict accuracy, citation correctness, OPP-115 routing) | Deferred |
| 6 — Streamlit demo | In progress |
| 7 — Polish, CI, deployment | Pending |

## Quickstart

```powershell
uv sync
uv run python -c "from complyagent.config import settings; print(settings.llm.worker_model)"
```

Running an audit programmatically:

```python
from complyagent.supervisor.run_audit import run_audit

report = run_audit(
    raw_policy_text=open("path/to/policy.txt").read(),
    audit_mode="full_policy",   # or "single_clause"
    policy_source="example.com/privacy",
)
print(report.executive_summary)
print(report.markdown_report)
```

## Architecture

A LangGraph supervisor coordinates six specialist workers, with three real runtime decisions hosted at the supervisor layer:

1. **Case routing** — single-clause vs. full-policy audits take structurally different paths (single-clause skips Gap Hunter entirely)
2. **Confidence-based re-retrieval** — when the Analyst returns a low-confidence verdict, the supervisor re-runs research+analysis for that statement (capped at `max_reretrieval=2`)
3. **Remediation skip filtering** — only violation/partial findings + all gaps receive remediations; compliant and unclear findings are passed through unchanged

Every supervisor decision is logged to a `SupervisorState.decisions` field, producing a fully auditable reasoning trail for each run.

### Workers

1. **Policy Parser** — atomizes policy text into self-contained factual claims, each tagged with a GDPR-relevant category
2. **Regulation Researcher** — LLM rewrites the statement into a GDPR-native search query, then invokes hybrid retrieval via a bound tool (one tool call per statement)
3. **Compliance Analyst** — verdicts each claim against retrieved articles; emits `compliant`, `partial`, `violation`, or `unclear` with a self-reported confidence score
4. **Gap Hunter** — checks the full statement set against a hardcoded checklist of mandatory GDPR Article 13/14 disclosures; runs only in full-policy audits
5. **Remediation Drafter** — writes process recommendations + drop-in policy text for each violation and gap
6. **Report Writer** — assembles the final `AuditReport` with executive summary and markdown narrative

### Hard guardrails

- `max_iterations=15` — supervisor decision-count ceiling; force-terminates retry loops
- `max_reretrieval=2` — per-statement retry cap
- `confidence_threshold=0.6` — trigger for re-retrieval
- All LLM chains wrapped with exponential-backoff retry to absorb rate-limit (429) errors

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

## Phase 4 Integration Result

End-to-end audit against synthetic Policy C (a deliberately egregious 8-violation fixture, included at `data/policies/synthetic/policy_c_egregious_violations.txt`):

- **8 of 8 documented violations caught**, including subtle ones (contractual waiver of GDPR rights, international transfers without safeguards, missing controller identity)
- 11 findings produced across all statements
- 16 remediations drafted (one per violation/partial finding + one per gap)
- Full audit completed in ~11 minutes on Groq free tier (most of which was rate-limit backoff)

Baseline output preserved at `data/eval/phase4_policy_c_baseline.txt`.

## Deferred Work

The following items are explicitly deferred from current phases, recorded here so the unfinished pieces remain visible:

- **Policy A & Policy B integration tests** — written but not yet run end-to-end. The free-tier Groq quota (200k tokens/day) supports approximately one full audit per day; these will be run after a tier upgrade.
- **Phase 5 — Formal evaluation** — verdict accuracy, citation correctness, gap recall, and OPP-115 category-routing benchmarks are planned but not yet implemented. Phase 4's integration test confirms the system works end-to-end; Phase 5 would measure how well it generalizes.
- **Human-in-the-loop verdict override** — `unclear` findings currently render as "manual review recommended" in the report. A UI-level override mechanism was scoped in the original plan but pushed to Phase 6 polish if time allows.