# ComplyAgent

**Multi-agent GDPR compliance auditor.** Paste a privacy policy, get a structured audit report: per-statement verdicts, coverage gap analysis, remediation drafts, and a full supervisor reasoning log.

Built with LangGraph (supervisor-worker multi-agent topology), hybrid RAG over the full EU GDPR text, and Groq-hosted `openai/gpt-oss-120b`.

---

## Demo

```
uv run streamlit run app.py
```

Paste any privacy policy text (or load a synthetic preset), choose **Full policy** or **Single clause**, and click **Run audit**. Results stream live as each worker completes.

---

## What it does

ComplyAgent runs six specialist workers in sequence, orchestrated by a LangGraph supervisor:

| Worker | Input | Output |
|---|---|---|
| **Policy Parser** | Raw policy text | Atomic `PolicyStatement` objects, each tagged with a GDPR category |
| **Regulation Researcher** | One `PolicyStatement` | Relevant `RegulationChunk` objects from the GDPR corpus (hybrid RAG + LLM query rewriting) |
| **Compliance Analyst** | Statement + retrieved chunks | `Finding` with verdict (`compliant` / `partial` / `violation` / `unclear`) and citations |
| **Gap Hunter** | All statements + findings | `Gap` objects for mandatory GDPR disclosures (Art. 13/14) the policy never addresses |
| **Remediation Drafter** | `Finding` or `Gap` | `Remediation` with a plain-English recommendation and drop-in policy language |
| **Report Writer** | Full audit state | `AuditReport` with executive summary and full markdown narrative |

The supervisor makes three real routing decisions at runtime:

1. **Case 1 vs. Case 2** — single-clause audits skip the Gap Hunter entirely
2. **Confidence-based re-retrieval** — low-confidence findings trigger the Researcher to retry (capped at `max_reretrieval=2`)
3. **Remediation filtering** — only `violation` and `partial` findings + all gaps get remediations; `compliant` and `unclear` are passed through

Every decision is logged to a `SupervisorState.decisions` trail, visible in the UI's reasoning log panel.

---

## Architecture

```
raw policy text
      │
      ▼
┌─────────────┐
│Policy Parser│  → list[PolicyStatement]
└─────────────┘
      │
      ▼  (one branch per statement, via LangGraph Send)
┌──────────────────────────────┐
│Regulation Researcher         │  LLM rewrites statement → GDPR search query → retrieve()
│  +                           │
│Compliance Analyst            │  Verdict + citations + confidence score
└──────────────────────────────┘
      │
      ▼  (confidence check → retry if < 0.6, cap at 2 retries)
┌────────────┐       ┌──────────────────┐
│ Gap Hunter │  OR   │ (Case 1: skipped)│
└────────────┘       └──────────────────┘
      │
      ▼
┌───────────────────┐
│Remediation Drafter│  (violation/partial findings + all gaps only)
└───────────────────┘
      │
      ▼
┌─────────────┐
│Report Writer│  → AuditReport
└─────────────┘
```

### Retrieval pipeline (Phase 2)

Hybrid retrieval over 882 GDPR chunks (709 articles + 173 recitals):

- **BM25** (sparse, exact legal terminology matching)
- **BAAI/bge-base-en-v1.5** dense embeddings stored in ChromaDB
- **Weighted RRF fusion** (BM25 weight 0.4, dense weight 0.6)
- **BAAI/bge-reranker-v2-m3** cross-encoder reranking

