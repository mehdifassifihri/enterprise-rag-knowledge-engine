"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  CheckCircle2,
  Crosshair,
  FlaskConical,
  Info,
  Target,
  TrendingUp,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { evaluationSchema, type Evaluation } from "@/lib/contracts";
import { formatDate } from "@/lib/utils";
import {
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  PageHeading,
  StatCard,
} from "./common";
export function EvaluationChart({
  strategies,
}: {
  strategies: Evaluation["strategies"];
}) {
  const data = strategies
    .filter((s) => s.status === "completed")
    .flatMap((s) =>
      s.points.map((p) => ({
        label: `${s.name} @${p.k}`,
        Recall: p.recall,
        MRR: p.mrr,
        nDCG: p.ndcg,
        "Hit rate": p.hit_rate,
      })),
    );
  if (!data.length)
    return (
      <EmptyState
        icon={BarChart3}
        title="No measured strategies"
        description="Pending runs are not plotted as zero scores."
      />
    );
  return (
    <div
      className="chart-container"
      role="img"
      aria-label="Measured retrieval quality by strategy and cutoff; exact values are available in the table below"
    >
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <BarChart
          data={data}
          margin={{ top: 8, right: 0, left: -25, bottom: 0 }}
          barGap={3}
        >
          <CartesianGrid
            vertical={false}
            stroke="var(--border)"
            strokeDasharray="3 4"
          />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10, fill: "var(--muted)" }}
            tickLine={false}
            axisLine={false}
            dy={8}
          />
          <YAxis
            domain={[0, 1]}
            tick={{ fontSize: 10, fill: "var(--muted)" }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              fontSize: 11,
              color: "var(--foreground)",
            }}
            cursor={{ fill: "var(--subtle)" }}
          />
          {[
            ["Recall", "#ed5528"],
            ["MRR", "#eca886"],
            ["nDCG", "#53797a"],
            ["Hit rate", "#b7c4cc"],
          ].map(([key, color]) => (
            <Bar
              key={key}
              dataKey={key}
              fill={color}
              radius={[8, 8, 0, 0]}
              maxBarSize={32}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
export function EvaluationLab() {
  const [category, setCategory] = useState("all");
  const report = useQuery({
    queryKey: ["evaluation"],
    queryFn: () => api("evaluation", evaluationSchema),
    staleTime: 60000,
  });
  const measured = report.data?.strategies.find(
    (s) => s.status === "completed",
  );
  const point = measured?.points.find((p) => p.k === 5);
  const metric = (n: number | null | undefined) =>
    n == null ? "—" : n.toFixed(4);
  return (
    <>
      <PageHeading
        eyebrow="Evidence over intuition"
        title="Evaluation lab"
        description="Measured retrieval quality. Honest about what’s still unmeasured."
        action={
          <span className="pill">
            <FlaskConical size={12} />
            Reviewed synthetic benchmark
          </span>
        }
      />
      {report.isPending ? (
        <LoadingSkeleton />
      ) : report.isError ? (
        <ErrorState error={report.error} retry={() => report.refetch()} />
      ) : !report.data.available ? (
        <div className="card">
          <EmptyState
            icon={FlaskConical}
            title="No evaluation results yet"
            description="Run the evaluation CLI, review its synthetic artifacts and configure EVALUATION_REPORT_DIR on the frontend server."
          />
          <pre style={{ margin: 20 }}>
            .venv/bin/python -m enterprise_knowledge_engine.evaluation.runner
            --strategies keyword
          </pre>
        </div>
      ) : (
        <div className="stack">
          <div className="notice">
            <Info size={16} />
            <span>
              Real keyword measurements are available. Vector, hybrid and actual
              reranking quality remain pending; fixture providers are never used
              as semantic benchmark evidence.
            </span>
          </div>
          <section className="stats-grid">
            <StatCard
              label={`Recall@5 · ${measured?.name || "unavailable"}`}
              value={metric(point?.recall)}
              caption={`${point?.denominator ?? 0} eligible positive questions`}
              icon={Target}
            />
            <StatCard
              label="MRR@5"
              value={metric(point?.mrr)}
              caption="Reciprocal rank within cutoff"
              icon={TrendingUp}
            />
            <StatCard
              label="nDCG@5"
              value={metric(point?.ndcg)}
              caption="Graded relevance, discounted by rank"
              icon={Crosshair}
            />
            <StatCard
              label="Hit rate@5"
              value={metric(point?.hit_rate)}
              caption="Queries with a relevant result"
              icon={CheckCircle2}
            />
          </section>
          <section className="card card-pad">
            <div className="between wrap">
              <div>
                <h2>Quality across retrieval cutoffs</h2>
                <p className="muted small" style={{ marginTop: 5 }}>
                  Macro averages over positive questions · higher is better
                </p>
              </div>
              <div className="chart-legend">
                {[
                  ["Recall", "#ed5528"],
                  ["MRR", "#eca886"],
                  ["nDCG", "#53797a"],
                  ["Hit rate", "#b7c4cc"],
                ].map(([label, color]) => (
                  <span className="row" key={label}>
                    <span className="dot" style={{ background: color }} />
                    {label}
                  </span>
                ))}
              </div>
            </div>
            <EvaluationChart strategies={report.data.strategies} />
          </section>
          <section className="card">
            <div className="section-header">
              <h2>Strategy comparison</h2>
              <p>
                Pending is not zero. External model runs have not been
                performed.
              </p>
            </div>
            <div className="table-scroll">
              <table className="metric-table">
                <thead>
                  <tr>
                    <th>Strategy</th>
                    <th>State</th>
                    <th>K</th>
                    <th>Recall</th>
                    <th>MRR</th>
                    <th>nDCG</th>
                    <th>Hit rate</th>
                    <th>Service p95</th>
                  </tr>
                </thead>
                <tbody>
                  {report.data.strategies.flatMap((s) =>
                    s.points.length
                      ? s.points.map((p) => (
                          <tr key={`${s.name}-${p.k}`}>
                            <td>{s.name}</td>
                            <td>
                              <span className="pill ready">Measured</span>
                            </td>
                            <td>{p.k}</td>
                            <td>{metric(p.recall)}</td>
                            <td>{metric(p.mrr)}</td>
                            <td>{metric(p.ndcg)}</td>
                            <td>{metric(p.hit_rate)}</td>
                            <td>{s.latency_p95_ms?.toFixed(2) ?? "—"} ms</td>
                          </tr>
                        ))
                      : [
                          <tr key={s.name}>
                            <td>{s.name}</td>
                            <td>
                              <span className="pill" title={s.reason}>
                                {s.status}
                              </span>
                            </td>
                            <td colSpan={6} className="muted">
                              {s.reason || "No measured results"}
                            </td>
                          </tr>,
                        ],
                  )}
                </tbody>
              </table>
            </div>
          </section>
          <div className="two-col">
            <section className="card card-pad">
              <h2 className="section-title">Dataset & experiment conditions</h2>
              <dl className="metadata">
                <dt>Version</dt>
                <dd>{report.data.dataset_version}</dd>
                <dt>Questions</dt>
                <dd>{report.data.question_count}</dd>
                <dt>Measured on</dt>
                <dd>
                  {report.data.run_at
                    ? formatDate(report.data.run_at)
                    : "Unavailable"}
                </dd>
                <dt>Fingerprint</dt>
                <dd>
                  <code>{report.data.dataset_sha256}</code>
                </dd>
              </dl>
              <p className="quiet-note">{report.data.conditions}</p>
            </section>
            <section className="card card-pad">
              <h2 className="section-title">Read the results critically</h2>
              <p className="muted small" style={{ lineHeight: 1.9 }}>
                The keyword baseline has limited natural-language recall.
                Conjunctive full-text queries can miss paraphrases. These
                measurements do not demonstrate that hybrid search is better.
              </p>
              <p
                className="muted small"
                style={{ lineHeight: 1.9, marginTop: 12 }}
              >
                Latency is a tiny local serial service measurement, excluding
                indexing. It is not production capacity, browser latency or
                model inference timing. Real provider charges have not been
                measured.
              </p>
            </section>
          </div>
          <section className="card">
            <div className="between section-header wrap">
              <div>
                <h2>Per-question evidence</h2>
                <p>Actual ranked document labels from the reviewed run</p>
              </div>
              <select
                className="input"
                style={{ width: 180 }}
                aria-label="Filter question category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                <option value="all">All categories</option>
                {[...new Set(report.data.questions.map((q) => q.category))].map(
                  (c) => (
                    <option key={c}>{c}</option>
                  ),
                )}
              </select>
            </div>
            <div className="table-scroll" style={{ maxHeight: 400 }}>
              <table>
                <thead>
                  <tr>
                    <th>Question</th>
                    <th>Category</th>
                    <th>Retrieved labels</th>
                    <th>Relevant labels</th>
                    <th>Latency</th>
                  </tr>
                </thead>
                <tbody>
                  {report.data.questions
                    .filter(
                      (q) => category === "all" || q.category === category,
                    )
                    .map((q) => (
                      <tr key={`${q.strategy}-${q.id}`}>
                        <td>{q.id}</td>
                        <td className="muted">
                          {q.category.replaceAll("_", " ")}
                        </td>
                        <td>
                          {q.error ||
                            q.ranked_labels.join(", ") ||
                            "No results"}
                        </td>
                        <td className="muted">
                          {q.relevant_labels.join(", ") || "None expected"}
                        </td>
                        <td className="muted">
                          {q.latency_ms?.toFixed(2) ?? "—"} ms
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </>
  );
}
