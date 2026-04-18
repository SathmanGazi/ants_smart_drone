from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def transcode_to_h264(src: Path, dst: Path) -> bool:
    """
    OpenCV's mp4v writer produces MP4 files that most browsers refuse
    to decode in <video>. Re-wrap/transcode to H.264 + yuv420p + faststart
    so the processed video plays cleanly in Chrome, Firefox, and Safari.

    Returns True on success, False if ffmpeg is missing or errors.
    """
    if not ffmpeg_available():
        logger.warning(
            "ffmpeg not found on PATH. Skipping H.264 transcode — the "
            "processed video may fail to play in browsers. Install ffmpeg "
            "and re-run a job to produce web-playable output."
        )
        return False

    cmd = [
        "ffmpeg",
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
