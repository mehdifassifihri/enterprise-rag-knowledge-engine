"""Document-level binary metrics and graded nDCG; missing judgments mean nonrelevant."""

import math
from collections.abc import Sequence

METRICS = ("recall", "precision", "mrr", "ndcg", "hit_rate")


def retrieval_metrics(ranked: Sequence[str], judgments: dict[str, int], k: int) -> dict:
    if type(k) is not int or k < 1:
        raise ValueError("K must be a positive integer")
    if any(type(g) is not int or not 0 <= g <= 3 for g in judgments.values()):
        raise ValueError("Relevance grades must be 0–3")
    # Multiple chunks of a document count once, at its first appearance.
    unique = list(dict.fromkeys(ranked))[:k]
    relevant = {label for label, grade in judgments.items() if grade > 0}
    if not relevant:
        return dict.fromkeys(
            METRICS
        )  # Undefined; do not award perfect scores to abstention queries.
    hits = [i for i, label in enumerate(unique, 1) if label in relevant]
    dcg = sum(
        (2 ** judgments.get(label, 0) - 1) / math.log2(i + 1) for i, label in enumerate(unique, 1)
    )
    ideal = sum(
        (2**grade - 1) / math.log2(i + 1)
        for i, grade in enumerate(sorted(judgments.values(), reverse=True)[:k], 1)
    )
    return {
        "recall": len(hits) / len(relevant),
        "precision": len(hits) / k,
        "mrr": 1 / hits[0] if hits else 0.0,
        "ndcg": dcg / ideal,
        "hit_rate": float(bool(hits)),
    }


def aggregate(rows: list[dict], ks: Sequence[int]) -> dict:
    output = {}
    for category in ["overall", *sorted({r["category"] for r in rows})]:
        group = rows if category == "overall" else [r for r in rows if r["category"] == category]
        reciprocal = [
            retrieval_metrics(r["ranked_labels"], r["relevance"], max(1, len(r["ranked_labels"])))[
                "mrr"
            ]
            for r in group
        ]
        reciprocal = [value for value in reciprocal if value is not None]
        negatives = [r for r in group if not any(r["relevance"].values()) and not r.get("error")]
        output[category] = {
            "mrr": {
                "value": sum(reciprocal) / len(reciprocal) if reciprocal else None,
                "denominator": len(reciprocal),
            },
            "negative_queries_returning_any": sum(bool(r["ranked_labels"]) for r in negatives),
            "negative_query_success_denominator": len(negatives),
            "queries": len(group),
            "zero_relevance_queries": sum(not any(r["relevance"].values()) for r in group),
            "errors": sum(r.get("error") is not None for r in group),
            "at_k": {},
        }
        for k in ks:
            scores = [retrieval_metrics(r["ranked_labels"], r["relevance"], k) for r in group]
            output[category]["at_k"][str(k)] = {}
            for metric in METRICS:
                values = [s[metric] for s in scores if s[metric] is not None]
                output[category]["at_k"][str(k)][metric] = {
                    "value": sum(values) / len(values) if values else None,
                    "denominator": len(values),
                }
    return output
