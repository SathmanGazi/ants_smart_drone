import { Uploader } from "@/components/Uploader";

export default function HomePage() {
  return (
    <div className="space-y-10">
      <section className="max-w-2xl">
        <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight">
          Analyze drone traffic footage.
        </h1>
        <p className="mt-3 text-surface-muted">
          Upload a single <span className="kbd">.mp4</span> clip. The backend
          runs YOLOv8 detection and ByteTrack across every frame, counts each
          unique vehicle exactly once, and produces an annotated video plus a
          downloadable report.
        </p>
      </section>

      <section>
        <Uploader />
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        <InfoCard
          title="Robust counting"
          body="Unique-ID logic with confirmed tracks, displacement gates, stationary grace, and soft re-identification across brief occlusions."
        />
        <InfoCard
          title="Live progress"
          body="Frame-accurate progress is pushed over WebSockets while the pipeline runs, with automatic reconnection."
        />
        <InfoCard
          title="Exportable reports"
          body="Per-track CSV and a multi-sheet XLSX summarize counts, timestamps, and class breakdown."
        />
      </section>
    </div>
  );
}

function InfoCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="panel p-5">
      <h3 className="font-medium">{title}</h3>
      <p className="text-sm text-surface-muted mt-1.5 leading-relaxed">{body}</p>
    </div>
  );
}
