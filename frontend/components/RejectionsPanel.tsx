"use client";

import { useState } from "react";
import clsx from "clsx";
import { formatTimestamp } from "@/lib/format";
import type { RejectedTrack } from "@/types";

interface Props {
  rejected: RejectedTrack[];
  summary: Record<string, number>;
}

export function RejectionsPanel({ rejected, summary }: Props) {
  const [open, setOpen] = useState(false);
  const total = rejected.length;
  const summaryItems = Object.entries(summary).sort((a, b) => b[1] - a[1]);

  return (
    <div className="panel overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-4 p-4 text-left hover:bg-white/2 transition"
      >
        <div>
          <h3 className="font-semibold">Rejected candidate tracks</h3>
          <p className="text-xs text-surface-muted mt-0.5">
            Tracks the tracker opened but the counting gate rejected.
            Confirms the filter is killing flickers and stationary short-lived boxes — not real vehicles.
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span className="text-sm tabular-nums">
            <span className="font-semibold">{total}</span>
            <span className="text-surface-muted"> rejected</span>
          </span>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className={clsx(
              "w-4 h-4 text-surface-muted transition-transform",
              open && "rotate-180"
            )}
          >
            <path d="m6 9 6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
      </button>

      {open && (
        <div className="border-t border-surface-border">
          {summaryItems.length > 0 && (
            <div className="flex flex-wrap gap-2 px-4 py-3 border-b border-surface-border">
              {summaryItems.map(([reason, n]) => (
                <span
                  key={reason}
                  className="text-xs px-2.5 py-1 rounded-full border border-surface-border bg-black/30 font-mono"
                >
                  {reason}
                  <span className="ml-2 text-surface-muted">×{n}</span>
                </span>
              ))}
            </div>
          )}

          <div className="thin-scroll overflow-auto max-h-[420px]">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface-raised/95 backdrop-blur z-10">
                <tr className="text-left text-xs uppercase tracking-wider text-surface-muted">
                  <th className="px-4 py-2 font-medium">Track</th>
                  <th className="px-4 py-2 font-medium">Class</th>
                  <th className="px-4 py-2 font-medium text-right">First</th>
                  <th className="px-4 py-2 font-medium text-right">Last</th>
                  <th className="px-4 py-2 font-medium text-right">Frames</th>
                  <th className="px-4 py-2 font-medium text-right">Disp. (px)</th>
                  <th className="px-4 py-2 font-medium text-right">Conf.</th>
                  <th className="px-4 py-2 font-medium">Reason</th>
                </tr>
              </thead>
              <tbody>
                {rejected.map((r) => (
                  <tr
                    key={r.track_id}
                    className="border-t border-surface-border/60 hover:bg-white/2"
                  >
                    <td className="px-4 py-2 tabular-nums">{r.track_id}</td>
                    <td className="px-4 py-2 capitalize">{r.vehicle_class}</td>
                    <td className="px-4 py-2 tabular-nums text-right">
                      {formatTimestamp(r.first_seen_ts)}
                    </td>
                    <td className="px-4 py-2 tabular-nums text-right">
                      {formatTimestamp(r.last_seen_ts)}
                    </td>
                    <td className="px-4 py-2 tabular-nums text-right">
                      {r.total_hits}
                    </td>
                    <td className="px-4 py-2 tabular-nums text-right">
                      {r.displacement_px.toFixed(0)}
                    </td>
                    <td className="px-4 py-2 tabular-nums text-right">
                      {r.median_confidence.toFixed(2)}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs text-surface-muted">
                      {r.rejection_reason}
                    </td>
                  </tr>
                ))}
                {rejected.length === 0 && (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-4 py-10 text-center text-surface-muted"
                    >
                      No rejected tracks — every candidate passed the gate.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
