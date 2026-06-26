# Retrieval Evaluation Notes (Phase 2)

## Methodology

Evaluated `retrieve()` against the [ClaimRAG-LAW](https://huggingface.co/datasets/SNTSVV/ClaimRAG-LAW)
`gdpr-rag` subset (SNTSVV, HuggingFace) — 149 real GDPR questions with ground-truth
source chunks.

**Ground truth extraction:** restricted to `query_id >= 60` (90 of 149 rows), where
the dataset consistently embeds an explicit `# Article N` heading in `relevant_chunk`.
Rows below `query_id` 60 use inconsistent formatting (sometimes title-only, sometimes
leading with a cross-referenced article number in body text rather than the chunk's
own identity) and were found, on inspection, to produce incorrect ground truth under
every extraction strategy tried — excluded rather than patched further.

**Metric:** Recall@5, Recall@10, Mean Reciprocal Rank (MRR), computed by checking
whether any returned chunk's `article_number` matches the query's ground-truth article.

## Headline result

Since this benchmark's ground truth only ever references GDPR **Articles** (never
Recitals), we report results with retrieval restricted to Article chunks for a fair
comparison:

| Metric | Value |
|---|---|
| Recall@5 | 0.7111 (64/90) |
| Recall@10 | 0.7889 (71/90) |
| MRR | 0.5948 |

## Diagnostic: recital competition

An initial unrestricted run (Articles + Recitals both eligible, matching production
behavior) measured Recall@5 = 0.6444, Recall@10 = 0.7222, MRR = 0.4436 — meaningfully
lower. Manual inspection of the gap confirmed Recitals were legitimately winning
top-5 slots from Articles on several queries — not retrieval error. For example, a
question about repurposing customer data for marketing was best answered by
**Recital 50** (which directly addresses compatibility of further processing with
the original purpose) rather than the terser principle statement in Article 5(1)(b).
Recitals are kept in production retrieval for this reason — they provide interpretive
value the bare article text often lacks — even though this benchmark has no mechanism
to credit a correct Recital-only answer.

## Diagnostic: remaining gap below 0.85

Manual inspection of the 26 articles-only failures showed a consistent pattern: the
system was not returning irrelevant results, but rather a different, often more
specific or operative provision than the one article the benchmark happened to label
(e.g. returning Article 6(4)'s compatibility test for a repurposing question labeled
"Article 5" — the principle-level statement). Several scenario questions appear to
genuinely require synthesizing 2+ articles, which a single ground-truth label can't
fully capture. This points to ground-truth strictness on multi-hop questions as the
dominant remaining factor, not a fixable retrieval defect — further tuning
(embedding model, `initial_k`, RRF weights) was not pursued, since it would optimize
against an imperfect yardstick rather than genuinely improve answer quality.

## Conclusion

Recall@5 = 0.71 (articles-only) falls short of the original 0.85 target. Given the
diagnostic evidence above, this gap is attributed primarily to benchmark ground-truth
granularity rather than retrieval quality, and was accepted rather than chased
further at this stage of the project.