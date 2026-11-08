"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  CheckCheck,
  FileText,
  Info,
  Loader2,
  MessageSquare,
  Paperclip,
  Send,
  Search,
  PanelRightClose,
  PanelRightOpen,
  Layers3,
  RefreshCw,
  Plus,
  ShieldCheck,
  Sparkles,
  User,
} from "lucide-react";
import { ProviderNotice } from "./provider-notice";
import { api } from "@/lib/api";
import {
  askSchema,
  capabilitiesSchema,
  type AskResponse,
  type Citation,
} from "@/lib/contracts";
import { Button } from "./ui/button";
import { EmptyState, ErrorState } from "./common";
export function CitationBadge({
  citation,
  onClick,
}: {
  citation: Citation;
  onClick: () => void;
}) {
  return (
    <button
      className="citation-badge"
      aria-label={`View source ${citation.source_id}: ${citation.filename || "document"}`}
      onClick={onClick}
    >
      <FileText size={9} />
      {citation.source_id}
    </button>
  );
}
export function SourcePanel({
  citation,
  sources,
  onSelect,
}: {
  citation: Citation | null;
  sources: Citation[];
  onSelect: (c: Citation) => void;
}) {
  return (
    <aside className="card source-panel" aria-label="Source details">
      <div className="row">
        <BookOpen size={15} className="text-primary" />
        <h2 style={{ fontSize: 13 }}>Source explorer</h2>
      </div>
      {!citation ? (
        <EmptyState
          icon={FileText}
          title="Evidence lives here"
          description="Select a citation in an answer to inspect its source and supporting quote."
        />
      ) : (
        <>
          <div className="row" style={{ marginTop: 20 }}>
            <span className="pill ready">{citation.source_id}</span>
            <span className="small muted">Verified source identity</span>
          </div>
          <h3 className="source-title">
            {citation.filename || "Untitled document"}
          </h3>
          <p style={{ fontSize: 10, marginTop: 6 }}>
            Chunk {citation.chunk_position + 1}
            {citation.page ? ` · Page ${citation.page}` : ""}
          </p>
          {citation.supporting_quotes.map((quote, i) => (
            <blockquote className="source-quote" key={i}>
              {quote}
            </blockquote>
          ))}
          <dl
            className="metadata"
            style={{ gridTemplateColumns: "1fr", gap: 6, marginTop: 24 }}
          >
            <dt>Document ID</dt>
            <dd>
              <code>{citation.document_id}</code>
            </dd>
            <dt>Chunk ID</dt>
            <dd>
              <code>{citation.chunk_id}</code>
            </dd>
            <dt>Source offsets</dt>
            <dd>
              {citation.start_offset ?? "—"} – {citation.end_offset ?? "—"}
            </dd>
          </dl>
          <div className="quiet-note">
            <Info size={12} />
            <span>
              Source IDs and quotes are checked server-side. A matching quote
              does not by itself prove every claim.
            </span>
          </div>
        </>
      )}
      {sources.length > 1 && (
        <div
          style={{
            marginTop: 20,
            borderTop: "1px solid var(--border)",
            paddingTop: 14,
          }}
        >
          <span className="eyebrow">Sources in this answer</span>
          {sources.map((c) => (
            <button
              className="source-list-button"
              key={c.source_id}
              onClick={() => onSelect(c)}
            >
              <span className="pill">{c.source_id}</span>
              {c.filename}
            </button>
          ))}
        </div>
      )}
    </aside>
  );
}
export function ChatMessage({
  role,
  content,
  response,
  onCitation,
}: {
  role: "user" | "assistant";
  content: string;
  response?: AskResponse;
  onCitation: (c: Citation) => void;
}) {
  const parts = content.split(/(\[S[1-9][0-9]?\])/g);
  return (
    <article className={`chat-message ${role}`}>
      <div className="message-avatar">
        {role === "user" ? <User size={14} /> : <Sparkles size={14} />}
      </div>
      <div className="message-content">
        <div className="message-label">
          {role === "user" ? "You" : "Knowledge assistant"}
          {response?.status === "insufficient_evidence" && (
            <span className="pill" style={{ marginLeft: 9 }}>
              Insufficient evidence
            </span>
          )}
        </div>
        {parts.map((part, i) => {
          const c = response?.citations.find(
            (c) => part === `[${c.source_id}]`,
          );
          return c ? (
            <CitationBadge key={i} citation={c} onClick={() => onCitation(c)} />
          ) : (
            <span key={i}>{part}</span>
          );
        })}
        {response?.status === "insufficient_evidence" && (
          <p className="quiet-note" style={{ marginTop: 10 }}>
            The available sources do not support an answer. Try a more specific
            question or add relevant documents.
          </p>
        )}
        {response && (
          <div
            className="row wrap muted"
            style={{ fontSize: 10, marginTop: 12 }}
          >
            <span className="row">
              <CheckCheck size={12} />
              {response.retrieval.sources_used} cited sources
            </span>
            <span>· {response.retrieval.mode}</span>
            {response.timings.retrieval_ms !== null && (
              <span>
                · retrieval {response.timings.retrieval_ms.toFixed(0)} ms
              </span>
            )}
            {response.timings.model_ms !== null && (
              <span>· model {response.timings.model_ms.toFixed(0)} ms</span>
            )}
            {response.usage?.total_tokens != null && (
              <span>· {response.usage.total_tokens} tokens</span>
            )}
          </div>
        )}
        {response?.retrieval.warnings.map((w, i) => (
          <p className="quiet-note" key={i}>
            {w}
          </p>
        ))}
      </div>
    </article>
  );
}
function KnowledgeCompanion() {
  return (
    <div className="companion-scene" aria-hidden="true">
      <div className="companion-bubble bubble-left">
        <BookOpen size={16} /> Find the right passage.
      </div>
      <svg className="companion-bot" viewBox="0 0 180 180" fill="none">
        <defs>
          <linearGradient
            id="bot-shell"
            x1="60"
            y1="30"
            x2="135"
            y2="160"
            gradientUnits="userSpaceOnUse"
          >
            <stop stopColor="var(--companion-shell)" />
            <stop offset="1" stopColor="var(--companion-shade)" />
          </linearGradient>
          <linearGradient
            id="bot-body"
            x1="65"
            y1="95"
            x2="130"
            y2="166"
            gradientUnits="userSpaceOnUse"
          >
            <stop stopColor="var(--companion-shell)" />
            <stop offset="1" stopColor="var(--companion-shade)" />
          </linearGradient>
        </defs>
        <ellipse
          cx="91"
          cy="166"
          rx="43"
          ry="7"
          fill="var(--companion-detail)"
          opacity=".1"
        />
        <path
          d="M59 101C42 103 30 134 37 141C44 146 61 130 67 118"
          fill="var(--companion-limb)"
        />
        <path
          d="M122 101C139 103 150 134 143 141C136 146 119 130 113 118"
          fill="var(--companion-limb)"
        />
        <path
          d="M61 101C61 85 121 85 121 101L116 136C114 149 102 159 91 160C78 159 66 149 65 136L61 101Z"
          fill="url(#bot-body)"
        />
        <rect
          x="48"
          y="45"
          width="18"
          height="30"
          rx="8"
          fill="var(--companion-limb)"
        />
        <rect
          x="116"
          y="45"
          width="18"
          height="30"
          rx="8"
          fill="var(--companion-limb)"
        />
        <rect
          x="59"
          y="34"
          width="65"
          height="57"
          rx="17"
          fill="url(#bot-shell)"
        />
        <rect
          x="66"
          y="41"
          width="51"
          height="40"
          rx="11"
          fill="var(--companion-face)"
        />
        <path
          d="M77 61Q81 55 85 61M99 61Q103 55 107 61"
          stroke="#fff"
          strokeWidth="4"
          strokeLinecap="round"
        />
        <circle cx="80" cy="116" r="3" fill="var(--companion-detail)" />
        <circle cx="91" cy="116" r="3" fill="var(--companion-detail)" />
        <circle cx="102" cy="116" r="3" fill="var(--companion-detail)" />
        <rect
          x="82"
          y="135"
          width="19"
          height="5"
          rx="2.5"
          fill="var(--companion-detail)"
        />
        <path d="M92 34V24" stroke="var(--primary)" strokeWidth="3" />
        <circle cx="92" cy="21" r="5" fill="var(--primary)" />
      </svg>
      <div className="companion-bubble bubble-right">
        <Sparkles size={16} /> Bring your knowledge to life.
      </div>
    </div>
  );
}
type Turn = { question: string; response: AskResponse };
export function Assistant() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [withHistory, setWithHistory] = useState(true);
  const [showSources, setShowSources] = useState(false);
  const capabilities = useQuery({
    queryKey: ["capabilities"],
    queryFn: () => api("capabilities", capabilitiesSchema),
  });
  const composer = useRef<HTMLTextAreaElement>(null);
  const [selected, setSelected] = useState<Citation | null>(null);
  const [sources, setSources] = useState<Citation[]>([]);
  const bottom = useRef<HTMLDivElement>(null);
  const mutation = useMutation({
    mutationFn: async (text: string) => {
      let used = 0;
      const history = withHistory
        ? turns
            .flatMap((t) => [
              { role: "user" as const, content: t.question.slice(0, 1000) },
              {
                role: "assistant" as const,
                content: t.response.answer.slice(0, 1000),
              },
            ])
            .slice(-6)
            .reverse()
            .filter((m) => {
              if (!m.content.trim() || used + m.content.length > 4000)
                return false;
              used += m.content.length;
              return true;
            })
            .reverse()
        : [];
      return api("ask", askSchema, {
        method: "POST",
        body: JSON.stringify({
          question: text,
          top_k: 5,
          search_mode: "hybrid",
          rerank: false,
          history,
        }),
      });
    },
    onSuccess: (response, text) => {
      setTurns((prev) => [...prev, { question: text, response }]);
      setQuestion("");
      setSources(response.citations);
      setSelected(response.citations[0] || null);
      setShowSources(response.citations.length > 0);
    },
  });
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [turns, mutation.isPending]);
  function submit(text = question) {
    if (text.trim() && !mutation.isPending) mutation.mutate(text.trim());
  }
  return (
    <div
      className={`assistant-studio ${turns.length || mutation.isPending ? "has-conversation" : ""}`}
    >
      <ProviderNotice />
      <div className="studio-topbar">
        <span
          className="studio-model"
          title="Configured server-side model; model selection is managed by the operator"
        >
          <span className="studio-mini-bot">
            <Sparkles size={15} />
          </span>
          {capabilities.data?.llm_model || "Knowledge assistant"}
          <span className="studio-model-tag">Grounded</span>
        </span>
        <h1>AI knowledge assistant</h1>
        <div className="row">
          <Button
            className="studio-sources-toggle"
            variant="ghost"
            size="icon"
            aria-label={showSources ? "Hide source panel" : "Show source panel"}
            aria-expanded={showSources}
            onClick={() => setShowSources((v) => !v)}
          >
            {showSources ? (
              <PanelRightClose size={18} />
            ) : (
              <PanelRightOpen size={18} />
            )}
          </Button>
          <Button
            className="studio-new-chat"
            variant="outline"
            disabled={mutation.isPending}
            onClick={() => {
              setTurns([]);
              setSources([]);
              setSelected(null);
              setShowSources(false);
              setQuestion("");
              mutation.reset();
              composer.current?.focus();
            }}
          >
            <Plus size={15} />
            <span>New conversation</span>
          </Button>
        </div>
      </div>
      <div className={`studio-layout ${showSources ? "with-sources" : ""}`}>
        <section
          className="studio-conversation"
          aria-label="Knowledge conversation"
        >
          <div
            className="studio-messages"
            role="log"
            aria-label="Conversation messages"
            aria-busy={mutation.isPending}
          >
            {!turns.length && !mutation.isPending ? (
              <div className="studio-welcome">
                <span className="studio-kicker">
                  <span className="dot" /> YOUR KNOWLEDGE COMPANION
                </span>
                <h2>
                  <span>A little curiosity.</span>
                  <br />A world of understanding.
                </h2>
                <p>
                  Ask your documents a question.
                  <br className="studio-mobile-break" /> Get answers you can
                  trace back to the source.
                </p>
                <KnowledgeCompanion />
              </div>
            ) : (
              turns.map((turn, i) => (
                <div className="stack studio-turn" key={i}>
                  <ChatMessage
                    role="user"
                    content={turn.question}
                    onCitation={() => {}}
                  />
                  <ChatMessage
                    role="assistant"
                    content={turn.response.answer}
                    response={turn.response}
                    onCitation={(c) => {
                      setSelected(c);
                      setSources(turn.response.citations);
                      setShowSources(true);
                    }}
                  />
                </div>
              ))
            )}
            {mutation.isPending && (
              <div className="stack studio-turn">
                <ChatMessage
                  role="user"
                  content={mutation.variables}
                  onCitation={() => {}}
                />
                <div className="studio-thinking" role="status">
                  <Loader2 size={17} className="animate-spin" />
                  <span>Finding sources and preparing your answer...</span>
                </div>
              </div>
            )}
            {mutation.isError && (
              <div className="studio-turn">
                <ErrorState error={mutation.error} />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => submit()}
                  disabled={mutation.isPending}
                >
                  <RefreshCw size={12} />
                  Retry question
                </Button>
              </div>
            )}
            <div ref={bottom} />
          </div>
          <div className="studio-composer-area">
            <form
              className="studio-composer"
              onSubmit={(event) => {
                event.preventDefault();
                submit();
              }}
            >
              <div className="studio-context-banner">
                <span>
                  <ShieldCheck size={15} />
                  Built around your knowledge. Backed by sources.
                </span>
                <Link href="/knowledge">
                  Manage documents
                  <Layers3 size={14} />
                </Link>
              </div>
              <div className="studio-input-area">
                <label className="sr-only" htmlFor="question">
                  Ask a question
                </label>
                <textarea
                  ref={composer}
                  id="question"
                  placeholder="What would you like to understand?"
                  maxLength={1000}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  disabled={mutation.isPending}
                  onKeyDown={(e) => {
                    if (
                      e.key === "Enter" &&
                      !e.shiftKey &&
                      !e.nativeEvent.isComposing
                    ) {
                      e.preventDefault();
                      submit();
                    }
                  }}
                />
                <div className="studio-composer-tools">
                  <div className="row wrap">
                    <Link className="studio-tool" href="/knowledge">
                      <Paperclip size={16} />
                      <span>Add documents</span>
                    </Link>
                    <label
                      className={`studio-tool studio-context-toggle ${withHistory ? "selected" : ""}`}
                      title="Include up to six recent messages, bounded to 4,000 characters. Prior answers are not source evidence."
                    >
                      <input
                        type="checkbox"
                        checked={withHistory}
                        onChange={(e) => setWithHistory(e.target.checked)}
                      />
                      <MessageSquare size={15} />
                      <span>Conversation context</span>
                    </label>
                    <span
                      className="studio-tool studio-retrieval-label"
                      title="Each question uses hybrid retrieval over your authorized documents"
                    >
                      <Search size={15} />
                      Hybrid retrieval
                    </span>
                  </div>
                  <Button
                    className="studio-send"
                    size="icon"
                    type="submit"
                    aria-label="Send question"
                    disabled={!question.trim() || mutation.isPending}
                  >
                    {mutation.isPending ? (
                      <Loader2 size={18} className="animate-spin" />
                    ) : (
                      <Send size={19} />
                    )}
                  </Button>
                </div>
              </div>
            </form>
            {!turns.length && !mutation.isPending && (
              <div
                className="studio-suggestions"
                aria-label="Suggested questions"
              >
                {[
                  {
                    label: "Refund policy",
                    icon: BookOpen,
                    question: "What is the customer refund policy?",
                  },
                  {
                    label: "Cancellation terms",
                    icon: FileText,
                    question: "What are the subscription cancellation terms?",
                  },
                  {
                    label: "Security policy",
                    icon: ShieldCheck,
                    question: "What are the internal security requirements?",
                  },
                ].map(({ label, icon: Icon, question: prompt }) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => {
                      setQuestion(prompt);
                      composer.current?.focus();
                    }}
                  >
                    <Icon size={14} />
                    {label}
                  </button>
                ))}
              </div>
            )}
            <p className="studio-disclaimer">
              Session-only conversation · Verify important claims against the
              cited sources.
            </p>
          </div>
        </section>
        {showSources && (
          <SourcePanel
            citation={selected}
            sources={sources}
            onSelect={setSelected}
          />
        )}
      </div>
    </div>
  );
}
