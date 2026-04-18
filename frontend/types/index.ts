export type JobStatus = "queued" | "processing" | "completed" | "failed";

export interface JobProgress {
  frame: number;
  total_frames: number;
  percent: number;
  fps_processing: number;
  message?: string | null;
}

export interface JobRecord {
  id: string;
  filename: string;
  status: JobStatus;
  progress: JobProgress;
  error?: string | null;
  created_at: number;
  started_at?: number | null;
  finished_at?: number | null;
}

export interface TrackReport {
  track_id: number;
  vehicle_class: string;
  first_seen_frame: number;
  last_seen_frame: number;
  first_seen_ts: number;
  last_seen_ts: number;
  total_hits: number;
  median_confidence: number;
  counted_at_frame: number;
}

export interface DetectionRow {
  frame: number;
  timestamp: number;
  track_id: number;
  vehicle_class: string;
  confidence: number;
  bbox: [number, number, number, number];
}

export interface RejectedTrack {
  track_id: number;
  vehicle_class: string;
  first_seen_frame: number;
  last_seen_frame: number;
  first_seen_ts: number;
  last_seen_ts: number;
  total_hits: number;
  displacement_px: number;
  median_confidence: number;
  rejection_reason: string;
}

export interface JobResult {
  job_id: string;
  total_unique: number;
  by_class: Record<string, number>;
  processing_duration_sec: number;
  video_duration_sec: number;
  fps: number;
  total_frames: number;
  counted_tracks: TrackReport[];
  rejected_tracks: RejectedTrack[];
  rejection_summary: Record<string, number>;
  sample_detections: DetectionRow[];
  processed_video_url: string;
  csv_url: string;
  xlsx_url: string;
}

export type SocketEvent =
  | { type: "snapshot"; status: JobStatus; progress: JobProgress; error?: string | null }
  | { type: "progress"; progress: JobProgress }
  | {
      type: "status";
      status: JobStatus;
      error?: string | null;
      total_unique?: number;
      by_class?: Record<string, number>;
    }
  | { type: "error"; error: string };
