"use client";
import Link from "next/link";
import { useState, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  FileText,
  Layers3,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  documentListSchema,
  statsSchema,
  type DocumentRecord,
} from "@/lib/contracts";
import { PageHeading, StatCard, ErrorState, LoadingSkeleton } from "./common";
import { Button } from "./ui/button";
import { DocumentInspector, DocumentTable } from "./documents";
export function Dashboard() {
  const [selected, setSelected] = useState<DocumentRecord | null>(null);
  const stats = useQuery({
    queryKey: ["stats"],
    queryFn: () => api("documents/stats", statsSchema),
  });
  const documents = useQuery({
    queryKey: ["documents", "recent"],
    queryFn: () => api("documents?limit=5&offset=0", documentListSchema),
  });
  const total = stats.data?.documents ?? 0;
  const ready = stats.data?.ready ?? 0;
  const failed = stats.data?.failed ?? 0;
  const progress = total ? Math.round((ready / total) * 100) : 0;
  return (
    <>
      <PageHeading
        eyebrow="Workspace / Overview"
        title="Knowledge overview"
        description="A clear view of your documents, answers, and evidence."
        action={
          <Button asChild>
            <Link href="/knowledge">
              <Plus size={15} />
              Add knowledge
            </Link>
          </Button>
        }
      />
      <div className="stack dashboard-stack">
        {stats.isError && (
          <ErrorState error={stats.error} retry={() => stats.refetch()} />
        )}
        <section className="stats-grid" aria-label="Workspace totals">
          <StatCard
            label="Documents"
            value={stats.data?.documents ?? "—"}
            caption="In your knowledge base"
            icon={FileText}
          />
          <StatCard
            label="Stored chunks"
            value={stats.data?.chunks ?? "—"}
            caption="Searchable passages"
            icon={Layers3}
          />
          <StatCard
            label="Ready to search"
            value={stats.data?.ready ?? "—"}
            caption="Indexed and available"
            icon={CheckCircle2}
          />
          <StatCard
            label="Needs attention"
            value={stats.data?.failed ?? "—"}
            caption="Failed ingestion attempts"
            icon={ShieldCheck}
          />
        </section>
        <div className="overview-middle">
          <section className="card hero">
            <div className="hero-main">
              <span className="hero-label">
                <span className="dot" /> YOUR KNOWLEDGE, CONNECTED
              </span>
              <h2>
                Less searching.
                <br />
                More understanding.
              </h2>
              <p>
                Turn the information you already have into answers you can
                trace. Your next insight starts with a question.
              </p>
              <div className="row wrap">
                <Button asChild>
                  <Link href="/assistant">
                    <Sparkles size={16} />
                    Ask your knowledge
                    <ArrowUpRight size={16} />
                  </Link>
                </Button>
                <Link className="hero-secondary" href="/playground">
                  Explore retrieval
                  <ArrowRight size={14} />
                </Link>
              </div>
              <div className="hero-footnote">
                <ShieldCheck size={14} /> Answers grounded in your sources
              </div>
            </div>
            <div className="hero-art" aria-hidden="true">
              <div className="orbit orbit-one" />
              <div className="orbit orbit-two" />
              <div className="orbit orbit-three" />
              <div className="art-file">
                <FileText size={27} />
                <i />
                <i />
                <i />
              </div>
              <div className="art-spark">
                <Sparkles size={22} />
              </div>
            </div>
          </section>
          <section className="card index-health">
            <div className="between">
              <h2>Index health</h2>
              <Layers3 size={18} className="muted" />
            </div>
            <div
              className="index-ring"
              style={{ "--progress": `${progress}%` } as CSSProperties}
              role="img"
              aria-label={
                stats.data
                  ? `${ready} of ${total} documents ready`
                  : "Index health unavailable"
              }
            >
              <div>
                <strong>{stats.data ? `${progress}%` : "—"}</strong>
                <span>documents ready</span>
              </div>
            </div>
            <div className="health-legend">
              <span>
                <i className="legend-ready" />
                Ready<strong>{stats.data ? ready : "—"}</strong>
              </span>
              <span>
                <i className="legend-failed" />
                Failed<strong>{stats.data ? failed : "—"}</strong>
              </span>
              <span>
                <i className="legend-pending" />
                Other
                <strong>{stats.data ? total - ready - failed : "—"}</strong>
              </span>
            </div>
          </section>
        </div>
        <div className="two-col dashboard-bottom">
          <section className="card">
            <div className="between section-header">
              <div>
                <h2>Recent documents</h2>
                <p>Your latest additions to the knowledge base</p>
              </div>
              <Link className="link" href="/knowledge">
                View all
                <ArrowRight size={12} />
              </Link>
            </div>
            {documents.isPending ? (
              <LoadingSkeleton />
            ) : documents.isError ? (
              <div className="card-pad">
                <ErrorState
                  error={documents.error}
                  retry={() => documents.refetch()}
                />
              </div>
            ) : (
              <DocumentTable
                items={documents.data.items}
                onInspect={setSelected}
              />
            )}
          </section>
          <section className="card">
            <div className="section-header">
              <h2>Make your next move</h2>
              <p>A shorter path from question to clarity</p>
            </div>
            {[
              {
                href: "/knowledge",
                icon: BookOpen,
                title: "Build your knowledge base",
                description: "Upload and manage source documents",
              },
              {
                href: "/playground",
                icon: Search,
                title: "Look under the hood",
                description: "Inspect retrieval scores and passages",
              },
              {
                href: "/evaluation",
                icon: CheckCircle2,
                title: "Measure what matters",
                description: "Review actual benchmark evidence",
              },
            ].map(({ href, icon: Icon, title, description }) => (
              <Link className="action-item" href={href} key={href}>
                <Icon />
                <div className="spacer">
                  <strong>{title}</strong>
                  <p>{description}</p>
                </div>
                <ArrowUpRight size={13} />
              </Link>
            ))}
          </section>
        </div>
        <p className="quiet-note">
          <ShieldCheck size={13} />
          Totals and recent uploads come directly from your tenant-scoped
          database. No generated activity or estimated metrics.
        </p>
      </div>
      <DocumentInspector
        document={selected}
        onClose={() => setSelected(null)}
      />
    </>
  );
}
