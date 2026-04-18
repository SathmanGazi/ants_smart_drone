import { formatDuration } from "@/lib/format";
import type { JobResult } from "@/types";

interface Props {
  result: JobResult;
}

function Card({
  label,
  value,
  hint,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
}) {
  return (
    <div className="panel p-5">
      <div className="text-xs uppercase tracking-wider text-surface-muted">
        {label}
      </div>
      <div className="text-3xl font-semibold mt-1.5 tabular-nums">{value}</div>
      {hint && <div className="text-xs text-surface-muted mt-2">{hint}</div>}
    </div>
  );
}

export function MetricsCards({ result }: Props) {
  const classBreakdown = Object.entries(result.by_class)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <Card
        label="Unique vehicles"
        value={result.total_unique}
        hint={`across ${result.total_frames} frames`}
      />
      <Card
        label="Processing time"
        value={formatDuration(result.processing_duration_sec)}
        hint={`video ${formatDuration(result.video_duration_sec)} @ ${result.fps.toFixed(
          1
        )} fps`}
      />
      <Card
        label="Top class"
        value={
          classBreakdown[0]
            ? `${classBreakdown[0][0]}`
            : "—"
        }
        hint={
          classBreakdown[0]
            ? `${classBreakdown[0][1]} counted`
            : "no counted vehicles"
        }
      />
      <div className="panel p-5">
        <div className="text-xs uppercase tracking-wider text-surface-muted">
          Breakdown
        </div>
        <ul className="mt-2 space-y-1.5">
          {classBreakdown.length === 0 && (
            <li className="text-sm text-surface-muted">No vehicles counted.</li>
          )}
          {classBreakdown.map(([cls, n]) => (
            <li
              key={cls}
              className="flex items-center justify-between text-sm"
            >
              <span className="capitalize">{cls}</span>
              <span className="tabular-nums font-medium">{n}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
