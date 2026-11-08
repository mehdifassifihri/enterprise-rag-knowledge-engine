"use client";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Clock3,
  FileText,
  Info,
  Loader2,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { ProviderNotice } from "./provider-notice";
import { api } from "@/lib/api";
import {
  capabilitiesSchema,
  searchInputSchema,
  searchSchema,
  type SearchMode,
  type SearchResult,
} from "@/lib/contracts";
import { EmptyState, ErrorState, PageHeading } from "./common";
import { Button } from "./ui/button";
export function SearchResultCard({ result }: { result: SearchResult }) {
  return (
    <article className="card result-card">
      <div className="between wrap">
        <div className="row">
          <span className="result-rank">{result.rank}</span>
          <FileText size={15} className="muted" />
          <h2 style={{ fontSize: 13 }}>
            {result.filename || "Untitled document"}
          </h2>
          <span className="pill">
            {result.page
              ? `Page ${result.page}`
              : `Chunk ${result.chunk_position + 1}`}
          </span>
        </div>
        <span className="pill ready">
          {result.score_type.replaceAll("_", " ")} · {result.score.toFixed(5)}
        </span>
      </div>
      <p>{result.content}</p>
      <div className="result-footer">
        <span>Retrieved by {result.sources.join(" + ")}</span>
        <div className="row wrap">
          {result.vector_distance !== null && (
            <span>Cosine distance {result.vector_distance.toFixed(4)}</span>
          )}
          {result.keyword_score !== null && (
            <span>Keyword rank {result.keyword_score.toFixed(4)}</span>
          )}
          {result.rrf_score !== null && (
            <span>RRF {result.rrf_score.toFixed(5)}</span>
          )}
        </div>
      </div>
      <details style={{ marginTop: 12, fontSize: 10, color: "var(--muted)" }}>
        <summary style={{ cursor: "pointer" }}>
          Source identifiers & provenance
        </summary>
        <div className="stack" style={{ gap: 5, marginTop: 10 }}>
          <code>Document {result.document_id}</code>
          <code>Chunk {result.chunk_id}</code>
          <span>
            Offsets {result.start_offset ?? "—"} – {result.end_offset ?? "—"} ·
            vector rank {result.vector_rank ?? "—"} · keyword rank{" "}
            {result.keyword_rank ?? "—"}
          </span>
          {result.rerank_score !== null && (
            <span>Reranker score {result.rerank_score}</span>
          )}
        </div>
      </details>
    </article>
  );
}
export function Playground() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [topK, setTopK] = useState(5);
  const [rerank, setRerank] = useState(false);
  const [validation, setValidation] = useState("");
  const capabilities = useQuery({
    queryKey: ["capabilities"],
    queryFn: () => api("capabilities", capabilitiesSchema),
  });
  const mutation = useMutation({
    mutationFn: async () => {
      const input = searchInputSchema.parse({
        query,
        mode,
        top_k: topK,
        rerank: rerank && !!capabilities.data?.reranking_available,
      });
      const start = performance.now();
      const response = await api("search", searchSchema, {
        method: "POST",
        body: JSON.stringify(input),
      });
      return { response, elapsed: performance.now() - start };
    },
  });
  return (
    <>
      <ProviderNotice />
      <PageHeading
        eyebrow="Understand what gets retrieved"
        title="Retrieval playground"
        description="Explore the passages, compare search modes, inspect the scores."
      />
      <div className="stack">
        <form
          className="card search-controls"
          onSubmit={(e) => {
            e.preventDefault();
            setValidation("");
            if (
              !searchInputSchema.safeParse({ query, mode, top_k: topK, rerank })
                .success
            ) {
              setValidation(
                "Enter a query of 1–1,000 characters and a top K between 1 and 50.",
              );
              return;
            }
            mutation.mutate();
          }}
        >
          <div className="search-field">
            <div className="input-wrap">
              <Search size={16} />
              <input
                className="input"
                aria-label="Search query"
                placeholder="Search your knowledge, naturally…"
                value={query}
                maxLength={1000}
                required
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Search size={14} />
              )}
              Search knowledge
            </Button>
          </div>
          <div className="search-options">
            <div className="segmented" role="group" aria-label="Search mode">
              {(["vector", "keyword", "hybrid"] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  aria-pressed={mode === v}
                  onClick={() => setMode(v)}
                >
                  {v[0].toUpperCase() + v.slice(1)}
                </button>
              ))}
            </div>
            <div className="row">
              <label htmlFor="top-k" className="muted">
                Top K
              </label>
              <input
                className="input"
                style={{ width: 66, minHeight: 34, padding: "6px 9px" }}
                type="number"
                id="top-k"
                min={1}
                max={50}
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
              />
            </div>
            <label
              className="row muted"
              title={
                capabilities.data?.reranking_available
                  ? "Use configured managed reranker"
                  : "Managed reranking is not configured"
              }
            >
              <input
                type="checkbox"
                checked={rerank}
                disabled={!capabilities.data?.reranking_available}
                onChange={(e) => setRerank(e.target.checked)}
              />
              Rerank
              {!capabilities.data?.reranking_available && (
                <span className="pill">Not configured</span>
              )}
            </label>
          </div>
          {validation && (
            <p
              role="alert"
              className="small"
              style={{ color: "var(--danger)", marginTop: 12 }}
            >
              {validation}
            </p>
          )}
        </form>
        <div className="quiet-note">
          <Info size={13} />
          <span>
            Hybrid uses Reciprocal Rank Fusion. Cosine, keyword, RRF and
            reranker scores have different meanings; none is a calibrated
            probability. Keyword matching uses English and simple PostgreSQL
            tokenization.
          </span>
        </div>
        {mutation.isError ? (
          <ErrorState error={mutation.error} />
        ) : mutation.isPending ? (
          <div className="card">
            <EmptyState
              icon={Loader2}
              title="Looking for relevant passages…"
              description="Searching only the documents authorized for this workspace."
            />
          </div>
        ) : mutation.data ? (
          <>
            <div className="between wrap">
              <div className="row">
                <h2 style={{ fontSize: 13 }}>
                  {mutation.data.response.results.length} retrieved passages
                </h2>
                <span className="pill">{mutation.data.response.mode}</span>
              </div>
              <span className="row muted small">
                <Clock3 size={12} />
                {mutation.data.elapsed.toFixed(0)} ms end-to-end · includes
                proxy/network
              </span>
            </div>
            {mutation.data.response.warnings.map((w, i) => (
              <div className="notice" key={i}>
                <Info size={14} />
                {w}
              </div>
            ))}
            <p className="muted small">
              Reranking: {mutation.data.response.reranking_status} · vector
              strategy: {mutation.data.response.vector_strategy || "not used"}
              {mutation.data.response.rrf_k !== null
                ? ` · RRF k=${mutation.data.response.rrf_k}`
                : ""}
            </p>
            {mutation.data.response.results.length ? (
              mutation.data.response.results.map((r) => (
                <SearchResultCard key={r.chunk_id} result={r} />
              ))
            ) : (
              <div className="card">
                <EmptyState
                  icon={Search}
                  title="No matching passages"
                  description="Try different wording, use keyword mode for identifiers, or add relevant source documents."
                />
              </div>
            )}
          </>
        ) : (
          <div className="card">
            <EmptyState
              icon={SlidersHorizontal}
              title="Make retrieval visible"
              description="Run a query to see the exact passages and ranking evidence your answer service would use."
            />
          </div>
        )}
      </div>
    </>
  );
}
