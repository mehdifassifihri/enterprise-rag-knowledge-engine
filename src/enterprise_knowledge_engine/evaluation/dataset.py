import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class BenchmarkDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(pattern=r"^[a-z0-9-]+$")
    tenant: str = Field(pattern=r"^[a-z0-9-]+$")
    path: str


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str
    documents: list[BenchmarkDocument] = Field(min_length=1, max_length=100)


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^q[0-9]{3}$")
    tenant: str
    question: str = Field(min_length=1, max_length=1000)
    category: str
    relevance: dict[str, StrictInt]
    reference_answer: str | None
    expected_status: Literal["answered", "insufficient_evidence"]
    forbidden_substrings: list[str] = Field(default_factory=list, max_length=20)


class Dataset:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.manifest = Manifest.model_validate_json((root / "manifest.json").read_text())
        self.questions = [
            Question.model_validate_json(line)
            for line in (root / "questions.jsonl").read_text().splitlines()
            if line
        ]
        labels = {d.label: d for d in self.manifest.documents}
        if len(labels) != len(self.manifest.documents):
            raise ValueError("Duplicate document labels")
        if len({q.id for q in self.questions}) != len(self.questions):
            raise ValueError("Duplicate question IDs")
        if not 30 <= len(self.questions) <= 100:
            raise ValueError("Benchmark requires 30–100 questions")
        for doc in self.manifest.documents:
            self.content(doc)
        for question in self.questions:
            if question.tenant not in {d.tenant for d in labels.values()}:
                raise ValueError("Unknown question tenant")
            if question.expected_status == "answered" and not question.reference_answer:
                raise ValueError("Answered question requires a reference")
            for label, grade in question.relevance.items():
                if label not in labels or labels[label].tenant != question.tenant:
                    raise ValueError("Relevance must reference documents authorized for the tenant")
                if type(grade) is not int or not 1 <= grade <= 3:
                    raise ValueError("Relevance grades must be integers 1–3")
        digest = hashlib.sha256()
        for path in [root / "manifest.json", root / "questions.jsonl"]:
            digest.update(path.read_bytes())
        for doc in self.manifest.documents:
            digest.update(self.content(doc))
        self.sha256 = digest.hexdigest()

    def content(self, doc: BenchmarkDocument) -> bytes:
        path = (self.root / doc.path).resolve()
        if not path.is_relative_to(self.root) or path.suffix != ".md":
            raise ValueError("Benchmark documents must be Markdown within dataset root")
        content = path.read_bytes()
        if not content or len(content) > 100000:
            raise ValueError("Benchmark document must be nonempty and <=100KB")
        return content
