# Smart Drone Traffic Analyzer

End-to-end proof of concept for analyzing aerial / drone video footage:
uploads an `.mp4`, detects and tracks vehicles, produces a de-duplicated
unique-vehicle count, renders an annotated video, and exports CSV / XLSX
reports.

This is built as a real, modular full-stack app — not a one-file demo —
so the same codebase can grow into a production traffic-analytics service.

---

## Stack

| Layer           | Choice                                        |
|-----------------|-----------------------------------------------|
| Frontend        | Next.js 14 (App Router) + TypeScript + Tailwind |
| Backend         | FastAPI + Pydantic v2                         |
| Realtime        | Native WebSocket (`/ws/jobs/{id}`)            |
| Detection       | YOLOv8 (Ultralytics)                          |
| Tracking        | ByteTrack (via `supervision`)                 |
| Video I/O       | OpenCV                                        |
| Reporting       | pandas → CSV + XLSX (openpyxl)                |

---

## Project layout

```
ants_smart_drone/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry
│   │   ├── config.py            # Env-driven settings
│   │   ├── schemas.py           # Pydantic models
│   │   ├── api/
│   │   │   ├── jobs.py          # Upload / status / result / download
│   │   │   └── websocket.py     # Live progress
│   │   ├── services/
│   │   │   ├── job_manager.py   # In-memory job registry (swap for Redis)
│   │   │   ├── storage.py       # Filesystem paths (swap for S3)
│   │   │   ├── events.py        # Pub/sub for WS
│   │   │   └── processor.py     # Background job runner
│   │   ├── cv/
│   │   │   ├── detector.py      # YOLOv8 wrapper
│   │   │   ├── tracker.py       # ByteTrack wrapper
│   │   │   ├── counter.py       # Unique counting logic
│   │   │   ├── annotator.py     # Frame overlays
│   │   │   └── pipeline.py      # End-to-end orchestrator
│   │   └── report/
│   │       └── generator.py     # CSV + XLSX
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── page.tsx             # Upload landing
│   │   ├── jobs/[jobId]/page.tsx# Job detail + results
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── components/
│   ├── lib/
│   ├── types/
│   └── package.json
└── README.md
```

---

## Running locally

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows:
. .venv/Scripts/activate
# macOS / Linux:
# source .venv/bin/activate

pip install -r requirements.txt

# First run will auto-download yolov8n.pt (~6 MB) into the working dir.
cp .env.example .env

# Production-style: no file watcher. Use this for any real job,
# especially long videos.
uvicorn app.main:app --port 8000

# Dev-only alternative: reload on code edits, but explicitly ignore
# the storage tree so writing results mid-job doesn't kill the server.
# Do NOT use plain `--reload` — it will restart mid-job when the
# pipeline writes output files, killing the in-flight background task.
# uvicorn app.main:app --reload --reload-dir app --reload-exclude "storage/*" --port 8000
```

API is now live at `http://localhost:8000` (Swagger at `/docs`).

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

The frontend talks to the backend via `NEXT_PUBLIC_API_URL` (defaults to
`http://localhost:8000`). Override in `frontend/.env.local` if needed.

---

## What happens when you upload a video

1. `POST /jobs` accepts a multipart `.mp4`, validates extension + MIME,
   persists it to `storage/uploads/{job_id}.mp4`, registers an in-memory
   job record in state `queued`, and returns `{ job_id }`.
2. FastAPI schedules a background task that runs the CV pipeline.
3. The pipeline streams frames through YOLO → ByteTrack → the counting
   engine, writes an annotated output video, and broadcasts progress
   over the job's WebSocket topic every N frames.
4. On completion the job transitions to `completed` and `result.json`,
   `processed.mp4`, `report.csv`, and `report.xlsx` are written under
   `storage/outputs/{job_id}/`.
5. The UI subscribes to the WS for live progress and fetches the final
   result, renders metric cards, a detections table, and a playable
   processed video.

---

## Unique-counting strategy

Naive "every tracked ID == one vehicle" counting breaks on drone footage
because of occlusions, stationary vehicles, partial re-entry, and flicker
detections. The `cv/counter.py` module enforces:

- **Confirmed tracks only.** A track must accumulate `MIN_HITS_TO_COUNT`
  total hits *and* a `MIN_STREAK` of consecutive frames. Rejects flicker.
- **Displacement gate OR stationary grace.** Either the track has moved
  more than `MIN_DISPLACEMENT_PX` over its trajectory, or it has existed
  for `STATIONARY_GRACE_FRAMES`. This counts a parked car exactly once,
  not zero and not repeatedly.
- **Stable class via majority vote.** Class of record is the mode of all
  observed classes for the track. A car briefly classified as truck does
  not flip the breakdown.
- **Permanent counted-ID set.** Once counted, `tracker_id` is never
  counted again even if ByteTrack's `lost_track_buffer` re-emits it.
- **Soft re-ID fallback.** If a new ID appears within `REID_WINDOW_FRAMES`
  of a lost track, with near-identical last-known centroid and class,
  the new track inherits `counted=True` — an extra safety net on top of
  ByteTrack's own occlusion handling.
- **Optional ROI.** A polygon can be supplied via env / config; only
  tracks whose centroid lies inside the polygon are eligible. Not set
  by default.

