from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from claude_rebuild import rebuild_with_claude, tool_has_claude
from compose import AUTOPLAY, catalog_entry, template_id_for
from config import (
    CATALOG_JS,
    DOWNLOAD_TIMEOUT,
    FFMPEG_TIMEOUT,
    FRAME_WIDTH,
    HYPERFRAMES_ROOT,
    INBOX,
    LIBRARY_DIR,
    MAX_FPS,
    MIN_FPS,
    TARGET_FRAMES,
)
from library import publish


def which(name: str) -> str | None:
    return shutil.which(name)


def library_status() -> dict:
    page = HYPERFRAMES_ROOT / "template-library.html"
    html = page.read_text(encoding="utf-8") if page.exists() else ""
    return {
        "libraryRoot": str(HYPERFRAMES_ROOT),
        "libraryDir": str(LIBRARY_DIR),
        "libraryReady": LIBRARY_DIR.exists(),
        "catalogReady": CATALOG_JS.exists(),
        "libraryPage": str(page) if page.exists() else None,
        "libraryWired": "captured-templates.js" in html and "CAPTURED_TEMPLATES" in html,
        "inbox": str(INBOX),
    }


def tool_status() -> dict:
    return {
        "ytdlp": bool(which("yt-dlp")),
        "ffmpeg": bool(which("ffmpeg")),
        "claude": tool_has_claude(),
        **library_status(),
    }


def slugify(text: str, limit: int = 48) -> str:
    text = (text or "clip").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-") or "clip"
    return text[:limit].rstrip("-")


def folder_name(title: str, video_id: str, start: float, end: float) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    vid = video_id or "video"
    return f"{stamp}__{slugify(title)}__{vid}__{start:.1f}-{end:.1f}s"


def _run(cmd: list[str], timeout: int, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=cwd,
        timeout=timeout,
        capture_output=True,
        text=True,
    )


def _ytdlp_cmd(url: str, start: float, end: float, out_path: Path) -> list[str]:
    return [
        "yt-dlp",
        "--no-playlist",
        "--no-warnings",
        "--newline",
        "--extractor-args",
        "youtube:player_client=android,web",
        "--merge-output-format",
        "mp4",
        "--download-sections",
        f"*{start:.3f}-{end:.3f}",
        "--force-keyframes-at-cuts",
        "-f",
        "bv*[ext=mp4][height<=1080]+ba[ext=m4a]/b[ext=mp4]/b",
        "-o",
        str(out_path),
        url,
    ]


def download_clip(url: str, start: float, end: float, dest: Path, on_status) -> Path:
    out_path = dest / "clip.mp4"
    on_status("Downloading the clip…")
    try:
        result = _run(_ytdlp_cmd(url, start, end, out_path), DOWNLOAD_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("The download took too long and was stopped.") from exc
    if result.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
        return out_path
    last_error = (result.stderr or result.stdout or "").strip()
    if out_path.exists() and out_path.stat().st_size == 0:
        out_path.unlink()
    raise RuntimeError(plain_download_error(last_error))


def plain_download_error(raw: str) -> str:
    lower = raw.lower()
    if "http error 403" in lower or "sign in" in lower or "confirm your age" in lower:
        return "YouTube blocked the download. Try a public video, or play it once in Chrome and retry."
    if "private video" in lower:
        return "This video is private, so it can’t be captured."
    if "ffmpeg" in lower and "not found" in lower:
        return "ffmpeg is missing, so the clip couldn’t be cut."
    if raw:
        short = raw.splitlines()[-1][:240]
        return f"Couldn’t download that clip. {short}"
    return "Couldn’t download that clip."


def chosen_fps(duration: float) -> float:
    # Always at least 4 stills a second for Claude. Short clips can go higher.
    return max(float(MIN_FPS), min(float(MAX_FPS), TARGET_FRAMES / max(duration, 0.4)))


def extract_frames(clip: Path, dest: Path, duration: float, on_status) -> list[Path]:
    on_status("Pulling screens from the clip…")
    frames_dir = dest / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    fps = chosen_fps(duration)
    pattern = frames_dir / "frame_%04d.jpg"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(clip),
        "-vf",
        f"fps={fps:.3f},scale={FRAME_WIDTH}:-2",
        "-q:v",
        "3",
        str(pattern),
    ]
    try:
        result = _run(cmd, FFMPEG_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Pulling screens took too long and was stopped.") from exc
    frames = sorted(frames_dir.glob("frame_*.jpg"))
    if not frames:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else "ffmpeg produced no frames."
        raise RuntimeError(f"Couldn’t pull screens from the clip. {tail[:200]}")
    actual = len(frames) / max(duration, 0.01)
    if actual + 0.05 < MIN_FPS:
        raise RuntimeError(
            f"Need at least {MIN_FPS} stills a second for Claude. Only got {len(frames)} from {duration:.1f}s."
        )
    return frames


def make_contact_sheet(frames: list[Path], dest: Path, on_status) -> Path | None:
    if not frames:
        return None
    on_status("Making a contact sheet…")
    sample = list(frames)
    sheet = dest / "contact-sheet.jpg"
    if len(sample) == 1:
        shutil.copyfile(sample[0], sheet)
        return sheet
    cols = min(6, len(sample))
    rows = math.ceil(len(sample) / cols)
    while len(sample) < cols * rows:
        sample.append(sample[-1])
    work = dest / "_sheet"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    for index, frame in enumerate(sample, start=1):
        shutil.copyfile(frame, work / f"{index:04d}.jpg")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(work / "%04d.jpg"),
        "-vf",
        f"scale=320:-2,tile={cols}x{rows}",
        "-frames:v",
        "1",
        "-q:v",
        "4",
        str(sheet),
    ]
    try:
        result = _run(cmd, FFMPEG_TIMEOUT)
    except subprocess.TimeoutExpired:
        shutil.rmtree(work, ignore_errors=True)
        return None
    shutil.rmtree(work, ignore_errors=True)
    if result.returncode != 0 or not sheet.exists():
        return None
    return sheet


