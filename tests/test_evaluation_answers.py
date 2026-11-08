import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from qa_support import FACT, answer_json, result, retrieved

from enterprise_knowledge_engine.evaluation.answers import OpenAIJudge, RecordingLLM, check_answer
from enterprise_knowledge_engine.evaluation.dataset import Question
from enterprise_knowledge_engine.qa.context import build_context
from enterprise_knowledge_engine.qa.providers import FakeLLMProvider, LLMCompletion
from enterprise_knowledge_engine.qa.schemas import AskRequest
from enterprise_knowledge_engine.qa.service import answer_question
from enterprise_knowledge_engine.retrieval.reranking import NoopReranker


def fixture_answer(settings, monkeypatch):
    import enterprise_knowledge_engine.qa.service as qa

    monkeypatch.setattr(qa, "search", lambda *a: retrieved())
    recorder = RecordingLLM(FakeLLMProvider(answer_json()))
    response = answer_question(
        MagicMock(),
        result().document_id,
        AskRequest(question="policy"),
        settings,
        MagicMock(),
        NoopReranker(),
        recorder,
    ).response
    sources = recorder.sources
    assert sources == [
        s.model_dump(mode="json") for s in build_context([result()], settings).sources
    ]
    question = Question(
        id="q001",
        tenant="a",
        question="policy",
        category="semantic",
        relevance={"policy": 3},
        reference_answer=FACT,
        expected_status="answered",
    )
    return question, response, sources


def test_deterministic_answer_checks(settings, monkeypatch):
    question, response, sources = fixture_answer(settings, monkeypatch)
    metrics = check_answer(question, response, sources)
    assert metrics["reference_exact_match"]
    assert metrics["citation_validity"]
    assert metrics["quote_membership"]
    assert metrics["abstention_correct"]
    assert metrics["faithfulness"] is None
    assert not check_answer(question, response, [])["citation_validity"]
    response.citations[0].supporting_quotes = ["invented private fact"]
    assert not check_answer(question, response, sources)["quote_membership"]


@pytest.mark.parametrize("content", ["{invalid", json.dumps({"correctness": {"score": 3}})])
def test_invalid_judge_output_is_not_a_score(settings, monkeypatch, content):
    question, response, sources = fixture_answer(settings, monkeypatch)
    judge = OpenAIJudge(settings, "fixture-judge", max_calls=1)
    judge.provider = SimpleNamespace(
        generate_structured=lambda *a: LLMCompletion(content, "fixture")
    )
    output = judge.evaluate(question, response, sources)
    assert output["status"] == "error"
    assert output["scores"] is None
    assert judge.evaluate(question, response, sources)["status"] == "not_run"


def test_valid_judge_evidence_and_minimal_payload(settings, monkeypatch):
    question, response, sources = fixture_answer(settings, monkeypatch)
    score = {"score": 2, "rationale": "Exact source support.", "evidence": [FACT]}
    payload = json.dumps(dict.fromkeys(["correctness", "faithfulness", "citation_support"], score))
    judge = OpenAIJudge(settings, "fixture-judge")
    provider = MagicMock()
    provider.generate_structured.return_value = LLMCompletion(payload, "fixture")
    judge.provider = provider
    assert judge.evaluate(question, response, sources)["scores"]["correctness"]["score"] == 2
    sent = provider.generate_structured.call_args.args[0][1]["content"]
    assert "chunk_id" not in sent and "document_id" not in sent
    assert "history" not in sent
    score["evidence"] = ["nonexistent evidence"]
    provider.generate_structured.return_value = LLMCompletion(
        json.dumps(dict.fromkeys(["correctness", "faithfulness", "citation_support"], score)),
        "fixture",
    )
    assert judge.evaluate(question, response, sources)["status"] == "error"


def test_judge_provider_failure_is_missing_score(settings, monkeypatch):
    question, response, sources = fixture_answer(settings, monkeypatch)
    judge = OpenAIJudge(settings, "fixture-judge")
    judge.provider = MagicMock()
    judge.provider.generate_structured.side_effect = RuntimeError("SECRET KEY")
    output = judge.evaluate(question, response, sources)
    assert output["scores"] is None
    assert "SECRET" not in json.dumps(output)


@pytest.mark.parametrize("score", [True, False, "2", 2.0, -1, 3])
def test_judge_scores_are_strict_bounded_integers(score):
    from enterprise_knowledge_engine.evaluation.answers import JudgmentScore

    with pytest.raises(ValueError):
        JudgmentScore(score=score, rationale="fixture", evidence=["fixture"])
