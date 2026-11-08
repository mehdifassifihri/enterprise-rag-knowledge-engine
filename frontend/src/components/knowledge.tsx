"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { api } from "@/lib/api";
import {
  documentListSchema,
  statsSchema,
  type DocumentRecord,
} from "@/lib/contracts";
import { PageHeading, ErrorState, LoadingSkeleton } from "./common";
import { Button } from "./ui/button";
import {
  DeleteDocumentDialog,
  DocumentInspector,
  DocumentTable,
  UploadDropzone,
} from "./documents";
export function Knowledge() {
  const [offset, setOffset] = useState(0);
  const [filter, setFilter] = useState("");
  const [status, setStatus] = useState("all");
  const [selected, setSelected] = useState<DocumentRecord | null>(null);
  const [deleting, setDeleting] = useState<DocumentRecord | null>(null);
  const documents = useQuery({
    queryKey: ["documents", "page", offset],
    queryFn: () =>
      api(`documents?limit=20&offset=${offset}`, documentListSchema),
  });
  const stats = useQuery({
    queryKey: ["stats"],
    queryFn: () => api("documents/stats", statsSchema),
  });
  const items =
    documents.data?.items.filter(
      (d) =>
        (d.filename || d.title).toLowerCase().includes(filter.toLowerCase()) &&
        (status === "all" || d.status === status),
    ) || [];
  return (
    <>
      <PageHeading
        eyebrow="A single source of context"
        title="Knowledge base"
        description="Turn your source documents into searchable, connected knowledge."
      />
      <div className="stack">
        <UploadDropzone />
        <div className="toolbar">
          <div className="input-wrap">
            <Search size={15} />
            <input
              className="input"
              aria-label="Filter documents on this page"
              placeholder="Filter documents on this page…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>
          <div className="row">
            <label className="sr-only" htmlFor="status">
              Ingestion status
            </label>
            <select
              className="input"
              id="status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="all">All statuses</option>
              <option value="ready">Ready</option>
              <option value="failed">Failed</option>
              <option value="pending">Pending</option>
              <option value="processing">Processing</option>
            </select>
            <span className="pill">{stats.data?.documents ?? "—"} total</span>
          </div>
        </div>
        <section className="card">
          <div className="between section-header">
            <div>
              <h2>All documents</h2>
              <p>Your workspace’s searchable source library</p>
            </div>
            <span className="pill">{items.length} on this page</span>
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
              items={items}
              onInspect={setSelected}
              onDelete={setDeleting}
            />
          )}
          <div className="pagination">
            <span>
              Page {Math.floor(offset / 20) + 1} · filters apply to this page
            </span>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Previous documents"
              disabled={!offset || documents.isFetching}
              onClick={() => setOffset(Math.max(0, offset - 20))}
            >
              <ChevronLeft size={15} />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Next documents"
              disabled={
                documents.isFetching ||
                !documents.data ||
                documents.data.items.length < 20 ||
                (stats.data !== undefined &&
                  offset + 20 >= stats.data.documents)
              }
              onClick={() => setOffset(offset + 20)}
            >
              <ChevronRight size={15} />
            </Button>
          </div>
        </section>
        <p className="quiet-note">
          Source bytes are not retained. Deleting a document also deletes its
          chunks and embeddings.
        </p>
      </div>
      <DocumentInspector
        document={selected}
        onClose={() => setSelected(null)}
      />
      <DeleteDocumentDialog
        document={deleting}
        onClose={() => setDeleting(null)}
      />
    </>
  );
}