All thresholds live in `backend/app/config.py` and can be tuned per
deployment without touching code.

---

## Report contents

Generated per job under `storage/outputs/{job_id}/`:

- `processed.mp4` — annotated output video (bounding boxes, class,
  track ID, lightweight trail).
- `result.json` — machine-readable summary consumed by the frontend.
- `report.csv` / `report.xlsx` — one row per *counted* track:
  - `track_id`
  - `class`
  - `first_seen_frame`, `last_seen_frame`
  - `first_seen_ts`, `last_seen_ts` (seconds)
  - `total_hits`
  - `median_confidence`
  - `counted_at_frame`

Top-of-file metadata in the XLSX includes total unique count, per-class
breakdown, processing duration, video duration, and FPS.

---

## Engineering assumptions

Decisions made where the brief left room for interpretation, documented
so the evaluator can agree or push back:

- **Input format:** only `.mp4` is accepted. Both extension and MIME are
  validated server-side. Other containers (mov, avi, mkv) are rejected
  up front rather than silently transcoded.
- **Vehicle classes:** the counted classes are the four COCO vehicle
  labels — `car`, `motorcycle`, `bus`, `truck` (IDs 2, 3, 5, 7). Other
  COCO classes emitted by YOLO are filtered out to keep the count
  semantically "vehicles only."
- **Frame-level scan, not skip-based.** The pipeline visits every frame.
  Frame skipping was considered as a speed lever but rejected because it
  directly reduces recall on small aerial vehicles and violates the
  brief's "accuracy > speed" spirit. Speed is addressed instead via GPU,
  model size, and `YOLO_IMGSZ`.
- **ROI is pixel-space, not georeferenced.** No homography / GIS layer.
  The polygon is specified in image pixels via `ROI_POLYGON_JSON` and
  matches the orientation of the source frames.
- **Single-process background execution.** `asyncio.create_task` runs the
  pipeline off the event loop via an executor. Concurrent jobs serialize.
  Scaling to Celery / Redis is a deliberate seam, not a rewrite — see
  "Scaling path" below.
- **In-memory job registry.** Restarting the backend clears the registry
  (output files on disk persist). Acceptable for an MVP; production path
  is SQLite or Redis behind the same `JobManager` interface.
- **FPS from video metadata is trusted** for timestamp conversion. If the
  container lies about its fps, reported timestamps are off by the same
  factor. Production systems should reconcile with decoded PTS.
- **GPU is opt-in.** `YOLO_DEVICE=cuda` if available; otherwise `cpu`.
  The same code path runs both; only throughput changes.
- **Browser playback requires ffmpeg** on the backend PATH. OpenCV's
  `mp4v` output isn't decoded by Chrome / Firefox / Safari, so the
  pipeline post-processes to H.264 + yuv420p + faststart. If ffmpeg is
  absent, the UI surfaces a clean "can't decode" message with a
  download link instead of a broken `<video>` element.

---

## Error handling

- Rejects non-`.mp4` uploads and empty files up front.
- Detects corrupt / unopenable videos via OpenCV and fails the job with
  a structured error surfaced in the UI.
- WS clients reconnect with backoff; if the socket never connects the UI
  falls back to polling `GET /jobs/{id}` every 1.5s.
- A crash inside the pipeline transitions the job to `failed` and the
  traceback is logged server-side (truncated message shown client-side).
- Model load failure at boot is surfaced as a 503 on the upload route.

---

## Scaling path (built-in, not implemented end-to-end)

The app is a strong MVP today, but the seams are deliberate:

- `JobManager` is an interface — swap the in-memory impl for Redis.
- `Storage` is path-based; replace with S3 / GCS with no route changes.
- `processor.py` uses `asyncio.create_task`, but exposes a `submit(job)`
  surface that plugs straight into Celery / RQ / Dramatiq.
- The WS pub/sub layer (`events.py`) can be backed by Redis Pub/Sub.
- Pydantic schemas give you an OpenAPI contract already; add auth by
  dropping in a dependency on `/jobs`.
- The frontend has no hard assumptions about a single job in flight —
  `jobs/[jobId]` is already a per-job route, ready for a history list.

---

## Known limitations

- Single-process background task runner. Concurrent uploads run serially
  past the first. This is deliberate for the MVP — see scaling path.
- YOLOv8n is fast but not the most accurate — swap to `yolov8s.pt` or
  `yolov8m.pt` by changing `YOLO_MODEL` in `.env`.
- ROI configuration is config-only for now; no in-UI polygon editor.
- No persistent job history; restarting the backend clears the registry
  (files on disk stay).
- ffmpeg must be on the backend `PATH` for the H.264 transcode step.
  Without it the pipeline still produces `processed.mp4`, but the
  `mp4v` codec isn't decoded by most browsers — the UI surfaces a
  graceful error with a download fallback.

---

## Next improvements (prioritized)

1. Persist job registry to SQLite so the history survives restart.
2. Redis-backed pub/sub + Celery worker for real concurrency.
3. In-UI polygon ROI editor on top of the first video frame.
4. Per-class confidence filters controllable from the UI.
5. Speed estimation using homography + known scene scale.
6. Live processing-ETA during long jobs (based on rolling fps).
