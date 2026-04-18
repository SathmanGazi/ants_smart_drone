"use client";

import { useEffect, useRef, useState } from "react";
import { WS_URL } from "./api";
import type { JobProgress, JobStatus, SocketEvent } from "@/types";

interface UseJobSocketState {
  status: JobStatus | null;
  progress: JobProgress | null;
  error: string | null;
  connected: boolean;
}

export function useJobSocket(jobId: string | null): UseJobSocketState {
  const [state, setState] = useState<UseJobSocketState>({
    status: null,
    progress: null,
    error: null,
    connected: false,
  });
  const retryRef = useRef(0);
  const aliveRef = useRef(true);

  useEffect(() => {
    if (!jobId) return;
    aliveRef.current = true;
    let ws: WebSocket | null = null;
    let pingTimer: ReturnType<typeof setInterval> | null = null;

    const connect = () => {
      if (!aliveRef.current) return;
      ws = new WebSocket(`${WS_URL}/ws/jobs/${jobId}`);

      ws.onopen = () => {
        retryRef.current = 0;
        setState((s) => ({ ...s, connected: true }));
        pingTimer = setInterval(() => {
          try {
            ws?.send("ping");
          } catch {
            /* ignore */
          }
        }, 20_000);
      };

      ws.onmessage = (ev) => {
        let msg: SocketEvent;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }
        setState((s) => {
          switch (msg.type) {
            case "snapshot":
              return {
                ...s,
                status: msg.status,
                progress: msg.progress,
                error: msg.error ?? null,
              };
            case "progress":
              return { ...s, progress: msg.progress };
            case "status":
              return {
                ...s,
                status: msg.status,
                error: msg.error ?? s.error,
              };
            case "error":
              return { ...s, error: msg.error };
            default:
              return s;
          }
        });
      };

      ws.onclose = () => {
        if (pingTimer) clearInterval(pingTimer);
        setState((s) => ({ ...s, connected: false }));
        if (!aliveRef.current) return;
        retryRef.current += 1;
        const delay = Math.min(10_000, 500 * 2 ** retryRef.current);
        setTimeout(connect, delay);
      };

      ws.onerror = () => {
        try {
          ws?.close();
        } catch {
          /* ignore */
        }
      };
    };

    connect();
    return () => {
      aliveRef.current = false;
      if (pingTimer) clearInterval(pingTimer);
      try {
        ws?.close();
      } catch {
        /* ignore */
      }
    };
  }, [jobId]);

  return state;
}
