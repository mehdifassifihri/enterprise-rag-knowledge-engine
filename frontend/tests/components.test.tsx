import { expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ChatMessage } from "../src/components/assistant";
import { SearchResultCard } from "../src/components/playground";
import type { SearchResult } from "../src/lib/contracts";
it("renders untrusted answers as text rather than executable HTML", () => {
  const markup = renderToStaticMarkup(
    <ChatMessage
      role="assistant"
      content={'<script>alert("untrusted")</script> [S99]'}
      onCitation={() => {}}
    />,
  );
  expect(markup).not.toContain("<script>");
  expect(markup).toContain("&lt;script&gt;");
  expect(markup).toContain("[S99]");
  expect(markup).not.toContain("citation-badge");
});
it("labels RRF scores without implying calibrated confidence", () => {
  const result: SearchResult = {
    chunk_id: "11111111-1111-4111-8111-111111111111",
    document_id: "22222222-2222-4222-8222-222222222222",
    filename: "fixture.md",
    content: "Synthetic retrieval fixture",
    page: null,
    chunk_position: 0,
    start_offset: 0,
    end_offset: 27,
    rank: 1,
    score: 0.0327,
    score_type: "rrf",
    retrieval_score: 0.0327,
    sources: ["vector", "keyword"],
    vector_rank: 1,
    keyword_rank: 1,
    vector_distance: 0.2,
    cosine_similarity: 0.8,
    normalized_similarity: 0.9,
    keyword_score: 0.1,
    rrf_score: 0.0327,
    rerank_score: null,
  };
  const markup = renderToStaticMarkup(<SearchResultCard result={result} />);
  expect(markup).toContain("rrf");
  expect(markup).not.toContain("confidence");
  expect(markup).toContain(result.document_id);
});
