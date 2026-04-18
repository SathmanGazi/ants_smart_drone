"use client";

import type { JobProgress as JobProgressT, JobStatus } from "@/types";
import { StatusBadge } from "./StatusBadge";

interface Props {
  status: JobStatus;
  progress: JobProgressT | null;
  connected: boolean;
  error?: string | null;
  filename?: string;
}

export function JobProgress({ status, progress, connected, error, filename }: Props) {
  // Once the job is done, pin the bar to 100% regardless of the last
  // reported frame — cv2's frame count can under-report slightly.
  const rawPct = progress?.percent ?? 0;
  const pct = status === "completed" ? 100 : rawPct;
  return (
    <div className="panel p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-wider text-surface-muted">
            Job
          </div>
          <h2 className="text-lg font-semibold truncate">{filename || "video"}</h2>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="text-[11px] text-surface-muted inline-flex items-center gap-1.5"
            title={connected ? "Live updates connected" : "Reconnecting…"}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                connected ? "bg-emerald-400" : "bg-amber-400 animate-pulse"
              }`}
            />
            {connected ? "live" : "reconnecting"}
          </span>
          <StatusBadge status={status} />
        </div>
      </div>

      <div className="mt-5">
        <div className="flex items-center justify-between text-xs text-surface-muted">
          <span>
            {progress?.frame ?? 0} / {progress?.total_frames ?? 0} frames
          </span>
          <span>{pct.toFixed(1)}%</span>
        </div>
        <div className="mt-2 h-2 rounded-full bg-surface-border overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-brand to-brand-emerald transition-all"
            style={{ width: `${Math.min(100, pct)}%` }}
          />
        </div>
        <div className="mt-2 text-xs text-surface-muted">
          {status === "processing"
            ? `Processing at ~${progress?.fps_processing?.toFixed(1) ?? "—"} fps`
            : status === "queued"
            ? "Waiting to start…"
            : status === "completed"
            ? "Complete."
            : "Stopped."}
        </div>
      </div>

      {error && (
        <div className="mt-4 rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      )}
    </div>
  );
}