Evaluated against 90 queries from [ClaimRAG-LAW](https://huggingface.co/datasets/SNTSVV/ClaimRAG-LAW) (articles-only subset for fair comparison):

| Metric | Value |
|---|---|
| Recall@5 | 0.71 |
| Recall@10 | 0.79 |
| MRR | 0.59 |

Full methodology: [`docs/eval_notes.md`](docs/eval_notes.md)

---

## Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph (StateGraph, Send fan-out, conditional edges, cyclic retry loop) |
| LLM | Groq `openai/gpt-oss-120b` (primary), Cerebras (fallback) |
| LLM framework | LangChain / LangChain-Groq / LangChain-Cerebras |
| Vector store | ChromaDB (persistent) |
| Embeddings | BAAI/bge-base-en-v1.5 |
| Reranker | BAAI/bge-reranker-v2-m3 |
| Sparse retrieval | rank_bm25 (BM25Okapi) |
| Schemas | Pydantic v2 |
| Config | Hydra / OmegaConf |
| UI | Streamlit (streaming via LangGraph `.stream()`) |
| Observability | LangSmith (auto-instrumented) |
| Package manager | uv |
| Testing | pytest (unit: mocked LLM, integration: real LLM) |

---

## Quickstart

```powershell
# Install dependencies
uv sync

# Add your API keys to .env (copy from .env.example)
copy .env.example .env
# Fill in GROQ_API_KEY (required), LANGSMITH_API_KEY (optional)

# Run the Streamlit app
uv run streamlit run app.py
```

### Run programmatically

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

### Stream events (for custom UIs)

```python
from complyagent.supervisor.run_audit import stream_audit
from complyagent.supervisor.events import AuditEvent, AuditCompleteEvent

for event in stream_audit(raw_policy_text=..., audit_mode="full_policy"):
    if isinstance(event, AuditEvent):
        print(f"[{event.phase}] {event.decision.reasoning if event.decision else 'done'}")
    elif isinstance(event, AuditCompleteEvent):
        print(event.report.executive_summary)
```

---

## Project structure

```
complyagent/
├── app.py                          # Streamlit entry point
├── data/
│   ├── policies/synthetic/         # Three synthetic test policies + ground-truth sidecars
│   ├── processed/chunks.json       # 882 GDPR chunks (pre-built)
│   ├── chroma/                     # Persistent ChromaDB vector index
│   └── eval/                       # Integration test baselines
├── docs/
│   ├── eval_notes.md               # Retrieval evaluation methodology + results
│   └── project_notes.md            # Full technical reference (architecture decisions, bugs, lessons)
├── src/complyagent/
│   ├── agents/                     # Six worker functions + LLM factory + retry helper
│   ├── demo/                       # Synthetic AuditReport fixture for UI development
│   ├── prompts/                    # ChatPromptTemplate definitions (one per worker)
│   ├── retrieval/                  # BM25, embeddings, ChromaDB, RRF, reranker, retrieve()
│   ├── schemas/                    # Pydantic models (policy, findings, gaps, report, state)
│   └── supervisor/                 # LangGraph graph, run_audit, stream_audit, events
├── tests/
│   ├── agents/                     # Unit tests (mocked LLM, 46 tests)
│   ├── supervisor/                 # Unit tests (mocked workers, 16 tests)
│   └── integration/                # Real-LLM integration tests (3 policies, @pytest.mark.integration)
└── scripts/                        # Spot-check scripts for manual verification
```

---

## Validation results

| Test | Result |
|---|---|
| Policy C (8 documented violations) | **8/8 caught** in a single real-LLM run |
| Policy A (mostly compliant) | Pending (deferred to post-tier upgrade) |
| Policy B (subtle gaps) | Pending (deferred to post-tier upgrade) |
| Single-clause retention violation | Correct `violation` verdict, confidence 0.96, cites `GDPR-Art-5-1-e` |
| Single-clause vague sharing clause | Correct `violation` after 2 retries (retry loop demonstrated live) |

Policy C baseline output: [`data/eval/phase4_policy_c_baseline.txt`](data/eval/phase4_policy_c_baseline.txt)

---

## Guardrails

| Parameter | Value | Purpose |
|---|---|---|
| `max_iterations` | 15 | Hard ceiling on supervisor decision count; prevents runaway loops |
| `max_reretrieval` | 2 | Per-statement retry cap on low-confidence findings |
| `confidence_threshold` | 0.6 | Minimum Analyst confidence before triggering re-retrieval |
| `stale_state_threshold` | 3 | Supervisor turns without state change before escalation |

All chains are wrapped with `with_retry(stop_after_attempt=5, wait_exponential_jitter=True)` to handle rate-limit errors.

---

## Known limitations and deferred work

- **Free-tier rate limits** (Groq: 8k TPM, 200k TPD) constrain integration test throughput. Policies A and B integration tests have been written and validated to run; execution deferred to post-tier upgrade.
- **Phase 5 (formal evaluation)** deferred: verdict accuracy at scale, RAGAS faithfulness eval on the Analyst, full OPP-115 category-routing benchmarks.
- **Recital preference in citations:** the Analyst occasionally cites GDPR Recitals (interpretive context) rather than the binding Article text. Calibration issue, not a structural bug.
- **Free-tier demo speed:** a full-policy audit takes 10-15 minutes on Groq free tier due to rate-limit backoff. Single-clause audits complete in 1-3 minutes. Dev Tier / Cerebras eliminates most of this.
- **Phase 7** (CI/CD, Docker, Streamlit Cloud deployment) not yet implemented.

---

## Development phases

| Phase | Deliverable | Status |
|---|---|---|
| 1 | Pydantic schemas, GDPR PDF chunker (882 chunks), synthetic test policies | ✅ Complete |
| 2 | Hybrid RAG pipeline, ChromaDB, BM25, RRF, reranker, retrieval eval | ✅ Complete |
| 3 | Six worker agents (46 unit tests) | ✅ Complete |
| 4 | LangGraph supervisor, routing, retry loop, decision logging (16 unit tests + Policy C integration) | ✅ Complete |
| 5 | Formal evaluation (verdict accuracy, RAGAS faithfulness, OPP-115 routing) | ⏳ Deferred |
| 6 | Streamlit demo UI, LangSmith, streaming | ✅ Complete |
| 7 | CI/CD, Docker, Streamlit Cloud deployment | ⏳ Pending |
