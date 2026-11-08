"use client";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownToLine,
  ChevronLeft,
  ChevronRight,
  FileText,
  Loader2,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { api, apiDelete, upload } from "@/lib/api";
import {
  capabilitiesSchema,
  chunksSchema,
  documentSchema,
  type DocumentRecord,
} from "@/lib/contracts";
import { formatBytes, formatDate } from "@/lib/utils";
import { Button } from "./ui/button";
import { Modal } from "./ui/dialog";
import {
  ConfirmationDialog,
  EmptyState,
  ErrorState,
  LoadingSkeleton,
} from "./common";
export function DocumentTable({
  items,
  onInspect,
  onDelete,
}: {
  items: DocumentRecord[];
  onInspect: (d: DocumentRecord) => void;
  onDelete?: (d: DocumentRecord) => void;
}) {
  if (!items.length)
    return (
      <EmptyState
        title="No documents here yet"
        description="Upload a PDF, text file or Markdown document to start building your knowledge base."
      />
    );
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Document</th>
            <th>Status</th>
            <th>Chunks</th>
            <th>Uploaded</th>
            <th>
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((doc) => (
            <tr key={doc.id}>
              <td>
                <div className="row">
                  <div
                    className={`file-icon file-${doc.filename?.split(".").pop()?.toLowerCase() || "txt"}`}
                  >
                    <FileText size={16} />
                  </div>
                  <div>
                    <button
                      className="document-name"
                      onClick={() => onInspect(doc)}
                    >
                      {doc.filename || doc.title}
                    </button>
                    <p className="document-meta">
                      {formatBytes(doc.size_bytes)} ·{" "}
                      {(
                        doc.filename?.split(".").pop() || "document"
                      ).toUpperCase()}
                    </p>
                  </div>
                </div>
              </td>
              <td>
                <span className={`pill ${doc.status}`}>
                  <span className="dot" />
                  {doc.status}
                </span>
              </td>
              <td className="muted">{doc.chunk_count.toLocaleString()}</td>
              <td className="muted">{formatDate(doc.created_at)}</td>
              <td>
                {onDelete && (
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Delete ${doc.filename || doc.title}`}
                    onClick={() => onDelete(doc)}
                  >
                    <Trash2 size={14} />
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function UploadDropzone() {
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState(0);
  const [validation, setValidation] = useState("");
  const [filename, setFilename] = useState("");
  const capabilities = useQuery({
    queryKey: ["capabilities"],
    queryFn: () => api("capabilities", capabilitiesSchema),
  });
  const limit = Math.min(
    capabilities.data?.max_upload_bytes || 10485760,
    10485760,
  );
  const mutation = useMutation({
    mutationFn: (file: File) => upload(file, setProgress, documentSchema),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
  });
  function accept(file?: File) {
    if (!file || mutation.isPending) return;
    setValidation("");
    mutation.reset();
    if (!/\.(pdf|txt|md|markdown)$/i.test(file.name)) {
      setValidation("Choose a PDF, TXT or Markdown file.");
      return;
    }
    if (!file.size) {
      setValidation("This file is empty.");
      return;
    }
    if (file.size > limit) {
      setValidation(`Choose a file smaller than ${formatBytes(limit)}.`);
      return;
    }
    setFilename(file.name);
    setProgress(0);
    mutation.mutate(file);
  }
  return (
    <div
      className={`dropzone ${dragging ? "dragging" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        if (e.dataTransfer.files.length > 1) {
          setValidation("Upload one document at a time.");
          return;
        }
        accept(e.dataTransfer.files[0]);
      }}
    >
      <div className="drop-icon">
        {mutation.isPending ? (
          <Loader2 className="animate-spin" size={21} />
        ) : (
          <UploadCloud size={21} />
        )}
      </div>
      <h2>
        {mutation.isPending
          ? progress === 100
            ? "Indexing your document…"
            : "Uploading your document…"
          : "A little knowledge goes a long way."}
      </h2>
      <p>
        {mutation.isPending
          ? filename
          : `Drop a document here, or choose a file. PDF, TXT, Markdown · up to ${formatBytes(limit)}`}
      </p>
      <input
        ref={input}
        className="sr-only"
        type="file"
        accept=".pdf,.txt,.md,.markdown"
        aria-label="Upload document"
        onChange={(e) => {
          accept(e.target.files?.[0]);
          e.target.value = "";
        }}
        disabled={mutation.isPending}
      />
      {mutation.isPending ? (
        <>
          <div
            className="progress"
            role="progressbar"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="File transfer"
          >
            <div style={{ width: `${progress}%` }} />
          </div>
          <small className="muted">
            {progress === 100
              ? "Transfer complete. Extraction and embedding are still running."
              : `${progress}% transferred`}
          </small>
        </>
      ) : (
        <Button variant="outline" onClick={() => input.current?.click()}>
          <ArrowDownToLine size={14} />
          Choose document
        </Button>
      )}
      {validation && (
        <p role="alert" style={{ color: "var(--danger)" }}>
          {validation}
        </p>
      )}
      {mutation.isError && (
        <div style={{ marginTop: 16 }}>
          <ErrorState error={mutation.error} />
        </div>
      )}
      {mutation.isSuccess && (
        <p
          role="status"
          className="text-primary"
          style={{ color: "var(--primary)" }}
        >
          {filename} is indexed and ready.
        </p>
      )}
    </div>
  );
}
export function DocumentInspector({
  document,
  onClose,
}: {
  document: DocumentRecord | null;
  onClose: () => void;
}) {
  const [offset, setOffset] = useState(0);
  const detail = useQuery({
    queryKey: ["documents", "detail", document?.id],
    queryFn: () => api(`documents/${document!.id}`, documentSchema),
    enabled: !!document,
  });
  const chunks = useQuery({
    queryKey: ["documents", "chunks", document?.id, offset],
    queryFn: () =>
      api(
        `documents/${document!.id}/chunks?limit=10&offset=${offset}`,
        chunksSchema,
      ),
    enabled: !!document,
  });
  const doc = detail.data || document;
  return (
    <Modal
      open={!!document}
      onOpenChange={(open) => {
        if (!open) {
          onClose();
          setOffset(0);
        }
      }}
      title={doc?.filename || "Document details"}
      description="Metadata and stored source passages"
    >
      {doc && (
        <>
          <dl className="metadata">
            <dt>Document ID</dt>
            <dd>
              <code>{doc.id}</code>
            </dd>
            <dt>Ingestion</dt>
            <dd>
              <span className={`pill ${doc.status}`}>{doc.status}</span>
            </dd>
            <dt>Size / chunks</dt>
            <dd>
              {formatBytes(doc.size_bytes)} / {doc.chunk_count}
            </dd>
            <dt>Pages</dt>
            <dd>{doc.page_count ?? "Not available for this format"}</dd>
            <dt>Embedding model</dt>
            <dd>{doc.embedding_model || "Not embedded"}</dd>
            <dt>SHA-256</dt>
            <dd>
              <code>{doc.content_hash || "Unavailable"}</code>
            </dd>
            {doc.error_code && (
              <>
                <dt>Error</dt>
                <dd>{doc.error_code}</dd>
              </>
            )}
          </dl>
          <h2>Stored chunks</h2>
          {chunks.isPending ? (
            <LoadingSkeleton />
          ) : chunks.isError ? (
            <ErrorState error={chunks.error} />
          ) : !chunks.data.items.length ? (
            <p className="muted small" style={{ marginTop: 12 }}>
              No stored chunks.
            </p>
          ) : (
            chunks.data.items.map((chunk) => (
              <article className="chunk-preview" key={chunk.id}>
                <div className="between">
                  <span className="pill">Chunk {chunk.position + 1}</span>
                  <small className="muted">
                    {chunk.page_number
                      ? `Page ${chunk.page_number}`
                      : `Offset ${chunk.start_offset ?? "—"}`}
                  </small>
                </div>
                <p>{chunk.content}</p>
                {chunk.truncated && (
                  <small className="muted">
                    Preview limited to 2,000 characters.
                  </small>
                )}
              </article>
            ))
          )}
          <div className="pagination">
            <Button
              variant="ghost"
              size="icon"
              aria-label="Previous chunks"
              disabled={!offset || chunks.isFetching}
              onClick={() => setOffset(Math.max(0, offset - 10))}
            >
              <ChevronLeft size={15} />
            </Button>
            <span>From chunk {offset + 1}</span>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Next chunks"
              disabled={
                chunks.isFetching ||
                !chunks.data ||
                chunks.data.items.length < 10 ||
                offset + 10 >= doc.chunk_count
              }
              onClick={() => setOffset(offset + 10)}
            >
              <ChevronRight size={15} />
            </Button>
          </div>
        </>
      )}
    </Modal>
  );
}
export function DeleteDocumentDialog({
  document,
  onClose,
}: {
  document: DocumentRecord | null;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: async () => {
      await apiDelete(`documents/${document!.id}`);
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["documents"] });
      client.invalidateQueries({ queryKey: ["stats"] });
      onClose();
    },
  });
  return (
    <>
      <ConfirmationDialog
        open={!!document}
        onOpenChange={(v) => {
          if (!v) onClose();
        }}
        title="Delete this document?"
        description={`“${document?.filename || document?.title || "Document"}” and its stored chunks will be permanently removed. This cannot be undone.`}
        onConfirm={() => mutation.mutate()}
        pending={mutation.isPending}
      />
      {mutation.isError && <ErrorState error={mutation.error} />}
    </>
  );
}
