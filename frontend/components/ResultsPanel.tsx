"use client";

import { useState } from "react";
import { absolute } from "@/lib/api";
import type { JobResult } from "@/types";
import { DetectionsTable } from "./DetectionsTable";
import { MetricsCards } from "./MetricsCards";
import { RejectionsPanel } from "./RejectionsPanel";

interface Props {
  result: JobResult;
}

export function ResultsPanel({ result }: Props) {
  const videoUrl = absolute(result.processed_video_url);
  const csvUrl = absolute(result.csv_url);
  const xlsxUrl = absolute(result.xlsx_url);
  const [videoBroken, setVideoBroken] = useState(false);

  return (
    <div className="space-y-6">
      <MetricsCards result={result} />

      <div className="panel overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 p-4 border-b border-surface-border">
          <div>
            <h3 className="font-semibold">Processed video</h3>
            <p className="text-xs text-surface-muted mt-0.5">
              Bounding boxes, class labels, track IDs, motion trails.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <a className="btn-ghost" href={csvUrl} download>
              Download CSV
            </a>
            <a className="btn-primary" href={xlsxUrl} download>
              Download XLSX
            </a>
          </div>
        </div>
        <div className="bg-black relative">
          <video
            key={videoUrl}
            className="w-full max-h-[70vh] block"
            src={videoUrl}
            controls
            playsInline
            onError={() => setVideoBroken(true)}
          />
          {videoBroken && (
            <div className="absolute inset-0 bg-black/80 grid place-items-center p-6 text-center">
              <div className="max-w-md">
                <h4 className="font-semibold text-rose-200">
                  Browser couldn’t decode this video
                </h4>
                <p className="text-sm text-surface-muted mt-1.5">
                  The annotated file exists on disk but its codec isn’t
                  web-playable. Install <code className="kbd">ffmpeg</code> on
                  the backend machine so it can transcode to H.264, then
                  re-run the job. You can still download the raw output below.
                </p>
                <a href={videoUrl} download className="btn-ghost mt-4 inline-flex">
                  Download processed.mp4
                </a>
              </div>
            </div>
          )}
        </div>
      </div>

      <DetectionsTable tracks={result.counted_tracks} />

      <RejectionsPanel
        rejected={result.rejected_tracks}
        summary={result.rejection_summary}
      />
    </div>
  );
}
