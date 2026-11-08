import math
from pathlib import Path

import pytest

from enterprise_knowledge_engine.evaluation.dataset import Dataset
from enterprise_knowledge_engine.evaluation.metrics import aggregate, retrieval_metrics
from enterprise_knowledge_engine.evaluation.performance import latency_summary, percentile, run_load


def test_hand_calculated_graded_metrics():
    # Positions 2/3 have gains 7/1. Precision denominator is K.
    scores = retrieval_metrics(["x", "a", "b"], {"a": 3, "b": 1}, 3)
    assert scores["recall"] == 1
    assert scores["precision"] == pytest.approx(2 / 3)
    assert scores["mrr"] == 0.5
    assert scores["hit_rate"] == 1
    assert scores["ndcg"] == pytest.approx(
        (7 / math.log2(3) + 1 / math.log2(4)) / (7 + 1 / math.log2(3))
    )


@pytest.mark.parametrize("k", [1, 3, 5, 10])
def test_cutoffs_empty_duplicate_and_short_lists(k):
    scores = retrieval_metrics(["a", "a"], {"a": 1, "b": 1}, k)
    assert scores["recall"] == 0.5
    assert scores["precision"] == 1 / k
    assert scores["mrr"] == 1
    assert all(value == 0 for value in retrieval_metrics([], {"a": 1}, k).values())
    assert all(value is None for value in retrieval_metrics(["a"], {}, k).values())


@pytest.mark.parametrize("k", [0, -1, True, 1.5])
def test_invalid_k(k):
    with pytest.raises(ValueError):
        retrieval_metrics([], {}, k)


def test_macro_denominators_and_categories():
    rows = [
        {"category": "semantic", "ranked_labels": ["a"], "relevance": {"a": 1}},
        {"category": "missing", "ranked_labels": ["x"], "relevance": {}},
        {"category": "semantic", "ranked_labels": [], "relevance": {"a": 1}, "error": "timeout"},
    ]
    scores = aggregate(rows, [1])
    assert scores["overall"]["at_k"]["1"]["recall"] == {"value": 0.5, "denominator": 2}
    assert scores["overall"]["errors"] == 1
    assert scores["overall"]["zero_relevance_queries"] == 1
    assert scores["missing"]["at_k"]["1"]["recall"] == {"value": None, "denominator": 0}


def test_versioned_dataset_is_valid():
    dataset = Dataset(Path("evaluation/datasets/v1"))
    assert len(dataset.questions) >= 30
    assert len(dataset.sha256) == 64
    assert {q.category for q in dataset.questions} >= {
        "semantic",
        "exact_identifier",
        "multi_document",
        "paraphrase",
        "ambiguous",
        "missing_information",
        "conflicting_evidence",
        "tenant_isolation",
        "prompt_injection",
    }
    assert dataset.sha256 == Dataset(dataset.root).sha256


def test_dataset_rejects_paths_outside_root():
    from enterprise_knowledge_engine.evaluation.dataset import BenchmarkDocument

    dataset = Dataset(Path("evaluation/datasets/v1"))
    with pytest.raises(ValueError):
        dataset.content(BenchmarkDocument(label="bad", tenant="a", path="../README.md"))


def test_hand_calculated_latency_statistics():
    assert percentile([10.0, 20.0, 30.0, 40.0], 50) == 25
    assert percentile([10.0, 20.0, 30.0, 40.0], 95) == pytest.approx(38.5)
    assert percentile([], 95) is None
    assert latency_summary([10.0, 30.0])["average_ms"] == 20


@pytest.mark.parametrize(
    "kwargs",
    [
        {"base_url": "http://example.com"},
        {"base_url": "http://private:secret@localhost"},
        {"requests": 501},
        {"concurrency": 17},
        {"scenarios": ["hybrid"]},
        {"scenarios": ["ask"], "allow_paid": True, "requests": 11},
    ],
)
def test_load_safety_bounds(kwargs):
    args = {"base_url": "http://localhost", "key": "not-a-real-key", "scenarios": ["list"]}
    with pytest.raises(ValueError):
        run_load(**(args | kwargs))


def test_load_report_counts_http_failures(monkeypatch):
    import httpx

    import enterprise_knowledge_engine.evaluation.performance as performance

    original = httpx.Client

    def factory(**kwargs):
        return original(
            **kwargs,
            transport=httpx.MockTransport(
                lambda request: httpx.Response(503 if request.method == "POST" else 200, json={})
            ),
        )

    monkeypatch.setattr(performance.httpx, "Client", factory)
    output = run_load("http://127.0.0.1", "fixture", ["list", "keyword"], requests=3, concurrency=2)
    assert output["scenarios"]["list"]["failure_count"] == 0
    assert output["scenarios"]["keyword"]["failure_count"] == 3
    assert output["scenarios"]["keyword"]["errors"] == {"http_503": 3}
    assert output["scenarios"]["list"]["throughput_requests_per_second"] > 0


def test_unavailable_semantic_strategies_write_pending_without_database(settings, tmp_path):
    from enterprise_knowledge_engine.evaluation.runner import run

    dataset = Dataset(Path("evaluation/datasets/v1"))
    report = run(dataset, settings, tmp_path, [1, 3], ["vector", "hybrid", "hybrid_rerank"])
    assert report["metrics"] == {}
    assert all(s["status"] == "pending" for s in report["strategies"].values())


def test_paid_answer_evaluation_requires_explicit_real_provider(settings, tmp_path):
    from enterprise_knowledge_engine.evaluation.runner import run

    dataset = Dataset(Path("evaluation/datasets/v1"))
    with pytest.raises(ValueError, match="explicit paid"):
        run(dataset, settings, tmp_path, [1], ["keyword"], answers=True)
