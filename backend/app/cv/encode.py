from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


_FFMPEG_FALLBACK = (
    r"C:\Users\Musa\AppData\Local\Microsoft\WinGet\Packages"
    r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
    r"\ffmpeg-8.1-full_build\bin\ffmpeg.exe"
)


def _ffmpeg_exe() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    p = Path(_FFMPEG_FALLBACK)
    return str(p) if p.exists() else None


def ffmpeg_available() -> bool:
    return _ffmpeg_exe() is not None


def transcode_to_h264(src: Path, dst: Path) -> bool:
    """
    OpenCV's mp4v writer produces MP4 files that most browsers refuse
    to decode in <video>. Re-wrap/transcode to H.264 + yuv420p + faststart
    so the processed video plays cleanly in Chrome, Firefox, and Safari.

    Returns True on success, False if ffmpeg is missing or errors.
    """
    exe = _ffmpeg_exe()
    if not exe:
        logger.warning(
            "ffmpeg not found on PATH. Skipping H.264 transcode — the "
            "processed video may fail to play in browsers. Install ffmpeg "
            "and re-run a job to produce web-playable output."
        )
        return False

    cmd = [
        _ffmpeg_exe(),
        "-y",
        "-loglevel", "error",
        "-i", str(src),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-an",
        str(dst),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=600)
    except Exception:
        logger.exception("ffmpeg invocation crashed")
        return False

    if result.returncode != 0:
        logger.error(
            "ffmpeg transcode failed (code %s): %s",
            result.returncode,
            result.stderr.decode(errors="ignore")[:500],
        )
        return False
    return True
