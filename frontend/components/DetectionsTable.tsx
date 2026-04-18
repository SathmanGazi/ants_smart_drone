"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import { formatTimestamp } from "@/lib/format";
import type { TrackReport } from "@/types";

interface Props {
  tracks: TrackReport[];
}

const COLUMNS: {
  key: keyof TrackReport;
  label: string;
  align?: "left" | "right";
  format?: (v: number | string) => string;
}[] = [
  { key: "track_id", label: "Track" },
  { key: "vehicle_class", label: "Class" },
  {
    key: "first_seen_ts",
    label: "First seen",
    align: "right",
    format: (v) => formatTimestamp(Number(v)),
  },
  {
    key: "last_seen_ts",
    label: "Last seen",
    align: "right",
    format: (v) => formatTimestamp(Number(v)),
  },
  { key: "total_hits", label: "Frames", align: "right" },
  {
    key: "median_confidence",
    label: "Conf.",
    align: "right",
    format: (v) => Number(v).toFixed(2),
  },
  { key: "counted_at_frame", label: "Counted @", align: "right" },
];

export function DetectionsTable({ tracks }: Props) {
  const [query, setQuery] = useState("");
  const [classFilter, setClassFilter] = useState("all");

  const classes = useMemo(
    () => Array.from(new Set(tracks.map((t) => t.vehicle_class))).sort(),
    [tracks]
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return tracks.filter((t) => {
      if (classFilter !== "all" && t.vehicle_class !== classFilter) return false;
      if (!q) return true;
      return (
        String(t.track_id).includes(q) ||
        t.vehicle_class.toLowerCase().includes(q)
      );
    });
  }, [tracks, query, classFilter]);

  return (
    <div className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 p-4 border-b border-surface-border">
        <h3 className="font-semibold">Counted tracks</h3>
        <div className="flex items-center gap-2">
          <select
            value={classFilter}
            onChange={(e) => setClassFilter(e.target.value)}
            className="bg-black/30 border border-surface-border rounded-lg px-2.5 py-1.5 text-sm"
          >
            <option value="all">All classes</option>
            {classes.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search id or class"
            className="bg-black/30 border border-surface-border rounded-lg px-3 py-1.5 text-sm w-48"
          />
        </div>
      </div>

      <div className="thin-scroll overflow-auto max-h-[520px]">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-surface-raised/95 backdrop-blur z-10">
            <tr className="text-left text-xs uppercase tracking-wider text-surface-muted">
              {COLUMNS.map((c) => (
                <th
                  key={c.key}
                  className={clsx(
                    "px-4 py-2 font-medium",
                    c.align === "right" && "text-right"
                  )}
                >
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => (
              <tr
                key={t.track_id}
                className="border-t border-surface-border/60 hover:bg-white/2"
              >
                {COLUMNS.map((c) => {
                  const raw = t[c.key] as number | string;
                  const value = c.format ? c.format(raw) : String(raw);
                  return (
                    <td
                      key={c.key}
                      className={clsx(
                        "px-4 py-2 tabular-nums",
                        c.align === "right" && "text-right",
                        c.key === "vehicle_class" && "capitalize"
                      )}
                    >
                      {value}
                    </td>
                  );
                })}
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td
                  colSpan={COLUMNS.length}
                  className="px-4 py-10 text-center text-surface-muted"
                >
                  No tracks match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
