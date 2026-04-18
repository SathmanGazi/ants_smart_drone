import type { JobRecord, JobResult } from "@/types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ||
  API_URL.replace(/^http/, "ws");

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data?.detail) detail = data.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function uploadVideo(
  file: File,
  onProgress?: (pct: number) => void
): Promise<{ job_id: string; status: string; filename: string }> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/jobs`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress((e.loaded / e.total) * 100);
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch (err) {
          reject(err);
        }
      } else {
        let detail = `HTTP ${xhr.status}`;
        try {
          detail = JSON.parse(xhr.responseText)?.detail || detail;
        } catch {
          /* ignore */
        }
        reject(new Error(detail));
      }
    };
    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.send(form);
  });
}

export async function getJob(jobId: string): Promise<JobRecord> {
  const res = await fetch(`${API_URL}/jobs/${jobId}`, { cache: "no-store" });
  return handle<JobRecord>(res);
}

export async function getResult(jobId: string): Promise<JobResult> {
  const res = await fetch(`${API_URL}/jobs/${jobId}/result`, {
    cache: "no-store",
  });
  return handle<JobResult>(res);
}

export function absolute(url: string): string {
  return url.startsWith("http") ? url : `${API_URL}${url}`;
}
