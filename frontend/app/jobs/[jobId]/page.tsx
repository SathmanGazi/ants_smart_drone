"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getJob, getResult } from "@/lib/api";
import { useJobSocket } from "@/lib/useJobSocket";
import { JobProgress } from "@/components/JobProgress";
import { ResultsPanel } from "@/components/ResultsPanel";
import type { JobRecord, JobResult, JobStatus } from "@/types";

export default function JobPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = params?.jobId ?? null;

  const [job, setJob] = useState<JobRecord | null>(null);
  const [result, setResult] = useState<JobResult | null>(null);
  const [fatal, setFatal] = useState<string | null>(null);

  const socket = useJobSocket(jobId);

  // Initial fetch
  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    getJob(jobId)
      .then((j) => {
        if (!cancelled) setJob(j);
      })
      .catch((e) => {
        if (!cancelled)
          setFatal(e instanceof Error ? e.message : "Failed to load job");
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  // Keep local job in sync with socket status/progress
  useEffect(() => {
    if (!job || !socket) return;
    setJob((prev) => {
      if (!prev) return prev;
      const next: JobRecord = { ...prev };
      if (socket.status) next.status = socket.status;
      if (socket.progress) next.progress = socket.progress;
      if (socket.error) next.error = socket.error;
      return next;
    });
  }, [socket.status, socket.progress, socket.error]);

  // Polling fallback in case the socket never connects
  useEffect(() => {
    if (!jobId) return;
    if (socket.connected) return;
    const t = setInterval(async () => {
      try {
        const j = await getJob(jobId);
        setJob(j);
      } catch {
        /* ignore */
      }
    }, 1500);
    return () => clearInterval(t);
  }, [jobId, socket.connected]);

  // Fetch result once completed
  const status: JobStatus | null = job?.status ?? null;
  useEffect(() => {
    if (!jobId || status !== "completed" || result) return;
    getResult(jobId)
      .then(setResult)
      .catch((e) =>
        setFatal(e instanceof Error ? e.message : "Failed to load result")
      );
  }, [jobId, status, result]);

  if (fatal) {
    return (
      <div className="panel p-6">
        <h2 className="text-lg font-semibold">Couldn’t load job</h2>
        <p className="text-sm text-surface-muted mt-1">{fatal}</p>
        <a className="btn-ghost mt-4 inline-flex" href="/">
          ← Back to upload
        </a>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="panel p-6">
        <div className="h-5 w-40 rounded bg-surface-border animate-pulse" />
        <div className="mt-3 h-3 w-64 rounded bg-surface-border animate-pulse" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <JobProgress
        status={job.status}
        progress={job.progress}
        connected={socket.connected}
        error={job.error}
        filename={job.filename}
      />

      {job.status === "completed" && result && <ResultsPanel result={result} />}
      {job.status === "completed" && !result && (
        <div className="panel p-6 text-sm text-surface-muted">
          Loading results…
        </div>
      )}
      {job.status === "failed" && (
        <div className="panel p-6 border-rose-500/40">
          <h3 className="font-semibold text-rose-200">Processing failed</h3>
          <p className="text-sm text-surface-muted mt-1">
            {job.error ?? "The pipeline reported an unknown error."}
          </p>
          <a className="btn-ghost mt-4 inline-flex" href="/">
            Try another file
          </a>
        </div>
      )}
    </div>
  );
}
