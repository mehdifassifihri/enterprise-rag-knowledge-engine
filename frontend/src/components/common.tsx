"use client";
import Link from "next/link";
import { AlertCircle, ArrowRight, Files, RefreshCw } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { ApiError } from "@/lib/api";
import { Button } from "./ui/button";
import { Modal } from "./ui/dialog";
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="between page-heading">
      <div>
        {eyebrow && (
          <p className="eyebrow" style={{ marginBottom: 10, marginTop: 0 }}>
            {eyebrow}
          </p>
        )}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
export function StatCard({
  label,
  value,
  caption,
  icon: Icon,
}: {
  label: string;
  value: React.ReactNode;
  caption: string;
  icon: LucideIcon;
}) {
  return (
    <div className="card stat-card">
      <div className="stat-top">
        <span>{label}</span>
        <span className="stat-icon-wrap">
          <Icon className="stat-icon" size={19} />
        </span>
      </div>
      <div className="stat-number">{value}</div>
      <div className="stat-caption">{caption}</div>
    </div>
  );
}
export function EmptyState({
  title,
  description,
  icon: Icon = Files,
  action,
}: {
  title: string;
  description: string;
  icon?: LucideIcon;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Icon size={20} />
      </div>
      <h2>{title}</h2>
      <p>{description}</p>
      {action}
    </div>
  );
}
export function ErrorState({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  return (
    <div className="error-state" role="alert">
      <AlertCircle size={17} />
      <span className="spacer">
        {error instanceof Error ? error.message : "Something went wrong."}
      </span>
      {retry && (
        <Button variant="ghost" size="sm" onClick={retry}>
          <RefreshCw size={13} />
          Retry
        </Button>
      )}
      {error instanceof ApiError && error.status === 401 && (
        <Link className="link" href="/login">
          Sign in
          <ArrowRight size={12} />
        </Link>
      )}
    </div>
  );
}
export function LoadingSkeleton() {
  return (
    <div
      className="card card-pad"
      role="status"
      aria-label="Loading workspace data"
    >
      <div className="skeleton skeleton-line" />
      <div className="skeleton skeleton-line" style={{ width: "95%" }} />
      <div className="skeleton skeleton-line" style={{ width: "55%" }} />
    </div>
  );
}
export function ConfirmationDialog({
  open,
  onOpenChange,
  title,
  description,
  onConfirm,
  pending,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  title: string;
  description: string;
  onConfirm: () => void;
  pending: boolean;
}) {
  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={description}
    >
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <Button
          variant="outline"
          onClick={() => onOpenChange(false)}
          disabled={pending}
        >
          Cancel
        </Button>
        <Button variant="destructive" onClick={onConfirm} disabled={pending}>
          {pending ? "Deleting…" : "Delete document"}
        </Button>
      </div>
    </Modal>
  );
}
