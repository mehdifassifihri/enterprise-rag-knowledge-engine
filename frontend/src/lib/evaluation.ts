import "server-only";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { z } from "zod";
import { evaluationSchema, type Evaluation } from "./contracts";
const metric = z.object({
  value: z.number().nullable(),
  denominator: z.number(),
});
const reportSchema = z.object({
  dataset_version: z.string(),
  dataset_sha256: z.string(),
  question_count: z.number(),
  run_finished_at: z.string(),
  strategies: z.record(
    z.string(),
    z.object({ status: z.string(), reason: z.string().optional() }),
  ),
  metrics: z.record(
    z.string(),
    z.object({
      overall: z.object({
        at_k: z.record(
          z.string(),
          z.object({
            recall: metric,
            mrr: metric,
            ndcg: metric,
            hit_rate: metric,
          }),
        ),
      }),
    }),
  ),
  latency: z.record(z.string(), z.object({ p95_ms: z.number() })),
});
const questionSchema = z.object({
  question_id: z.string(),
  category: z.string(),
  strategy: z.string(),
  ranked_labels: z.array(z.string()),
  relevance: z.record(z.string(), z.number()),
  latency_ms: z.number().nullable(),
  error: z.string().nullable(),
});
export async function readEvaluation(): Promise<Evaluation> {
  const root = path.resolve(
    process.env.EVALUATION_REPORT_DIR || "../evaluation/reports/local-keyword",
  );
  try {
    const report = reportSchema.parse(
      JSON.parse(await readFile(path.join(root, "metrics.json"), "utf8")),
    );
    const raw = await readFile(path.join(root, "per_question.jsonl"), "utf8");
    const questions = raw
      .trim()
      .split("\n")
      .filter(Boolean)
      .slice(0, 1000)
      .map((line) => questionSchema.parse(JSON.parse(line)));
    return evaluationSchema.parse({
      available: true,
      dataset_version: report.dataset_version,
      dataset_sha256: report.dataset_sha256,
      question_count: report.question_count,
      run_at: report.run_finished_at,
      conditions: `${report.question_count} recorded questions · document-level ranking · positive-query macro averages · indexing excluded`,
      strategies: Object.entries(report.strategies).map(([name, s]) => ({
        name,
        ...s,
        points: Object.entries(report.metrics[name]?.overall.at_k || {}).map(
          ([k, p]) => ({
            k: Number(k),
            recall: p.recall.value,
            mrr: p.mrr.value,
            ndcg: p.ndcg.value,
            hit_rate: p.hit_rate.value,
            denominator: p.recall.denominator,
          }),
        ),
        latency_p95_ms: report.latency[name]?.p95_ms ?? null,
      })),
      questions: questions.map((q) => ({
        id: q.question_id,
        category: q.category,
        strategy: q.strategy,
        ranked_labels: q.ranked_labels,
        relevant_labels: Object.keys(q.relevance),
        latency_ms: q.latency_ms,
        error: q.error ? "Retrieval failed" : null,
      })),
    });
  } catch {
    return { available: false, strategies: [], questions: [] };
  }
}
