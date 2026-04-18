import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Smart Drone Traffic Analyzer",
  description:
    "Upload drone footage, detect and track vehicles, and export per-track reports.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen flex flex-col">
          <header className="border-b border-surface-border bg-surface/60 backdrop-blur sticky top-0 z-20">
            <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
              <a href="/" className="flex items-center gap-2.5 group">
                <span className="w-7 h-7 rounded-lg bg-gradient-to-br from-brand to-brand-emerald grid place-items-center text-slate-950 font-bold text-sm shadow-panel">
                  S
                </span>
                <span className="font-semibold tracking-tight">
                  Smart Drone Traffic Analyzer
                </span>
              </a>
              <span className="text-xs text-surface-muted hidden sm:block">
                aerial · detection · tracking · counting
              </span>
            </div>
          </header>
          <main className="flex-1">
            <div className="max-w-6xl mx-auto px-6 py-10">{children}</div>
          </main>
          <footer className="border-t border-surface-border text-xs text-surface-muted">
            <div className="max-w-6xl mx-auto px-6 py-4 flex justify-between">
              <span>MVP · local processing</span>
              <span>YOLOv8 · ByteTrack</span>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
