import clsx from "clsx";
import type { JobStatus } from "@/types";

const STYLES: Record<JobStatus, string> = {
  queued: "bg-slate-700/40 text-slate-200 border-slate-600",
  processing: "bg-brand-soft/60 text-brand border-brand/40",
  completed: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  failed: "bg-rose-500/15 text-rose-300 border-rose-500/40",
};

const LABELS: Record<JobStatus, string> = {
  queued: "Queued",
  processing: "Processing",
  completed: "Completed",
  failed: "Failed",
};

export function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs border font-medium",
        STYLES[status]
      )}
    >
      <span
        className={clsx(
          "w-1.5 h-1.5 rounded-full",
          status === "processing" && "bg-brand animate-pulse",
          status === "completed" && "bg-emerald-400",
          status === "failed" && "bg-rose-400",
          status === "queued" && "bg-slate-400"
        )}
      />
      {LABELS[status]}
    </span>
  );
}
