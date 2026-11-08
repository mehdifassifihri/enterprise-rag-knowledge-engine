import { z } from "zod";
const uuid = z.string().uuid();
const nullableNumber = z.number().nullable();
export const modeSchema = z.enum(["vector", "keyword", "hybrid"]);
export type SearchMode = z.infer<typeof modeSchema>;
export const documentSchema = z.object({
  id: uuid,
  title: z.string(),
  filename: z.string().nullable(),
  media_type: z.string().nullable(),
  size_bytes: z.number(),
  content_hash: z.string().nullable(),
  status: z.enum(["pending", "processing", "ready", "failed"]),
  chunk_count: z.number(),
  page_count: nullableNumber,
  extraction_metadata: z.record(z.string(), z.unknown()),
  embedding_model: z.string().nullable(),
  embedding_dimensions: nullableNumber,
  error_code: z.string().nullable(),
  created_at: z.string(),
  processed_at: z.string().nullable(),
});
export type DocumentRecord = z.infer<typeof documentSchema>;
export const documentListSchema = z.object({
  items: z.array(documentSchema),
  limit: z.number(),
  offset: z.number(),
});
export const statsSchema = z.object({
  documents: z.number(),
  ready: z.number(),
  failed: z.number(),
  chunks: z.number(),
});
export const chunkSchema = z.object({
  id: uuid,
  document_id: uuid,
  position: z.number(),
  content: z.string(),
  page_number: nullableNumber,
  start_offset: nullableNumber,
  end_offset: nullableNumber,
  truncated: z.boolean(),
});
export const chunksSchema = z.object({
  items: z.array(chunkSchema),
  limit: z.number(),
  offset: z.number(),
});
export const capabilitiesSchema = z.object({
  embedding_provider: z.string(),
  embedding_model: z.string(),
  embeddings_configured: z.boolean(),
  llm_provider: z.string(),
  llm_model: z.string(),
  llm_configured: z.boolean(),
  reranking_available: z.boolean(),
  max_upload_bytes: z.number(),
  embedding_dimensions: z.number(),
  mcp_transport: z.string(),
});
export const searchInputSchema = z
  .object({
    query: z.string().trim().min(1).max(1000),
    mode: modeSchema,
    top_k: z.number().int().min(1).max(50),
    rerank: z.boolean(),
  })
  .strict();
const historySchema = z
  .array(
    z
      .object({
        role: z.enum(["user", "assistant"]),
        content: z.string().trim().min(1).max(1000),
      })
      .strict(),
  )
  .max(6)
  .refine((v) => v.reduce((n, m) => n + m.content.length, 0) <= 4000);
export const askInputSchema = z
  .object({
    question: z.string().trim().min(1).max(1000),
    top_k: z.number().int().min(1).max(20).optional(),
    search_mode: modeSchema.optional(),
    rerank: z.boolean().optional(),
    history: historySchema.optional(),
  })
  .strict();
export const resultSchema = z.object({
  chunk_id: uuid,
  document_id: uuid,
  filename: z.string().nullable(),
  content: z.string(),
  page: nullableNumber,
  chunk_position: z.number(),
  start_offset: nullableNumber,
  end_offset: nullableNumber,
  rank: z.number(),
  score: z.number(),
  score_type: z.enum([
    "normalized_cosine",
    "keyword_rank",
    "rrf",
    "reranker_relevance",
  ]),
  retrieval_score: z.number(),
  sources: z.array(z.enum(["vector", "keyword"])),
  vector_rank: nullableNumber,
  keyword_rank: nullableNumber,
  vector_distance: nullableNumber,
  cosine_similarity: nullableNumber,
  normalized_similarity: nullableNumber,
  keyword_score: nullableNumber,
  rrf_score: nullableNumber,
  rerank_score: nullableNumber,
});
export type SearchResult = z.infer<typeof resultSchema>;
export const searchSchema = z.object({
  query: z.string(),
  mode: modeSchema,
  results: z.array(resultSchema),
  score_type: z.string(),
  rrf_k: nullableNumber,
  candidate_limit_per_source: z.number(),
  vector_strategy: z.string().nullable(),
  reranking_status: z.string(),
  reranker_model: z.string().nullable(),
  warnings: z.array(z.string()),
});
export type SearchResponse = z.infer<typeof searchSchema>;
export const citationSchema = z.object({
  source_id: z.string(),
  document_id: uuid,
  chunk_id: uuid,
  filename: z.string().nullable(),
  page: nullableNumber,
  chunk_position: z.number(),
  start_offset: nullableNumber,
  end_offset: nullableNumber,
  excerpt: z.string(),
  supporting_quotes: z.array(z.string()),
});
export type Citation = z.infer<typeof citationSchema>;
export const askSchema = z.object({
  question: z.string(),
  answer: z.string(),
  status: z.enum(["answered", "insufficient_evidence", "error"]),
  abstention_reason: z.string().nullable(),
  citations: z.array(citationSchema),
  retrieval: z.object({
    mode: modeSchema,
    top_k: z.number(),
    sources_retrieved: z.number(),
    sources_supplied: z.number(),
    sources_used: z.number(),
    context_characters: z.number(),
    reranking_status: z.string().nullable(),
    warnings: z.array(z.string()),
  }),
  model: z.string().nullable(),
  usage: z
    .object({
      input_tokens: z.number().nullable().optional(),
      output_tokens: z.number().nullable().optional(),
      total_tokens: z.number().nullable().optional(),
    })
    .nullable(),
  timings: z.object({ retrieval_ms: nullableNumber, model_ms: nullableNumber }),
  request_id: z.string().nullable(),
  error: z.object({ code: z.string(), message: z.string() }).nullable(),
});
export type AskResponse = z.infer<typeof askSchema>;
export const evaluationSchema = z.object({
  available: z.boolean(),
  dataset_version: z.string().optional(),
  dataset_sha256: z.string().optional(),
  question_count: z.number().optional(),
  conditions: z.string().optional(),
  run_at: z.string().optional(),
  strategies: z.array(
    z.object({
      name: z.string(),
      status: z.string(),
      reason: z.string().optional(),
      points: z.array(
        z.object({
          k: z.number(),
          recall: nullableNumber,
          mrr: nullableNumber,
          ndcg: nullableNumber,
          hit_rate: nullableNumber,
          denominator: z.number(),
        }),
      ),
      latency_p95_ms: nullableNumber,
    }),
  ),
  questions: z.array(
    z.object({
      id: z.string(),
      category: z.string(),
      strategy: z.string(),
      ranked_labels: z.array(z.string()),
      relevant_labels: z.array(z.string()),
      latency_ms: nullableNumber,
      error: z.string().nullable(),
    }),
  ),
});
export type Evaluation = z.infer<typeof evaluationSchema>;