def write_manifest(
    dest: Path,
    payload: dict,
    clip: Path,
    frames: list[Path],
    sheet: Path | None,
) -> Path:
    data = {
        "source": "youtube",
        "url": payload.get("url"),
        "videoId": payload.get("videoId"),
        "title": payload.get("title"),
        "start": payload.get("start"),
        "end": payload.get("end"),
        "duration": payload.get("end") - payload.get("start"),
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "clip": clip.name,
        "framesDir": "frames",
        "frameCount": len(frames),
        "fps": round(len(frames) / max((payload.get("end") or 0) - (payload.get("start") or 0), 0.01), 2),
        "contactSheet": sheet.name if sheet else None,
        "status": "inbox",
        "templateKind": None,
        "templateId": None,
        "templatePath": None,
        "notes": "Reference clip and stills for rebuilding this motion graphic in HyperFrames. Do not republish the source footage.",
    }
    path = dest / "capture.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def run_capture(payload: dict, on_status) -> dict:
    missing = []
    if not which("yt-dlp"):
        missing.append("yt-dlp")
    if not which("ffmpeg"):
        missing.append("ffmpeg")
    if missing:
        raise RuntimeError(
            "The helper is missing " + " and ".join(missing) + ". Install them with Homebrew, then try again."
        )
    if not tool_has_claude():
        raise RuntimeError("Claude Code isn’t installed, so the graphic can’t be rebuilt yet.")

    title = payload.get("title") or "YouTube clip"
    video_id = payload.get("videoId") or "video"
    start = float(payload["start"])
    end = float(payload["end"])
    dest = INBOX / folder_name(title, video_id, start, end)
    dest.mkdir(parents=True, exist_ok=True)

    clip = download_clip(payload["url"], start, end, dest, on_status)
    frames = extract_frames(clip, dest, end - start, on_status)
    sheet = make_contact_sheet(frames, dest, on_status)
    write_manifest(payload=payload, dest=dest, clip=clip, frames=frames, sheet=sheet)
    template_path, spec = build_template(dest, frames, end - start, title, on_status)
    on_status("Saved to your template library.")
    return {
        "folder": str(dest),
        "clip": str(clip),
        "frameCount": len(frames),
        "contactSheet": str(sheet) if sheet else None,
        "templatePath": str(template_path) if template_path else None,
        "kind": spec.get("kind") if spec else None,
    }


def build_template(dest: Path, frames: list[Path], duration: float, title: str, on_status):
    fps = len(frames) / max(duration, 0.01)
    listing = [
        {
            "file": f"frames/{frame.name}",
            "time": round(index / max(fps, MIN_FPS), 3),
        }
        for index, frame in enumerate(frames)
    ]
    (dest / "frames.json").write_text(
        json.dumps({"fps": round(fps, 2), "count": len(frames), "duration": duration, "frames": listing}, indent=2),
        encoding="utf-8",
    )
    html = rebuild_with_claude(dest, frames, duration, title, on_status)
    if "hf-autoplay" not in html:
        html = html.replace("</body>", AUTOPLAY + "\n</body>") if "</body>" in html.lower() else html + AUTOPLAY
        (dest / "template.html").write_text(html, encoding="utf-8")
    spec = {
        "kind": "claude_rebuild",
        "headline": title[:80] or "Captured graphic",
        "duration": duration,
        "fps": round(fps, 2),
        "frameCount": len(frames),
    }
    tid = template_id_for(dest, spec["headline"])
    rel = f"Assets/templates/captured/{tid}.html"
    entry = catalog_entry(spec, tid, rel, title)
    lib_path = publish(entry, html)
    (dest / "spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    manifest_path = dest / "capture.json"
    if manifest_path.exists():
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        data["status"] = "templated"
        data["templateKind"] = spec["kind"]
        data["templateId"] = tid
        data["templatePath"] = str(lib_path)
        data["fps"] = spec["fps"]
        data["frameCount"] = len(frames)
        manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return lib_path, spec
