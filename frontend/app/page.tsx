import { Uploader } from "@/components/Uploader";
import { BackgroundBeams } from "@/components/ui/background-beams";
import { TextGenerateEffect } from "@/components/ui/text-generate-effect";
import { HoverEffect } from "@/components/ui/card-hover-effect";

const INFO_ITEMS = [
  {
    title: "Robust counting",
    description:
      "Unique-ID logic with confirmed tracks, displacement gates, stationary grace, and soft re-identification across brief occlusions.",
  },
  {
    title: "Live progress",
    description:
      "Frame-accurate progress is pushed over WebSockets while the pipeline runs, with automatic reconnection.",
  },
  {
    title: "Exportable reports",
    description:
      "Per-track CSV and a multi-sheet XLSX summarize counts, timestamps, and class breakdown.",
  },
];

export default function HomePage() {
  return (
    <div className="space-y-10">
      <section className="relative max-w-2xl py-6 overflow-hidden rounded-2xl">
        <BackgroundBeams />
        <div className="relative z-10">
          <TextGenerateEffect words="Analyze drone traffic footage." />
          <p className="mt-3 text-surface-muted">
            Upload a single <span className="kbd">.mp4</span> clip. The backend
            runs YOLOv8 detection and ByteTrack across every frame, counts each
            unique vehicle exactly once, and produces an annotated video plus a
            downloadable report.
          </p>
        </div>
      </section>

      <section>
        <Uploader />
      </section>

      <section>
        <HoverEffect items={INFO_ITEMS} />
      </section>
    </div>
  );
}
