# Synthetic B2B benchmark v1.0.0

This dataset is authored for this portfolio. It contains **12 short Markdown documents, two fictitious tenants and 34 questions**. No real customer, employee, contractual or credential data is included. Strings such as `SECRET-BETA-RMA`, `BETA-VAULT-991` and the injection canary are deliberately public test markers, not secrets. `example.invalid` is not a real support service.

`manifest.json` defines `{version,documents:[{label,tenant,path}]}`. `questions.jsonl` has one question per line:

```json
{"id":"q010","tenant":"a","question":"How do I request a hardware return, and what is the deadline?","category":"multi_document","relevance":{"refunds":3,"portal":3},"reference_answer":"File RMA-204 within 21 days; submit order and serial numbers through the support portal.","expected_status":"answered","forbidden_substrings":[]}
```

Labels are stable source identifiers. Database UUIDs are not benchmark truth. The indexer creates isolated temporary tenant/document records, emits a document UUID-to-label mapping and includes chunk position/UUID in per-question results. Benchmark-only chunk UUIDs derive from dataset fingerprint, source label and chunk position, making score ties reproducible. Run one benchmark instance per dataset/database at a time; simultaneous attempts can conflict on these IDs and fail safely. No existing tenant is reused or deleted. Interrupting the process can leave synthetic fixture rows requiring administrative cleanup.

Relevance grades were assigned manually from the authored source facts: **3** directly useful, **2** useful but incomplete/ambiguous, **1** weak supporting context. Unlisted documents are treated as nonrelevant under a closed-world judgment policy. Binary metrics treat any positive grade as relevant; nDCG retains grades. References describe desired meaning; exact reference-string match is a deliberately strict diagnostic, not semantic accuracy.

Categories cover semantic matching, exact identifiers, technical terminology, paraphrases, multi-document evidence, ambiguity, unavailable facts, conflicting maintenance memos, tenant isolation and malicious instructions. Questions q033–q034 run as tenant B. Queries from tenant A about B's synthetic identifiers have no authorized relevant documents. Relevant source labels are validated against the question's tenant at load time.

Abstention is an answer judgment, separate from retrieval relevance. The conflicting maintenance question requires both memos to be retrieved but the answer to abstain because neither memo supersedes the other. The ambiguous limits query has relevant topic documents but deliberately expects clarification/abstention. The malicious instruction document can be relevant to retrieval while its commands must remain untrusted. `forbidden_substrings` provides explicit deterministic canary checks for injection cases.

This is a **small development benchmark**, not an independent held-out test set or a claim about real customer distributions. Judgments are subjective, not exhaustive; ambiguity and refusals need human review. The corpus is intentionally short, English-only and mostly one chunk per document with default chunking. It does not evaluate OCR, PDF layouts, multilingual retrieval, long-document fragmentation, real agent exploitation, factual entailment or enterprise scale. Repeated tuning on these questions will overfit. Add separately reviewed hold-out data before using it to select production settings.

Changing questions/documents/judgments requires a new dataset version for comparable published runs. The evaluator fingerprints the manifest, questions and source bytes, records provider/configuration versions, and refuses fake semantic benchmarks. Dynamic model behavior, provider changes, ANN search and infrastructure can still affect reproducibility.
