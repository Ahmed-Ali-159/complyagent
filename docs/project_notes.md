# ComplyAgent — Full Technical Reference

This document is a complete narrative of the project: every architectural decision, why it was made, every significant bug encountered, and every lesson learned. Written as a reference for future revision.

---

## Project overview

ComplyAgent audits privacy policies against GDPR. It takes raw policy text and returns a structured `AuditReport` containing: atomic policy statements extracted by the Parser, per-statement compliance findings from the Analyst, coverage gap findings from the Gap Hunter, remediation drafts for everything non-compliant, and a final markdown report with executive summary.

The key design principle: **workers are pure functions; the supervisor owns all routing logic.** Workers do one thing (parse, retrieve, analyze, etc.) and return typed output. The LangGraph supervisor decides what runs next, when to retry, and what to skip.

---

## Phase 1: Schemas + data + chunker

### Pydantic schema decisions

**Discriminated union on `RegulationChunk`:** articles and recitals are structurally different (articles have paragraph/point sub-divisions; recitals don't). A discriminated union on `source_type: Literal["article", "recital"]` means the type system enforces which fields are valid for which chunk type. The `@model_validator(mode="before")` derives `source_type`, `article_number`, `paragraph`, etc. from the `chunk_id` string at construction time — callers never set these manually.

**`chunk_id` format:** `GDPR-Art-{article}[-{paragraph}][-{point}]` or `GDPR-Rec-{recital}`. Validated by regex in the model validator. This became important in Phase 3 unit tests — fake chunk IDs that didn't match the pattern caused `ValidationError` before they could be used.

**`PolicyStatement.source_span`:** tracks the verbatim original text a statement was distilled from. Distinct from `text` (which may be lightly reworded for clarity). Purpose: the audit report needs to cite the policy's *actual words*, not the system's cleaned-up paraphrase. Phrased as `str | None` because the LLM occasionally can't isolate a clean span.

**`AuditReport.decisions`:** added in Phase 6 to make the reasoning log available in the report object (and therefore in the UI). Required moving `SupervisorDecision` from `supervisor.py` into `report.py` to avoid a circular import — `supervisor.py` imports `AuditReport`, so `report.py` can't import from `supervisor.py`. The fix: define `SupervisorDecision` where it's needed structurally (`report.py`) and re-import it into `supervisor.py` for backward compatibility.

**The circular import / Pydantic identity bug:** Pydantic's runtime validation does a strict *class identity* check, not just structural compatibility. If `SupervisorDecision` is imported via two different paths (e.g. `from complyagent.schemas.report import SupervisorDecision` and `from complyagent.schemas.supervisor import SupervisorDecision` after a re-export), Python may have two separate class objects in memory, and Pydantic raises `ValidationError: Input should be a valid dictionary or instance of SupervisorDecision`. Solution: **always import from the module that defines the class**, not from re-export paths. This bug surfaced three times and took a while to diagnose.

### GDPR PDF chunker

Structure-aware chunker that preserves the GDPR's hierarchical structure: chapters, articles, paragraphs, and sub-points are all tracked. Two types of chunks: article provisions (binding law) and recitals (interpretive context). 882 chunks total: 709 articles + 173 recitals.

Important: recitals are often more useful for explaining *why* a rule exists than the terse article text itself. This matters in Phase 2's retrieval evaluation — the ClaimRAG-LAW benchmark only credits article-chunk answers, not recital ones, meaning our retrieval is *better* than the benchmark score implies for real-world use.

### Synthetic test policies

Three synthetic policies with documented ground-truth sidecars (`_violations.json`):
- **Policy A** (`policy_a_mostly_compliant.txt`): mostly compliant, a few minor issues
- **Policy B** (`policy_b_subtle_gaps.txt`): no outright false statements but misses mandatory disclosures — designed to test Gap Hunter specifically
- **Policy C** (`policy_c_egregious_violations.txt`): deliberately extreme violations — the sanity-check fixture

The sidecars document `violation_id`, `section` (maps to a section header in the policy text), `violated_articles` (GDPR chunk_ids), and `expected_verdict`. These became the integration test's ground truth in Phase 4.

---

## Phase 2: Hybrid retrieval

### Why hybrid (BM25 + dense), not just dense

GDPR text uses precise legal terminology — "data minimisation," "storage limitation," "lawful basis," "data subject rights" — that appears verbatim in relevant articles. BM25 (sparse, keyword-based) excels at exact terminology matching but struggles with semantic similarity. Dense embeddings handle paraphrase and semantic proximity but sometimes miss exact legal terms. RRF fusion of both gets the best of each.

### Architecture

**BM25:** `rank_bm25.BM25Okapi`. Never persisted — rebuilt in-memory from `chunks.json` on startup. Stateless, fast to rebuild.

**Dense embeddings:** `BAAI/bge-base-en-v1.5`. Articles have their article title prepended before embedding ("Article 5 — Principles relating to processing of personal data: [text]") to improve semantic matching. Recitals use bare text. Stored in ChromaDB.

**RRF fusion:** Weighted RRF with BM25 weight 0.4, dense weight 0.6. The higher dense weight reflects that semantic search is more useful for the query-rewriting use case (the Researcher rewrites policy text into GDPR-native queries).

**Reranker:** `BAAI/bge-reranker-v2-m3` cross-encoder. Takes the RRF-fused top-N candidates and re-scores them by joint query-chunk relevance. Catches cases where the biencoder embedding similarity didn't fully capture relevance.

### Retrieval evaluation

ClaimRAG-LAW benchmark: 90 ground-truth-verified GDPR queries. Because the benchmark's ground truth only ever cites articles (never recitals), we evaluated on an articles-only filtered subset for a fair comparison.

Results: Recall@5 = 0.71, Recall@10 = 0.79, MRR = 0.59.

Gap analysis: ~7 points of Recall@5 lost to recital/article slot competition (a recital got ranked higher than the article the benchmark expected). Remaining gap: multi-hop questions where the ground-truth article requires knowing context from adjacent articles — a retrieval design limitation, not a defect.

**Decision: accepted and documented honestly, not chased further.** Adding more complexity to fix edge cases that are partly attributable to benchmark-strictness would have diminishing returns.

---

## Phase 3: Six worker agents

### Design principles

**Workers are pure functions, not classes.** They take typed inputs, return typed outputs, have no state, make no calls to other workers. All stateful orchestration lives in the Supervisor (Phase 4). This makes workers independently testable with mocked LLMs.

**One schema for workers, one for domain.** Workers use private internal schemas (`_ParsedStatement`, `_AnalystOutput`, etc.) that expose only the fields the LLM should fill in. Python code assigns the rest (IDs, `target_kind`, `target_id`). This prevents the LLM from inventing IDs or mangling structured fields.

**LCEL composition for all chains:** `prompt | model.with_structured_output(Schema)`. Gives streaming/batch/async for free if Phase 6 needs them. Idiomatic LangChain.

**`with_llm_retry` wrapper:** all chains wrapped with `chain.with_retry(stop_after_attempt=5, wait_exponential_jitter=True, retry_if_exception_type=(Exception,))`. Applied at the chain level (after `.with_structured_output()`) not at the model level, because `RunnableRetry` doesn't forward `with_structured_output` attribute access — wrapping the model before calling `.with_structured_output()` causes `AttributeError`.

### Per-worker decisions

**Policy Parser:** `PolicyStatementList` wrapper schema because `with_structured_output` binds one schema, not a list. Unwrapped before return. `statement_id` assigned by Python (`stmt-001`, `stmt-002`, ...) in document order — deterministic and never asked of the LLM. Short-circuit: inputs under 5 chars return `[]` without calling the LLM.

**Compliance Analyst:** Verdict `unclear` is explicitly a legitimate choice in the prompt, not a last resort. This matters because LLMs default to confident verdicts even when evidence is weak. The few-shot example showing `unclear` with low confidence and empty citations is the most important example. Citation filtering: post-LLM Python filter drops any `chunk_id` in `cited_chunk_ids` that wasn't in the input chunk set. Silently drops, doesn't raise — an audit shouldn't fail because of a citation typo.

**Regulation Researcher:** The only tool-using worker. Uses LangChain's `create_agent` with `retrieve_gdpr_chunks` as a bound tool. The tool's `@tool` function does two things: calls the real `retrieve()` and captures the result in a module-level variable `_last_retrieve_result`. The agent's final message is natural language ("here are the chunks...") — we need the actual objects, not parsed text. Module-level capture is the cleanest extraction pattern. `recursion_limit=4` enforces the 1-call cap at the framework level (3 steps for a 1-tool-call path: agent decides → tool runs → agent answers; cap of 4 allows this with 1 step headroom). Defensive fallback: if the agent never calls the tool, fall back to `retrieve(statement.text)` directly.

**Gap Hunter:** Single batch call over all statements + the hardcoded checklist. Checklist defined in `gap_checklist.py` as `list[ChecklistItem(chunk_ids, requirement, severity)]`. Self-contained (includes the requirement description as a one-liner) rather than referencing chunk text at runtime — avoids coupling to retrieval, and the LLM benefits from human-written summaries more than verbose GDPR legalese. Validation: uses `frozenset` equality to match the LLM's returned `gdpr_basis` against checklist items. Order-independent. Fabricated gaps are silently dropped. IDs renumbered after filtering so they stay sequential.

**Remediation Drafter:** Two separate prompts (Finding vs. Gap), selected internally based on `isinstance(target, Finding)`. Finding prompt is rewrite-style; Gap prompt is additive-content style. LLM produces `recommendation` + `suggested_policy_text`; Python sets `target_kind`, `target_id`, `remediation_id`. Three input-validation checks raise `ValueError` rather than silently producing wrong output: Finding without `original_statement`, Gap with unexpected `original_statement`, mismatched IDs. Explicit mismatched-ID check catches a specific Phase 4 bug class where the supervisor loops over findings and statements without proper alignment.

**Report Writer:** `max_tokens=8192` via `.bind(max_tokens=8192)` on the model before the pipe — applied as a per-call override, not at the factory level. In Phase 4 integration testing, even this was too large for the free-tier Groq request ceiling (8k TPM limit = 8k tokens *per request*, not per minute). Fixed by removing `suggested_policy_text` from the LLM-facing prompt — it's still in the `AuditReport.remediations` passthrough, available for the UI to render. The LLM-generated markdown stays light and readable; the UI takes responsibility for surfacing the full remediation detail on demand.

### Unit test strategy

All worker tests use `RunnableLambda` (a real LangChain Runnable) as the mock, not `MagicMock`. Critical lesson: `PARSER_PROMPT | MagicMock()` builds a real LCEL chain, but `MagicMock`'s `__or__` returns something that doesn't preserve the configured `return_value` cleanly. Using `RunnableLambda(lambda _: result)` as the mock returns a genuine Runnable that the `|` operator composes correctly.

---

## Phase 4: LangGraph supervisor

### State design

`SupervisorState` is a Pydantic model annotated with LangGraph reducers on accumulator fields:

- `statements`, `findings`, `gaps`, `remediations`, `decisions`: `Annotated[list[T], operator.add]` — append on merge
- `retrieved_chunks`: `Annotated[dict, lambda a, b: {**a, **b}]` — dict merge, later writes win per key
- `findings` (special): custom `_latest_finding_per_statement` reducer — keeps the most recent Finding per `statement_id` so retries replace rather than append

**Why `findings` needs a custom reducer:** the re-retrieval retry loop re-runs `process_statement` for low-confidence statements. The new finding for that statement should *replace* the old one, not append alongside it. Without the custom reducer, both findings end up in the list and every downstream consumer (Gap Hunter, Remediation, Report Writer) sees duplicates.

`pending_retry_ids: list[str]` — a bookkeeping field the `check_confidence` node writes and the `route_after_confidence_check` router reads. Written fresh every confidence-check turn (Pydantic default last-write-wins for non-annotated fields), so it auto-resets between turns.

`audit_mode: Literal["single_clause", "full_policy"]` — set at audit start, never modified. The explicit user flag, not inferred from statement count (per the brief's "NOT a heuristic length detection" design decision).

### Graph topology

```
START → parser
parser → [fan-out via Send] → process_statement (per statement)
process_statement → check_confidence (converges all branches)
check_confidence → route_after_confidence_check [conditional]
  → process_statement (retry fan-out, cyclic)
  → route (passthrough, when no retries needed)
route → route_after_processing [conditional]
  → gap_hunter (Case 2)
  → remediation (Case 1, skips gap_hunter)
gap_hunter → remediation
remediation → report_writer
report_writer → END
```

**The `route` passthrough node** — a no-op lambda that exists solely to be the named destination when `route_after_confidence_check` decides "no retries, proceed." LangGraph conditional edges return node names, not functions. Without this node, there's no clean string to return when the flow should proceed to case-routing.

**Fan-out via `Send`:** `process_statement` is fanned out once per statement. Each `Send` payload is a minimal dict `{"statement": stmt}` — not a full state copy. Fanned-out nodes receive dicts, not Pydantic state instances, so they use `state["statement"]` (dict access), not `state.statement` (attribute access). This was Phase 4's first real failure: the original code used `state.statements[0]` assuming a Pydantic object. LangGraph passes fan-out payloads as dicts.

**Fan-out-of-fan-out problem:** the first attempt had separate `researcher_node` and `analyst_node` with two layers of fan-out. This caused each researcher branch to emit its own fan-out to all analysts, multiplying invocations quadratically. Fixed by combining into one `process_statement_node` that runs both researcher and analyst per statement — one layer of fan-out, no multiplication.

**The cyclic retry edge:** `check_confidence` → `process_statement` is a cycle. LangGraph handles this via `add_conditional_edges` returning a `list[Send]` (for retry fan-out) or a string `"route"` (for proceed). The `route_after_confidence_check` function returns either — this is how LangGraph's conditional edges support both "send to specific nodes with payloads" and "route to a named node."

### Decision logging

Every routing decision gets a `SupervisorDecision` appended to `state.decisions`. The `_make_decision()` helper takes the current state, builds the decision with `iteration = state.iteration + 1`, and the node returns both the decision (appended via the `add` reducer) and the new iteration count. This maintains the invariant `state.iteration == len(state.decisions)`.

`max_iterations=15` enforced in `route_after_confidence_check`: if `state.iteration >= MAX_ITERATIONS`, force-route to `"route"` regardless of pending retries. Prevents runaway loops from bugs in the retry logic.

### Integration testing

Policy C integration test result: **8/8 documented violations caught** in a single real-LLM run. Total: 11 findings (10 violations + 1 unclear), 16 remediations.

Rate-limit issues encountered:
- **TPM (8k tokens/minute):** hit during per-statement processing. Solved by `with_llm_retry` with exponential backoff absorbing the 18-second waits.
- **TPD (200k tokens/day):** hit when trying to run Policy B after Policy C in the same day. Each full-policy audit consumes the entire free-tier daily budget. Policies A and B integration tests written but deferred to post-tier upgrade.
- **413 Request Too Large:** Report Writer's prompt hit 12,476 tokens on a full Policy C state, exceeding the free tier's 8k per-request limit. Fixed by removing `suggested_policy_text` from the report prompt.

---

## Phase 5: Evaluation

Deferred. The work that was planned and why each piece matters:

**Verdict accuracy:** run all three synthetic policies, compare system verdicts against sidecar ground truth. The Phase 4 integration test gives you Policy C's result (8/8); Policies A and B need one run each.

**RAGAS faithfulness:** use RAGAS to measure whether the Analyst's rationale text actually follows from the retrieved chunks, or whether it's hallucinating legal reasoning not present in the context. This is the most novel eval component and would directly measure the system's most important failure mode. RAGAS can compute this automatically as "LLM-as-judge."

**OPP-115 category routing:** sample from the `alzoubi36/opp_115` HuggingFace dataset, run through the Parser, compare predicted `StatementCategory` against OPP-115 labels (with a mapping dict). Would demonstrate the Parser's generalization to real-world policy text.

**What was done instead of Phase 5:** two real single-clause demo audits that confirmed the system works correctly (retention violation with confidence 0.96, vague data-sharing clause triggering the retry loop correctly and returning a violation verdict).

---

## Phase 6: Streamlit UI

### Architecture decisions

**`stream_audit` vs `run_audit`:** two separate public functions in `run_audit.py`. `run_audit` uses `.invoke()` for tests and blocking callers. `stream_audit` is a generator using `.stream(mode="updates")`, yielding `AuditEvent` objects per node completion and a terminal `AuditCompleteEvent` carrying the final report.

**`AuditEvent` design:** carries `phase` (node name), `decision` (most recent `SupervisorDecision` if any), and `stats` (running counters). The `decision.reasoning` string from Phase 4's decision logging becomes the live progress feed text — this design means the Phase 4 decision log and Phase 6 streaming UI share the same data, zero duplication.

**LangSmith:** activated via environment variables (`LANGSMITH_API_KEY`, `LANGSMITH_TRACING=true`, `LANGSMITH_PROJECT=complyagent`). Zero code changes — LangChain auto-instruments when env vars are present. Traces available at smith.langchain.com and invaluable for debugging: full prompt/response waterfall per audit, per-call latency, token counts.

**Streamlit container stacking bug:** the first streaming UI implementation used `st.container()` for the feed, re-wrapped in `with feed_placeholder.container():` on every event. Streamlit's `.container()` stacks a new nested container each call instead of overwriting — creating cumulative visual duplication (all prior entries re-rendered on every event). Fixed by switching `feed_placeholder` to `st.empty()` and calling `feed_placeholder.markdown(...)` directly, which overwrites the slot contents cleanly.

**Preset-to-textarea bug:** `st.text_area` with a `key=` parameter is "owned" by Streamlit — the `value=` parameter only sets the initial value and is ignored on subsequent reruns. Sidebar buttons that try to set a separate session-state variable and rely on `value=st.session_state.policy_text` to pick it up will silently fail. Fix: write directly to `st.session_state.policy_input` (the widget's own key) from the button handler, then call `st.rerun()`. The widget reads from its key on next render.

**File uploader infinite-rerun prevention:** `st.file_uploader` fires on every script rerun as long as a file is staged. Without a content-equality check before writing to session state, the upload handler would rewrite session state → trigger rerun → detect file again → rewrite session state → infinite loop. Fixed by checking `if file_contents != st.session_state.get("policy_input", "")` before writing.

**Demo fixture:** `src/complyagent/demo/fixture_report.py` builds a realistic `AuditReport` from hard-coded data — useful for iterating on the report UI without LLM calls. Removed the UI button that exposed it (sidebar clutter), kept the module for development use.

**`SupervisorDecision` in `AuditReport`:** added `decisions: list[SupervisorDecision] = []` to `AuditReport` so the reasoning log is available in the report object (and therefore in the UI). This triggered the circular import issue (see Phase 1 schema decisions) and later the Pydantic class-identity bug — the most persistent bug class in the whole project.

### Known UI limitation: no cancel button

Streamlit has no built-in way to cancel a running script from the UI. Browser refresh kills the streaming connection. In-flight LLM calls still complete (and still count against quota) even after refresh. For production, a session-state flag checked between streaming events would allow soft cancellation.

---

## Cross-cutting lessons

### The Pydantic identity bug (the one that kept coming back)

When you move a class from module A to module B and add a re-export (`from B import X` in A), Python code that imports from A still works. But Pydantic's runtime type validation does `type(obj) is ExpectedClass` — a strict identity check. If `ExpectedClass` was imported via two different module paths in the same Python session, they may be two separate class objects even if they're textually identical. The check fails.

Rule: **import every class from the module that defines it**. Re-exports are convenient for backward compatibility but dangerous with Pydantic validation. Every time you move a schema class, track down every import and update it to the canonical path.

### LangGraph fan-out fundamentals

- Fanned-out nodes receive `dict`, not Pydantic state — use dict access (`state["key"]`), not attribute access (`state.key`)
- Fan-out-of-fan-out multiplies invocations quadratically — if two consecutive nodes both fan out over N items, you get N² invocations
- `Send` payloads should be minimal — only what the destination node actually reads. Full state copies cause validation issues and are wasteful
- `stream_mode="updates"` yields the full decisions list (accumulated so far) on every chunk, not just the new decision — callers must dedupe

### Provider rate limits shape system design

The free-tier Groq constraints (8k TPM, 200k TPD) aren't just operational inconveniences — they revealed real design decisions:

- The Report Writer prompt needed to be trimmed to fit under the per-request limit
- Full-policy audits consume the entire daily budget, making iterative development on integration tests impossible on free tier
- The retry decorator's exponential backoff converts per-minute rate limits from crashes into slowdowns — but daily limits are unrecoverable

The `with_llm_retry` wrapper is the right mitigation for per-minute limits. Daily limits require tier upgrades or provider switching.

### RunnableLambda vs MagicMock for chain testing

LangChain's `|` operator (LCEL pipe) builds `RunnableSequence` objects. When you pipe a `ChatPromptTemplate | MagicMock()`, LangGraph treats the mock as a Runnable (because MagicMock has `__or__`), but the resulting sequence's `.invoke()` doesn't preserve the mock's `return_value` cleanly. Use `RunnableLambda(lambda _: your_result)` as the mock target — it's a real Runnable, the pipe composes correctly, and `.invoke()` returns whatever you want.

### Decisions that improved the project when challenged

Several design decisions got better because they were questioned:

- **Two-case architecture** (Case 1 vs. Case 2) emerged from pushing back on a one-size-fits-all pipeline
- **Articles-only eval framing** for the ClaimRAG-LAW benchmark emerged from honestly diagnosing why recital-inclusive recall was lower — the benchmark was unfair to a production system that correctly uses recitals
- **`_format_remediations` trimming** for the Report Writer emerged from a real 413 error that forced rethinking what the LLM actually needs to see vs. what's passthrough state
- **`RunnableLambda` mock pattern** emerged from diagnosing why the first 4/8 tests failed in Phase 3

---

## File index

| File | Purpose |
|---|---|
| `app.py` | Streamlit entry point |
| `src/complyagent/agents/llm_client.py` | Single LLM factory — the only file that imports `ChatGroq`/`ChatCerebras` |
| `src/complyagent/agents/_retry.py` | `with_llm_retry()` helper applied to all chains |
| `src/complyagent/agents/parser.py` | Policy Parser worker |
| `src/complyagent/agents/analyst.py` | Compliance Analyst worker |
| `src/complyagent/agents/researcher.py` | Regulation Researcher worker (tool-calling) |
| `src/complyagent/agents/gap_hunter.py` | Gap Hunter worker |
| `src/complyagent/agents/gap_checklist.py` | Hardcoded Art. 13/14 disclosure checklist |
| `src/complyagent/agents/remediation.py` | Remediation Drafter worker |
| `src/complyagent/agents/report_writer.py` | Report Writer worker |
| `src/complyagent/prompts/` | `ChatPromptTemplate` definitions, one per worker |
| `src/complyagent/retrieval/retrieve.py` | Public retrieval API + `get_chunk_by_id()` helper |
| `src/complyagent/retrieval/bm25_retriever.py` | BM25Okapi wrapper |
| `src/complyagent/retrieval/embeddings.py` | BGE embedding wrapper |
| `src/complyagent/retrieval/reranker.py` | Cross-encoder reranker |
| `src/complyagent/retrieval/rrf.py` | Weighted RRF fusion |
| `src/complyagent/schemas/report.py` | `SupervisorDecision` + `AuditReport` (note: SupervisorDecision lives here to avoid circular import) |
| `src/complyagent/schemas/supervisor.py` | `SupervisorState` with LangGraph reducers |
| `src/complyagent/schemas/findings.py` | `Finding`, `Gap`, `Remediation` |
| `src/complyagent/schemas/policy.py` | `PolicyStatement` |
| `src/complyagent/schemas/regulation.py` | `RegulationChunk` |
| `src/complyagent/schemas/enums.py` | `VerdictType`, `StatementCategory`, `GapSeverity`, `WorkerName` |
| `src/complyagent/supervisor/graph.py` | LangGraph graph definition, all node functions, routing functions |
| `src/complyagent/supervisor/run_audit.py` | `run_audit()` (blocking) + `stream_audit()` (streaming generator) |
| `src/complyagent/supervisor/events.py` | `AuditEvent` + `AuditCompleteEvent` for streaming |
| `src/complyagent/demo/fixture_report.py` | Realistic `AuditReport` fixture for UI development without LLM calls |
| `src/complyagent/config.py` | Pydantic Settings, loads from `config.yaml` + `.env` |
| `config.yaml` | All tunable parameters (model, retrieval weights, graph guardrails) |
| `data/policies/synthetic/` | Three synthetic policies + ground-truth `_violations.json` sidecars |
| `data/processed/chunks.json` | 882 pre-built GDPR chunks |
| `data/chroma/` | Persistent ChromaDB vector index |
| `data/eval/phase4_policy_c_baseline.txt` | Policy C integration test output (8/8 violations) |
| `docs/eval_notes.md` | Retrieval evaluation methodology + results |
| `tests/agents/` | Unit tests for all 6 workers (46 tests, mocked LLM) |
| `tests/supervisor/` | Unit tests for graph scaffolding + streaming (16 tests, mocked workers) |
| `tests/integration/` | Real-LLM integration tests (`@pytest.mark.integration`) |
| `scripts/` | Spot-check scripts for manual verification of each worker |
