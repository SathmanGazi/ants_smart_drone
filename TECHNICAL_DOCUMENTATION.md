# Smart Drone Traffic Analyzer — Technical Documentation

An end-to-end proof of concept for analyzing aerial / drone video footage:
detect vehicles, track them across frames, count each vehicle exactly once,
render an annotated playback-ready video, and generate downloadable reports.

This document is the full technical write-up: what was built, why each
piece was chosen, how the components fit together, and the most important
engineering decision — **how unique-vehicle counting is kept honest in
the face of occlusions, stationary vehicles, ID switches, and flicker
detections**.

---

## Table of contents

1. [Product goals](#1-product-goals)
2. [Tech stack and rationale](#2-tech-stack-and-rationale)
3. [High-level architecture](#3-high-level-architecture)
4. [Repository layout](#4-repository-layout)
5. [Backend design](#5-backend-design)
6. [Frontend design](#6-frontend-design)
7. [Computer-vision pipeline](#7-computer-vision-pipeline)
8. [Unique-counting strategy (the core of the project)](#8-unique-counting-strategy-the-core-of-the-project)
9. [Diagnostic surface: counted vs rejected tracks](#9-diagnostic-surface-counted-vs-rejected-tracks)
10. [Reporting](#10-reporting)
11. [Realtime progress over WebSocket](#11-realtime-progress-over-websocket)
12. [Error handling](#12-error-handling)
13. [Performance characteristics](#13-performance-characteristics)
14. [Scaling path](#14-scaling-path)
15. [Known limitations](#15-known-limitations)
16. [Future improvements](#16-future-improvements)
17. [Local setup](#17-local-setup)
18. [Interview talking points](#18-interview-talking-points)

---

## 1. Product goals

A drone records aerial road footage. The operator wants:

- A de-duplicated **unique** vehicle count.
- A breakdown by vehicle class (car, truck, bus, motorcycle).
- An annotated video showing the detections, track IDs, and a live HUD.
- A structured report (CSV + XLSX) for downstream spreadsheets / BI tools.
- Confidence that the count is not double-counting due to occlusions,
  stops, or tracker ID switches.

Non-goals for this MVP: speed estimation, trajectory forecasting, ReID
across distinct videos, multi-camera fusion.

---

## 2. Tech stack and rationale

| Layer         | Choice                          | Why                                                                 |
|---------------|---------------------------------|---------------------------------------------------------------------|
| Frontend      | Next.js 14 (App Router) + TS    | Typed client, colocated routes, SSR-ready, ships a single bundle.   |
| Styling       | Tailwind CSS                    | Fast, deterministic styling without a design system dependency.     |
| Backend       | FastAPI + Pydantic v2           | Async, type-driven validation, OpenAPI out of the box.              |
| Realtime      | Native WebSocket                | No extra broker needed for MVP; drop-in replaceable with Redis.     |
| Detection     | Ultralytics YOLOv8 (`yolov8n`)  | Accurate, fast, trivial install, strong COCO coverage incl. vehicles. |
| Tracking      | ByteTrack via `supervision`     | SOTA MOT, no extra ReID model, handles brief occlusions by design.  |
| Video I/O     | OpenCV                          | Battle-tested decode/encode and per-frame control.                  |
| Post-encoding | ffmpeg (H.264, yuv420p, faststart) | Guarantees browser-playable MP4 regardless of OpenCV codec quirks. |
| Reporting     | pandas + openpyxl               | CSV and multi-sheet XLSX with one API.                              |

**Why not Streamlit / Gradio / Dash?** Those are fine for one-off demos
but force a single-process model and make architecture decisions for
you. The separation of Next.js frontend from FastAPI backend preserves
a clear HTTP/WS contract and lets the two scale independently.

**Why YOLOv8n (the nano variant)?** Good accuracy for cars/trucks/buses
at drone altitudes, ~6 MB weights, and fast CPU inference. Upgrading to
`yolov8s` or `yolov8m` is a single env var change (`YOLO_MODEL`).

**Why ByteTrack?** Its trick is associating low-confidence detections
with existing tracks *before* opening new ones, which is exactly the
regime drone footage lives in (partial occlusions, small far-away cars).
It also has a configurable `lost_track_buffer` so the same ID survives
~1 second of occlusion without a ReID model.

---

## 3. High-level architecture

```
┌───────────────────────┐      HTTP(S)        ┌───────────────────────────┐
│                       │  POST /jobs         │                           │
│   Next.js frontend    │ ─────────────────▶  │     FastAPI backend       │
│  (App Router + TS)    │  GET  /jobs/{id}/…  │   ┌─────────────────────┐ │
│                       │ ◀─────────────────  │   │  API routes         │ │
│  Uploader             │                     │   │  /jobs /ws/jobs/{id}│ │
│  JobProgress (WS)     │      WebSocket      │   └─────────┬───────────┘ │
│  ResultsPanel         │◀═══════════════════▶│             ▼             │
│  RejectionsPanel      │    live progress    │   ┌─────────────────────┐ │
│                       │                     │   │  Event broker       │ │
└───────────────────────┘                     │   │  (pub/sub, in-mem)  │ │
                                              │   └─────────┬───────────┘ │
                                              │             ▼             │
                                              │   ┌─────────────────────┐ │
                                              │   │  Job manager        │ │
                                              │   │  (in-memory reg.)   │ │
                                              │   └─────────┬───────────┘ │
                                              │             ▼             │
                                              │   ┌─────────────────────┐ │
                                              │   │  Processor          │ │
                                              │   │  (asyncio + exec.)  │ │
                                              │   └─────────┬───────────┘ │
                                              │             ▼             │
                                              │   ┌─────────────────────┐ │
                                              │   │  CV pipeline        │ │
                                              │   │  detector→tracker→  │ │
                                              │   │  counter→annotator  │ │
                                              │   └─────────┬───────────┘ │
                                              │             ▼             │
                                              │   ┌─────────────────────┐ │
                                              │   │  ffmpeg (H.264)     │ │
                                              │   └─────────┬───────────┘ │
                                              │             ▼             │
                                              │   ┌─────────────────────┐ │
                                              │   │  Report (CSV/XLSX)  │ │
                                              │   └─────────────────────┘ │
                                              └───────────────────────────┘
                                                        │
                                                        ▼
                                              storage/outputs/{job_id}/
                                                processed.mp4
                                                result.json
                                                report.csv
                                                report.xlsx
```

**Data flow for a single job**

1. Browser `POST /jobs` with multipart MP4.
2. Backend validates, persists to `storage/uploads/{job_id}.mp4`,
   registers a `JobRecord(status=queued)` in memory, schedules
   `processor.run_job(job_id)` via `asyncio.create_task`, returns
   `{job_id}`.
3. Frontend routes to `/jobs/{job_id}` and opens WS `ws/jobs/{job_id}`.
4. Worker moves `status=processing`, pushes `{type:"status"}` and
   periodic `{type:"progress"}` messages to the broker, which fans out
   to every subscribed WS.
5. Pipeline writes `processed.mp4` (mp4v), then ffmpeg transcodes to
   H.264/yuv420p/faststart.
6. Reports written (CSV + XLSX with 5 sheets).
7. Status flips to `completed`; WS broadcasts it; UI fetches
   `/jobs/{id}/result` and renders metrics, video, tables.

---

## 4. Repository layout

```
ants_smart_drone/
├── backend/
│   ├── app/
│   │   ├── main.py                      # FastAPI entry, CORS, routers, /health
│   │   ├── config.py                    # Pydantic Settings, env → runtime knobs
│   │   ├── schemas.py                   # API-level Pydantic models
│   │   ├── api/
│   │   │   ├── jobs.py                  # POST /jobs + 5 GET endpoints
│   │   │   └── websocket.py             # /ws/jobs/{job_id}
│   │   ├── services/
│   │   │   ├── job_manager.py           # In-memory registry, async-safe
│   │   │   ├── storage.py               # Filesystem path abstraction
│   │   │   ├── events.py                # Pub/sub broker for WS
│   │   │   └── processor.py             # Background orchestrator
│   │   ├── cv/
│   │   │   ├── detector.py              # YOLOv8 wrapper, COCO vehicle filter
│   │   │   ├── tracker.py               # ByteTrack via supervision
│   │   │   ├── counter.py               # Unique-count engine (the core)
│   │   │   ├── annotator.py             # Overlays, HUD, ROI shading, trails
│   │   │   ├── encode.py                # ffmpeg H.264 transcode
│   │   │   └── pipeline.py              # End-to-end per-video orchestrator
│   │   └── report/
│   │       └── generator.py             # CSV + 5-sheet XLSX
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── layout.tsx                   # Shell, header, footer
│   │   ├── page.tsx                     # Upload landing
│   │   ├── jobs/[jobId]/page.tsx        # Live job + results
│   │   └── globals.css                  # Tailwind layers, panel utility classes
│   ├── components/
│   │   ├── Uploader.tsx                 # Drag-and-drop, validation, upload progress
│   │   ├── JobProgress.tsx              # Live progress + status badge
│   │   ├── MetricsCards.tsx             # KPI cards
│   │   ├── DetectionsTable.tsx          # Counted tracks + filter/search
│   │   ├── RejectionsPanel.tsx          # Diagnostic collapsible
│   │   ├── ResultsPanel.tsx             # Video + downloads + tables
│   │   └── StatusBadge.tsx
│   ├── lib/
│   │   ├── api.ts                       # Typed client, upload helper
│   │   ├── useJobSocket.ts              # WS hook with backoff reconnect
│   │   └── format.ts                    # Small formatting utils
│   └── types/index.ts                   # Shared TS types mirroring backend schemas
├── TECHNICAL_DOCUMENTATION.md           # (this file)
└── README.md
```

---

## 5. Backend design

### 5.1 Module boundaries

The backend is deliberately split into five concerns, each a separate
file:

- **API routes** speak HTTP/WS, do no business logic beyond validation.
- **Services** own process-wide state: job registry, event bus,
  filesystem paths, the task orchestrator.
- **CV** is pure domain logic; it takes a file path in and emits a
  result. No knowledge of HTTP, jobs, or WebSockets.
- **Report** is side-effect code that serializes results to disk.
- **Schemas** are the typed contract between API and clients.

This means you could import `app.cv.pipeline.VideoPipeline` from a CLI,
a batch script, or a Celery worker without pulling any web framework.

### 5.2 Configuration

`app/config.py` is a Pydantic `BaseSettings`. All runtime knobs (model
name, confidence threshold, counting gates, ROI polygon, CORS origins,
max upload size) come from environment variables with safe defaults.
This gives us a single source of truth for tunables with zero code
changes required for per-deployment customization.

Examples:

- `YOLO_MODEL=yolov8s.pt` → upgrade detector accuracy.
- `MIN_HITS_TO_COUNT=10` → stricter counting (reject more flickers).
- `ROI_POLYGON_JSON=[[80,260],[1500,260],[1500,980],[80,980]]` → only
  count in a polygon.

### 5.3 Job manager

`services/job_manager.py` implements a minimal interface:

```python
create(filename)        -> JobRecord
get(job_id)             -> JobRecord | None
set_status(job_id, …)   -> JobRecord | None
set_progress(job_id, …) -> None
```

For the MVP this is an in-process dict protected by an `asyncio.Lock`.
Swapping to Redis / Postgres is a file change — API routes call only
the four methods above.

### 5.4 Event broker

`services/events.py` is an in-process fan-out:

```python
broker.subscribe(topic) -> asyncio.Queue
broker.unsubscribe(topic, queue)
broker.publish(topic, payload)
```

The processor publishes; each WS connection subscribes to its own
`job_id` topic. Slow consumers drop their oldest message (bounded
queue) rather than back up the producer. Identical interface maps 1:1
to Redis Pub/Sub when we go multi-process.

### 5.5 Processor

`services/processor.py` owns a job lifecycle. For the MVP it uses
`loop.create_task(run_job(job_id))` to run asynchronously within the
FastAPI process. Inside:

- Mark `processing`, broadcast status.
- Launch `VideoPipeline.run()` via `run_in_executor(None, …)` — the
  CV work is CPU-bound, so we get it off the event loop.
- Upon success, emit an explicit `percent=100.0` progress event (so
  the UI bar snaps shut even when cv2's frame count over-reports).
- Run the H.264 transcode (also via executor).
- Generate CSV and XLSX.
- Mark `completed`, broadcast.

On any exception: catch, log traceback, mark `failed`, broadcast the
error message, never crash the process.

### 5.6 API routes

```
POST /jobs                       → upload MP4, schedule processing
GET  /jobs/{id}                  → JobRecord (status + progress)
GET  /jobs/{id}/result           → JobResult (metrics + tables + URLs)
GET  /jobs/{id}/video            → H.264 processed.mp4 with Range support
GET  /jobs/{id}/report.csv       → per-track CSV
GET  /jobs/{id}/report.xlsx      → multi-sheet XLSX
WS   /ws/jobs/{id}               → live status + progress events
GET  /health                     → liveness
```

Upload does multipart streaming (not `await file.read()`): we stream
chunks into a file on disk, enforcing `MAX_UPLOAD_MB` incrementally so
we don't OOM on huge uploads.

---

## 6. Frontend design

### 6.1 Routes and components

Two pages:

- `app/page.tsx` — landing with the `Uploader`. Validates extension,
  file size, and emptiness client-side before we even hit the wire.
- `app/jobs/[jobId]/page.tsx` — live job view. Fetches `JobRecord` on
  mount, opens a WebSocket, falls back to polling `/jobs/{id}` every
  1.5s if the socket never connects, fetches `/jobs/{id}/result` once
  status flips to `completed`.

Key components:

- `Uploader` — drag-and-drop, `XMLHttpRequest`-based upload so we can
  report real upload percentage.
- `JobProgress` — status badge, progress bar, reconnect indicator.
- `MetricsCards` — KPI tiles (total unique, processing time, top class,
  breakdown).
- `DetectionsTable` — counted tracks with class filter and id/class
  search, sticky header, virtual-scroll-friendly.
- `RejectionsPanel` — collapsible diagnostic surface (see §9).
- `ResultsPanel` — ties the video player + downloads + tables together
  and shows a fallback error card if the browser can't decode the
  processed video (missing ffmpeg on backend).

### 6.2 WebSocket hook

`lib/useJobSocket.ts` handles:

- Exponential backoff reconnect (up to 10 s).
- `snapshot` replay (server sends current state on connect so late
  subscribers don't miss anything).
- `progress` / `status` / `error` message dispatch.
- 20-second application-level pings to keep NAT/proxy paths warm.

### 6.3 Failure UX

- Non-MP4 / empty / too-large uploads show inline errors, no router
  push.
- Non-existent job IDs show a "Couldn't load job" panel with a back
  link.
- `failed` jobs render the server-provided error string in a red panel
  with a "Try another file" link.
- If the processed `<video>` emits an `error` event, we overlay a
  readable message with a direct download link and guidance on
  installing ffmpeg.

---

## 7. Computer-vision pipeline

`cv/pipeline.py::VideoPipeline.run()` is the single entry point. Per
frame:

```
frame ──▶ VehicleDetector.infer ──▶ VehicleTracker.update ──▶
         RawDetection                supervision.Detections (with tracker_id)
                                         │
                                         ▼
                                  UniqueVehicleCounter.update
                                         │
                                         ▼
                                FrameAnnotator.annotate ──▶ VideoWriter
```

- `VehicleDetector` loads YOLO once per process (class-level memoization).
  It restricts results to COCO IDs `{2 car, 3 motorcycle, 5 bus, 7 truck}`.
- `VehicleTracker` wraps supervision's ByteTrack with fps-aware
  parameters: `lost_track_buffer = max(30, fps * 1.0)` frames lets a
  track survive ~1 s of occlusion.
- `UniqueVehicleCounter` is the interesting one — see §8.
- `FrameAnnotator` draws bounding boxes color-coded per class, track
  IDs, class labels with median confidence, a fading motion trail, a
  live HUD (unique count + per-class tallies), a progress bar, and the
  configured ROI polygon as a faint overlay so you can audit the mask
  visually.

Every decoded frame is written to the output writer (even when skipped
by `FRAME_STRIDE > 1`) so the output video's duration matches the input.

After the loop, ffmpeg transcodes `processed.mp4` from `mp4v` to
H.264/yuv420p/faststart in-place — the only reliable way to guarantee
HTML5 `<video>` playback across Chrome/Firefox/Safari.

---

## 8. Unique-counting strategy (the core of the project)

### 8.1 Why naive counting fails

"Count every unique `tracker_id` you see" breaks immediately on drone
footage because:

1. **Flicker detections** — YOLO sometimes fires a one-frame box at a
   road edge. ByteTrack dutifully opens a track, gives it an ID, and
   closes it on the next frame. Count +1 for noise.
2. **Edge flashes** — a car half-entering the frame for 2 frames.
3. **Occlusion → new ID** — ByteTrack's buffer isn't infinite. If a car
   passes under a bridge or behind a truck for 2 s at 30 fps, its ID
   gets retired and a fresh ID is assigned when it re-emerges. Count
   +1 for the same vehicle.
4. **Stationary vehicles** — a parked car may be detected every frame
   for the whole clip, producing many small bounding boxes with tiny
   jitter. Should count as 1, not per ID churn.
5. **Class instability** — YOLO briefly classifies a bus as a truck or
   vice versa on occasion. Breakdown would flip.

### 8.2 TrackState

For every tracker ID we maintain a `TrackState`:

```
track_id            : int
first_frame         : int
last_frame          : int
total_hits          : int            # cumulative frames seen
hit_streak          : int            # consecutive frames of the latest run
class_votes         : Counter[int]   # majority-vote class
confidences         : list[float]    # for median
trajectory          : deque[(x,y)]   # last 64 centroids
counted             : bool
counted_at_frame    : int | None
inherited           : bool           # reincarnated from a lost counted track
```

### 8.3 Counting gate

`_should_count(state)` returns True iff **all** of:

1. `total_hits ≥ MIN_HITS_TO_COUNT` (default 6 frames ≈ 0.25 s @ 24 fps).
2. `hit_streak ≥ MIN_STREAK` (default 3). Rejects single-frame flickers
   with intermittent false positives.
3. Movement requirement: either **trajectory displacement ≥
   `MIN_DISPLACEMENT_PX`** (default 35 px) **or** **track age ≥
   `STATIONARY_GRACE_FRAMES`** (default 60 frames ≈ 2 s).
   - Moving cars are counted once displacement crosses the threshold.
   - Parked / slow cars are counted exactly once after they've been
     stable for long enough, *not* every time their track ID churns.

If counted, the ID is added to a permanent `counted_ids` set. ByteTrack
may later kill and re-activate that exact ID (its internal lost-track
buffer does this); the counter still refuses to count it again because
the state object persists.

### 8.4 Class assignment

The reported class per track is **the mode over the track's lifetime**,
not the class at counting time. This prevents a one-frame
misclassification from polluting the breakdown. Concretely: the first
time YOLO says "truck" for a vehicle that becomes "car" for the next
50 frames, we vote car.

### 8.5 Soft re-ID across ByteTrack misses

ByteTrack's `lost_track_buffer` handles short occlusions. Beyond that,
the same vehicle gets a *new* ID. Without a ReID model we can't
recognize it by appearance. But we can still catch this case
heuristically:

When a new tracker_id is born, if there is a recently-lost counted
track whose last known centroid is within `REID_DISTANCE_PX` (default
60 px) and whose class matches, the new track **inherits** `counted=True`
and is marked `inherited=True`.

Effect: we don't issue a *new* count for what is almost certainly the
same vehicle. The inherited flag excludes this ghost row from the
report (see §9 on why this flag was added).

### 8.6 Optional ROI

A polygon in pixel coordinates can be provided via `ROI_POLYGON_JSON`.
Tracks whose centroid sits outside the polygon never pass the counting
gate. Useful to ignore:

- A side bridge visible in the frame where the operator doesn't want
  counts.
- An adjacent train track where nearby vehicles cause confusion.
- The very edges of the frame where half-vehicles flicker in and out.

The counter uses standard ray-casting for point-in-polygon. The
annotator renders the polygon as a faint outline on every frame so
you can visually audit the mask.

### 8.7 Config summary

Every knob is overridable via `.env`:

```
MIN_HITS_TO_COUNT=6          # lifetime frames required
MIN_STREAK=3                 # consecutive frames required
MIN_DISPLACEMENT_PX=35       # trajectory displacement to count a moving vehicle
STATIONARY_GRACE_FRAMES=60   # grace to count a parked vehicle
REID_WINDOW_FRAMES=30        # window to associate a fresh ID with a lost track
REID_DISTANCE_PX=60          # spatial tolerance for soft re-ID
ROI_POLYGON_JSON=…           # optional counting mask
```

---

## 9. Diagnostic surface: counted vs rejected tracks

A correctness-first counter can still feel opaque ("why was track 7
missing?"). To close that loop the counter also exposes a full
**rejection report**:

- Every `TrackState` with `counted=False` → one row.
- Each row includes the rejection reason evaluated post-run:
  `total_hits<6`, `streak<3`, or `displacement<35px & age<60f`.
- Aggregated `rejection_summary: {reason: count}` is included in the
  JSON result and as a dedicated XLSX sheet.
- The frontend renders a collapsible `RejectionsPanel` under the
  counted-tracks table so you can quickly audit what the filter is
  tossing.

This serves two purposes:

1. **Correctness audit.** If the rejected set is dominated by
   `total_hits<6` and the median confidence is low, the filter is doing
   its job. If you see real long-lived moving vehicles in the reject
   list, that's a signal to loosen thresholds.
2. **Interview / demo clarity.** The missing IDs you asked about
   (7, 9, 12, …) are no longer mysterious — every one of them has a
   machine-readable reason it didn't pass.

---

## 10. Reporting

### 10.1 `result.json`

Written to `storage/outputs/{job_id}/result.json`. This is the
machine-readable source of truth the API serves:

```json
{
  "total_unique": 37,
  "by_class": {"car": 36, "truck": 1},
  "processing_duration_sec": 20.42,
  "video_duration_sec": 10.18,
  "fps": 29.97,
  "total_frames": 302,
  "counted_tracks":   [ …TrackReport… ],
  "rejected_tracks":  [ …RejectedTrack… ],
  "rejection_summary": { "total_hits<6": 14, "streak<3": 4, … },
  "sample_detections": [ …DetectionRow… ]
}
```

### 10.2 `report.csv`

One row per counted track with `track_id, vehicle_class,
first_seen_frame, last_seen_frame, first_seen_ts, last_seen_ts,
total_hits, median_confidence, counted_at_frame`. Directly
spreadsheet-usable.

### 10.3 `report.xlsx` (five sheets)

| Sheet                 | Content                                                         |
|-----------------------|-----------------------------------------------------------------|
| Summary               | Source file, total unique, rejected count, durations, fps       |
| By class              | Counts per class                                                |
| Counted tracks        | Same rows as the CSV                                            |
| Rejections summary    | Reject reason → number of tracks                                |
| Rejected tracks       | Per-reject detail incl. displacement and reason                 |

---

## 11. Realtime progress over WebSocket

- Connection: `ws/jobs/{job_id}`.
- On accept, the server sends `{type:"snapshot", status, progress,
  error}` so a late subscriber gets current state immediately.
- During processing the CV loop calls `progress_cb(frame, total, fps)`
  every `PROGRESS_EVERY_N_FRAMES` frames (default 10). The callback
  uses `asyncio.run_coroutine_threadsafe` to marshal a `JobProgress`
  publish back onto the main loop — the pipeline itself runs in a
  worker thread via `run_in_executor`.
- On completion: an explicit `percent=100.0` progress event is
  broadcast *before* the `completed` status, so the bar visibly fills.
- On failure: `{type:"status", status:"failed", error}`.

Client side, `useJobSocket` reconcilies these into component state and
exposes a connection indicator. If the socket can't connect at all, the
page transparently polls `/jobs/{id}` every 1.5 s.

---

## 12. Error handling

| Scenario                           | Handling                                                                  |
|------------------------------------|---------------------------------------------------------------------------|
| Non-MP4 upload                     | 400 with message `Only .mp4 uploads are supported.`                       |
| Unexpected content-type            | 400                                                                       |
| Empty file                         | 400, upload deleted                                                       |
| File exceeds `MAX_UPLOAD_MB`       | 413, partial file deleted                                                 |
| Upload stream crash                | 500, partial file deleted                                                 |
| Corrupt / unopenable video         | `RuntimeError` → job `failed`, message surfaced in UI                     |
| Video metadata missing             | Same                                                                      |
| Model load failure                 | 503 on first `POST /jobs` (detector initializes lazily)                   |
| WS disconnect (network / tab sleep) | Client auto-reconnect w/ backoff; server re-sends snapshot on reconnect  |
| Processing exception               | Caught, traceback logged, job `failed`, truncated error on client        |
| Missing processed video on disk    | 404, UI shows "Couldn't load result"                                      |
| Browser can't decode processed MP4 | `<video onError>` overlay with download link + install-ffmpeg guidance   |

No exception path takes down the server process.

---

## 13. Performance characteristics

For the Road Traffic Dataset 01 (~10 s, 302 frames, 29.97 fps):

- Inference + tracking + annotation: ~20 s on CPU with `yolov8n`.
- ~15 fps processing throughput on a modern laptop CPU.
- ffmpeg transcode: <1 s.
- Total end-to-end job time: ~21 s.

Swapping to `yolov8s` roughly doubles inference cost but noticeably
improves recall on small far-away vehicles. GPU inference (set
`YOLO_DEVICE=cuda:0`) is a single env change and delivers 3–10×
speedups depending on hardware.

---

## 13b. Long videos (30–50 min and beyond)

The pipeline is streaming by construction — frames are decoded,
processed, annotated, and written one at a time. Nothing about the
algorithm assumes a short clip. In practice there are four knobs you
care about for long inputs:

### Throughput (the dominant cost)

On CPU with `yolov8n`: ~15 fps. A 50-min 30-fps clip is ~90k frames,
so ~100 min of wall-clock processing. Two ways to fix:

- **GPU**: set `YOLO_DEVICE=cuda:0`. Typical 3–10× speedup. The only
  change needed.
- **Frame stride**: `FRAME_STRIDE=2` halves inference cost. Acceptable
  for most drone footage because vehicles rarely change state
  meaningfully in 33 ms. Every decoded frame is still written to the
  output (so output duration is preserved), but detections only run on
  every Nth frame.

### Upload size

Default `MAX_UPLOAD_MB=8192` (8 GB). Uploads stream to disk in 1 MB
chunks with a byte-accurate cap — we never buffer the whole file in
memory. Frontend validation is aligned to the same limit. Bump both
for larger files or set lower for restricted deployments.

### Memory safety for tracks alive across the whole clip

A track seen in every frame of a 50-min clip would otherwise accrue 90k
confidences and unbounded state. Mitigations:

- `TrackState.confidences` is a bounded deque (`maxlen=512`). Median
  over a 512-sample reservoir is within ~1% of the true median.
- `TrackState.trajectory` is a bounded deque (`maxlen=64`) — only the
  recent trajectory matters for displacement gating.
- `sample_detections` in the result payload is capped at 1000 rows.
- `counted_ids` set is O(counted-tracks), expected to stay small
  relative to total frames.

### Progress traffic

Without throttling, 90k frames at `PROGRESS_EVERY_N_FRAMES=10` would
publish 9k WebSocket messages. The pipeline now throttles adaptively:
it emits at most once per `PROGRESS_EVERY_N_FRAMES` frames **and** at
least every 0.5 s wall-clock. You get a smooth progress bar regardless
of clip length, without flooding subscribers.

### ffmpeg transcode

50 min of annotated 1080p output transcodes in a couple of minutes
with `-preset veryfast` on modern CPUs. It runs on the executor pool
so it doesn't block FastAPI. If you need it faster, set
`-preset ultrafast` in [app/cv/encode.py](backend/app/cv/encode.py) at
the cost of larger files.

### Realistic long-video profile

| Clip     | Frames  | CPU (n)  | GPU (n)  | Output size (approx) |
|----------|---------|----------|----------|----------------------|
| 10 min   | 18,000  | ~20 min  | ~3 min   | 300–600 MB           |
| 30 min   | 54,000  | ~60 min  | ~8 min   | 1–2 GB               |
| 50 min   | 90,000  | ~100 min | ~14 min  | 2–3 GB               |

Strong recommendation: once clips exceed ~15 min, run the backend on a
box with a CUDA GPU and set `YOLO_DEVICE=cuda:0`. The rest of the
stack does not need to change.

---

## 14. Scaling path

Everything in the MVP is deliberately structured so the scale-out work
is a series of drop-in replacements:

| Today (MVP)                                   | Scale-out                                            |
|-----------------------------------------------|------------------------------------------------------|
| `JobManager` in-memory dict                   | Redis hash or Postgres row                           |
| `EventBroker` in-process asyncio queues       | Redis Pub/Sub (same publish/subscribe API)           |
| `asyncio.create_task(run_job)`                | Celery / RQ / Dramatiq task; same call site          |
| `Storage` local filesystem                    | S3 / GCS; same path-returning methods                |
| Single uvicorn worker                         | Multi-worker behind nginx; broker now shared         |
| No auth                                       | `Depends(require_user)` on `/jobs` routes            |
| No job history                                | Page paginated over the registry                     |
| Local ffmpeg subprocess                       | Celery worker on a GPU node w/ ffmpeg installed      |

The point is that no API route or frontend component needs to change
when any of those rows are swapped.

---

## 14b. Operational gotcha: `uvicorn --reload`

Do not run the backend with `--reload` during real processing. The
reloader watches the working directory and restarts on file changes —
including the output files the pipeline writes (`processed.mp4`,
`result.json`, `report.csv/xlsx`). A mid-job restart kills the async
background task and the job disappears from the registry, leaving the
UI stuck on the last progress tick and the WS disconnected.

For any real run:

```bash
uvicorn app.main:app --port 8000
```

For dev with source-file auto-restart, narrow the watcher:

```bash
uvicorn app.main:app --reload --reload-dir app \
        --reload-exclude "storage/*" --port 8000
```

The underlying design issue (in-process background tasks dying with
the server) is the same reason the scaling path lists Celery / RQ as
the first upgrade — a separate worker process is isolated from a web
server restart.

---

## 15. Known limitations

1. **Single-process task runner.** Concurrent uploads are serialized
   after the first. This is documented and intentional — the hook for
   a real queue is already in place.
2. **No persistent job history.** Restarting the backend clears the
   registry. Files on disk survive.
3. **ROI is config-only.** The polygon is edited in `.env`, not drawn
   in the UI.
4. **No ReID across videos.** Tracking is per-file. A car leaving the
   frame and re-entering later in a *different* clip is a new vehicle
   to us.
5. **`yolov8n` can miss very small vehicles.** Upgrade to `yolov8s`/`m`
   for better small-object recall.
6. **No audio.** ffmpeg transcode drops the audio track (`-an`) —
   traffic analysis doesn't need it and it simplifies the pipeline.
7. **CPU inference is slow for long clips.** Set `YOLO_DEVICE` to a
   CUDA device when available.

---

## 16. Future improvements

Ordered by value/effort:

1. Persist job registry to SQLite → survives restarts, minimal code.
2. In-UI polygon ROI editor drawn on the first frame of the uploaded
   video.
3. Swap asyncio task → Celery worker; unlock real concurrency and a
   dedicated GPU worker pool.
4. ReID model (e.g. `torchreid`) to cut the `REID_DISTANCE_PX`
   dependency and catch longer occlusions robustly.
5. Per-class confidence sliders in the UI with a preview run on the
   first N seconds.
6. Speed estimation via homography if we know the road scale, plus a
   virtual-line crossing counter for cleaner per-direction tallies.
7. Multi-video batch mode (upload folder → one combined report).
8. Docker compose setup (backend + frontend + a fake object store) for
   reproducible demos.
9. Unit tests for `UniqueVehicleCounter` using synthetic tracker output
   (flicker, stationary, ID-swap, occlusion cases) — this is
   deterministic logic, trivial to pin down with tests.

---

## 17. Local setup

### Prerequisites

- Python 3.10+ (tested on 3.11).
- Node.js 18+.
- ffmpeg on `PATH` (Windows: `winget install ffmpeg`).

### Backend

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate      # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

First run downloads `yolov8n.pt` (~6 MB) into the working directory.

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # optional; defaults point to localhost:8000
npm run dev
```

Open <http://localhost:3000>, drop in a `.mp4`, watch it work.

---

## 18. Interview talking points

**Pitch in one sentence:**
"A full-stack aerial-video analytics service: Next.js + FastAPI, YOLOv8 +
ByteTrack, with a purpose-built unique-counting engine that refuses to
double-count under occlusions, stationary vehicles, and tracker ID
switches — and exposes its reasoning via a rejection report."

**Architecture angle:**
Talk about the clean split of API / services / CV / report. The fact
that every service seam is a drop-in replacement for a scale-out
component (job manager → Redis, processor → Celery, storage → S3,
event broker → Redis Pub/Sub). Nothing in the API or the frontend has
to change to scale.

**The interesting engineering:**
The counting logic. It's not "YOLO and count distinct IDs" — it's a
state machine per track with four gates, a soft re-ID fallback, a
permanent counted-ID set, and majority-vote class assignment. Plus a
first-class diagnostic pathway (the rejections panel and XLSX sheet)
because counter correctness without observability is just a number on
a screen.

**Two war stories you can tell:**

1. *The "stuck at 99%" bug.*
   `cv2.CAP_PROP_FRAME_COUNT` over-reports by 1–2 frames; the
   processor now emits an explicit `100%` progress event before the
   `completed` status, and the UI clamps the bar when status flips.
2. *The ghost-row bug in the soft re-ID path.*
   A track inheriting `counted=True` prevented a recount (good) but
   was still emitted as its own row in the report (bad). Fix was the
   `inherited` flag: counted for suppression purposes, filtered out of
   the summary. Caught by reading the CSV — user spotted a track with
   `total_hits=1, counted_at_frame=301`, which should have been
   impossible under the stated gates.

**Ship-ability:**
Runs locally end-to-end with one command per side. Gracefully degrades
when ffmpeg is missing. Error states are real, not "something went
wrong". Every config value is an env var.
