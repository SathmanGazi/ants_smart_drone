"use client";

import { useState } from "react";
import type { TripwireCrossing } from "@/types";
import { formatTimestamp } from "@/lib/format";

interface Props {
  counts: Record<string, number>;
  crossings: TripwireCrossing[];
}

export function TripwirePanel({ counts, crossings }: Props) {
  const [open, setOpen] = useState(false);
  const directions = Object.keys(counts);
  const total = Object.values(counts).reduce((a, b) => a + b, 0);

  return (
    <div className="panel overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-3 p-4 text-left hover:bg-surface-border/30 transition"
      >
        <div>
          <h3 className="font-semibold">Tripwire crossings</h3>
          <p className="text-xs text-surface-muted mt-0.5">
            Directional counts from the configured virtual line.
            {total === 0 && " No crossings recorded."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {directions.map((d) => (
            <span
              key={d}
              className="inline-flex items-center gap-1.5 rounded-full bg-cyan-500/10 border border-cyan-400/30 px-2.5 py-1 text-xs text-cyan-200 tabular-nums"
            >
              <span className="uppercase text-[10px] text-cyan-300/80">{d}</span>
              <span className="font-semibold">{counts[d] ?? 0}</span>
            </span>
          ))}
          <span className="text-surface-muted text-sm">{open ? "–" : "+"}</span>
        </div>
      </button>

      {open && (
        <div className="border-t border-surface-border">
          {crossings.length === 0 ? (
            <p className="p-4 text-sm text-surface-muted">
              No vehicles crossed the tripwire during this clip.
            </p>
          ) : (
            <div className="max-h-80 overflow-auto thin-scroll">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-surface z-10">
                  <tr className="text-left text-xs uppercase tracking-wider text-surface-muted">
                    <th className="px-4 py-2">Track</th>
                    <th className="px-4 py-2">Class</th>
                    <th className="px-4 py-2">Frame</th>
                    <th className="px-4 py-2">Timestamp</th>
                    <th className="px-4 py-2">Direction</th>
                  </tr>
                </thead>
                <tbody>
                  {crossings.map((c, i) => (
                    <tr
                      key={`${c.track_id}-${c.frame}-${c.direction}-${i}`}
                      className="border-t border-surface-border/60"
                    >
                      <td className="px-4 py-2 tabular-nums">#{c.track_id}</td>
                      <td className="px-4 py-2">{c.vehicle_class}</td>
                      <td className="px-4 py-2 tabular-nums">{c.frame}</td>
                      <td className="px-4 py-2 tabular-nums">
                        {formatTimestamp(c.timestamp)}
                      </td>
                      <td className="px-4 py-2">
                        <span className="inline-flex rounded-full bg-cyan-500/10 border border-cyan-400/30 px-2 py-0.5 text-xs text-cyan-200 uppercase">
                          {c.direction}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
