"use client";

import { useCallback, useRef, useState } from "react";
import clsx from "clsx";
import { useRouter } from "next/navigation";
import { uploadVideo } from "@/lib/api";
import { humanBytes } from "@/lib/format";
import { Meteors } from "@/components/ui/meteors";

const ACCEPTED_EXT = [".mp4"];
// Matches the backend default (MAX_UPLOAD_MB). Override both if your
// deployment caps uploads lower.
const MAX_MB = 8192;

export function Uploader() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadPct, setUploadPct] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const pickFile = (f: File) => {
    setError(null);
    const name = f.name.toLowerCase();
    if (!ACCEPTED_EXT.some((ext) => name.endsWith(ext))) {
      setError("Only .mp4 files are supported.");
      return;
    }
    if (f.size === 0) {
      setError("The selected file is empty.");
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`File exceeds the ${MAX_MB} MB limit.`);
      return;
    }
    setFile(f);
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) pickFile(f);
  }, []);

  const submit = async () => {
    if (!file) return;
    setUploading(true);
    setUploadPct(0);
    setError(null);
    try {
      const { job_id } = await uploadVideo(file, setUploadPct);
      router.push(`/jobs/${job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setUploading(false);
    }
  };

  return (
    <div className="panel p-6 sm:p-8">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={clsx(
          "relative overflow-hidden cursor-pointer rounded-2xl border-2 border-dashed px-8 py-14 transition text-center",
          dragging
            ? "border-brand bg-brand/5"
            : "border-surface-border hover:border-brand/60 hover:bg-white/2"
        )}
      >
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <Meteors number={15} />
        </div>
        <div className="mx-auto w-12 h-12 rounded-xl bg-brand/10 text-brand grid place-items-center mb-4">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            className="w-6 h-6"
          >
            <path d="M12 16V4" strokeLinecap="round" />
            <path d="m7 9 5-5 5 5" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" strokeLinecap="round" />
          </svg>
        </div>
        <h3 className="text-base font-semibold">
          Drop a drone video here, or click to browse
        </h3>
        <p className="text-sm text-surface-muted mt-1">
          MP4 only, up to {MAX_MB} MB. H.264 recommended.
        </p>
        <input
          ref={inputRef}
          type="file"
          accept="video/mp4,.mp4"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) pickFile(f);
          }}
        />
      </div>

      {file && (
        <div className="mt-5 flex items-center justify-between gap-4 p-4 rounded-xl border border-surface-border bg-black/20">
          <div className="min-w-0">
            <div className="font-medium truncate">{file.name}</div>
            <div className="text-xs text-surface-muted mt-0.5">
              {humanBytes(file.size)}
              {file.type ? ` · ${file.type}` : ""}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              className="btn-ghost"
              onClick={() => {
                setFile(null);
                setError(null);
                if (inputRef.current) inputRef.current.value = "";
              }}
              disabled={uploading}
            >
              Remove
            </button>
            <button
              className="btn-primary"
              onClick={submit}
              disabled={uploading}
            >
              {uploading ? `Uploading ${uploadPct.toFixed(0)}%` : "Analyze video"}
            </button>
          </div>
        </div>
      )}

      {uploading && (
        <div className="mt-4 h-1.5 rounded-full bg-surface-border overflow-hidden">
          <div
            className="h-full bg-brand transition-all"
            style={{ width: `${uploadPct}%` }}
          />
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      )}
    </div>
  );
}
