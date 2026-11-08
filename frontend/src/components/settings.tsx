"use client";
import { useQuery } from "@tanstack/react-query";
import {
  Cable,
  CheckCircle2,
  CircleHelp,
  Info,
  LockKeyhole,
  Server,
  ShieldCheck,
  TerminalSquare,
} from "lucide-react";
import { z } from "zod";
import { api } from "@/lib/api";
import { capabilitiesSchema } from "@/lib/contracts";
import { ErrorState, LoadingSkeleton, PageHeading } from "./common";
export function SettingsPage() {
  const capability = useQuery({
    queryKey: ["capabilities"],
    queryFn: () => api("capabilities", capabilitiesSchema),
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api("ready", z.object({ status: z.string() })),
    retry: false,
  });
  const c = capability.data;
  return (
    <>
      <PageHeading
        eyebrow="Connected, with clear boundaries"
        title="Settings & integrations"
        description="Inspect your connection and learn how the workspace is configured."
      />
      <div className="stack">
        <div className="notice">
          <LockKeyhole size={15} />
          <span>
            Configuration is managed on the server. This page never displays API
            keys, database URLs or private environment values.
          </span>
        </div>
        {capability.isError && (
          <ErrorState
            error={capability.error}
            retry={() => capability.refetch()}
          />
        )}
        <div className="settings-grid">
          <section className="card card-pad">
            <div className="row section-title">
              <Server size={17} className="text-primary" />
              <h2>Backend connection</h2>
            </div>
            <div className="settings-item">
              <span>Readiness</span>
              <span className={`pill ${health.isSuccess ? "ready" : ""}`}>
                <span className="dot" />
                {health.isPending
                  ? "Checking"
                  : health.isSuccess
                    ? "Ready"
                    : "Unavailable"}
              </span>
            </div>
            <div className="settings-item">
              <span>Authentication</span>
              <span>Server-side tenant key</span>
            </div>
            <div className="settings-item">
              <span>Frontend session</span>
              <span>HTTP-only · 8 hours</span>
            </div>
            <div className="settings-item">
              <span>Tenant selection</span>
              <span>Server controlled</span>
            </div>
            <p className="quiet-note" style={{ marginTop: 18 }}>
              <Info size={12} />
              Readiness checks PostgreSQL, pgvector and migrations. It does not
              probe or charge external providers.
            </p>
          </section>
          <section className="card card-pad">
            <div className="row section-title">
              <CheckCircle2 size={17} className="text-primary" />
              <h2>Provider configuration</h2>
            </div>
            {capability.isPending ? (
              <LoadingSkeleton />
            ) : (
              <>
                <div className="settings-item">
                  <span>Embeddings</span>
                  <span>{c?.embedding_provider || "Unavailable"}</span>
                </div>
                <div className="settings-item">
                  <span>Embedding model</span>
                  <span>{c?.embedding_model || "Unavailable"}</span>
                </div>
                <div className="settings-item">
                  <span>Vector dimensions</span>
                  <span>{c?.embedding_dimensions ?? "—"}</span>
                </div>
                <div className="settings-item">
                  <span>Answer provider</span>
                  <span>
                    {c?.llm_provider || "Unavailable"} · {c?.llm_model || "—"}
                  </span>
                </div>
                <div className="settings-item">
                  <span>Credentials configured</span>
                  <span>
                    {c
                      ? `Embeddings: ${c.embeddings_configured ? "yes" : "no"} · Chat: ${c.llm_configured ? "yes" : "no"}`
                      : "Unavailable"}
                  </span>
                </div>
                <div className="settings-item">
                  <span>Managed reranking</span>
                  <span>
                    {c?.reranking_available ? "Configured" : "Not configured"}
                  </span>
                </div>
              </>
            )}
            <p className="quiet-note" style={{ marginTop: 18 }}>
              <CircleHelp size={12} />
              Configured does not mean live connectivity or quality is verified.
              Fake providers do not provide semantic retrieval or real generated
              answers.
            </p>
          </section>
          <section className="card card-pad">
            <div className="row section-title">
              <Cable size={17} className="text-primary" />
              <h2>MCP integration</h2>
            </div>
            <p className="muted small" style={{ lineHeight: 1.9 }}>
              The local stdio MCP server exposes the same tenant-scoped
              knowledge services to trusted AI clients. It does not run inside
              the browser or expose a remote MCP endpoint.
            </p>
            <pre>
              {
                "# From the repository root; configure MCP_API_KEY in ignored .env\nmake mcp\n\n# Controlled fixture demo, real official-SDK subprocess\nmake demo-mcp"
              }
            </pre>
            <div className="row wrap">
              {[
                "search_knowledge",
                "ask_knowledge",
                "list_documents",
                "get_document",
                "get_document_chunks",
              ].map((t) => (
                <code className="pill" key={t}>
                  {t}
                </code>
              ))}
            </div>
          </section>
          <section className="card card-pad">
            <div className="row section-title">
              <TerminalSquare size={17} className="text-primary" />
              <h2>Local development</h2>
            </div>
            <p className="muted small">
              See docs/FRONTEND.md for environment setup and demo modes.
            </p>
            <pre>
              {
                "# Repository root: configured .env + provisioned tenant\nmake db-up && make migrate && make run\n\n# Separate terminal\ncd frontend\nnpm ci\n# Configure ignored .env.local from .env.example\nnpm run dev"
              }
            </pre>
            <p className="quiet-note">
              <ShieldCheck size={12} />
              This shared demo is not a multi-user SaaS identity system.
              Production requires user authentication, tenant-bound sessions,
              authorization and admission controls.
            </p>
          </section>
        </div>
      </div>
    </>
  );
}
