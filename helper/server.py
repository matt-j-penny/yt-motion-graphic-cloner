#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import threading
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from capture import run_capture, tool_status  # noqa: E402
from config import HOST, INBOX, LOG_FILE, MAX_SECONDS, PORT, VERSION, WARN_SECONDS  # noqa: E402

JOBS: dict[str, dict] = {}
JOB_LOCK = threading.Lock()
ACTIVE = False


def log(message: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = message.rstrip() + "\n"
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(line)
    sys.stderr.write(line)


def json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length") or 0)
    raw = handler.rfile.read(length) if length else b"{}"
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def cors(handler: BaseHTTPRequestHandler) -> None:
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        path = args[0] if args else ""
        if "/health" in str(path):
            return
        log("%s - %s" % (self.address_string(), fmt % args))

    def send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        cors(self)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        cors(self)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            tools = tool_status()
            self.send_json(
                200,
                {
                    "ok": True,
                    "version": VERSION,
                    "inbox": tools["inbox"],
                    "libraryRoot": tools.get("libraryRoot"),
                    "libraryDir": tools.get("libraryDir"),
                    "libraryReady": tools.get("libraryReady", False),
                    "catalogReady": tools.get("catalogReady", False),
                    "libraryWired": tools.get("libraryWired", False),
                    "ytdlp": tools["ytdlp"],
                    "ffmpeg": tools["ffmpeg"],
                    "claude": tools.get("claude", False),
                    "busy": ACTIVE,
                },
            )
            return
        if parsed.path == "/jobs":
            with JOB_LOCK:
                jobs = list(JOBS.values())
            jobs.sort(key=lambda job: job.get("createdAt") or "", reverse=True)
            self.send_json(200, {"ok": True, "jobs": jobs[:20]})
            return
        if parsed.path.startswith("/jobs/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            with JOB_LOCK:
                job = JOBS.get(job_id)
            if not job:
                self.send_json(404, {"ok": False, "error": "That capture was not found."})
                return
            self.send_json(200, {"ok": True, **job})
            return
        self.send_json(404, {"ok": False, "error": "Unknown request."})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = json_body(self)
        except json.JSONDecodeError:
            self.send_json(400, {"ok": False, "error": "The capture request was not readable."})
            return
        if parsed.path == "/capture":
            self.start_capture(payload)
            return
        if parsed.path == "/reveal":
            path = Path(payload.get("path") or INBOX)
            if not str(path).startswith(str(INBOX.parent)):
                self.send_json(400, {"ok": False, "error": "That folder can’t be opened."})
                return
            path.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(["open", str(path)])
            self.send_json(200, {"ok": True})
            return
        if parsed.path == "/open-inbox":
            INBOX.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(["open", str(INBOX)])
            self.send_json(200, {"ok": True, "inbox": str(INBOX)})
            return
        self.send_json(404, {"ok": False, "error": "Unknown request."})

    def start_capture(self, payload: dict) -> None:
        global ACTIVE
        url = (payload.get("url") or "").strip()
        try:
            start = float(payload.get("start"))
            end = float(payload.get("end"))
        except (TypeError, ValueError):
            self.send_json(400, {"ok": False, "error": "Start and end times were missing."})
            return
        if not url:
            self.send_json(400, {"ok": False, "error": "The YouTube link was missing."})
            return
        if end <= start:
            self.send_json(400, {"ok": False, "error": "End needs to be after start."})
            return
        duration = end - start
        if duration > MAX_SECONDS:
            self.send_json(
                400,
                {
                    "ok": False,
                    "error": f"That’s {duration:.1f} seconds. Keep captures under {MAX_SECONDS} seconds.",
                },
            )
            return
        with JOB_LOCK:
            if ACTIVE:
                self.send_json(
                    409,
                    {"ok": False, "error": "A capture is already running. Wait for it to finish."},
                )
                return
            ACTIVE = True
            job_id = uuid.uuid4().hex[:12]
            job = {
                "id": job_id,
                "status": "queued",
                "progress": "Starting…",
                "error": None,
                "folder": None,
                "frameCount": None,
                "title": payload.get("title") or "",
                "start": start,
                "end": end,
                "duration": duration,
                "warn": duration >= WARN_SECONDS,
                "createdAt": payload.get("capturedAt"),
            }
            JOBS[job_id] = job
        thread = threading.Thread(target=self._run_job, args=(job_id, payload), daemon=True)
        thread.start()
        self.send_json(202, {"ok": True, "id": job_id, **job})

    def _run_job(self, job_id: str, payload: dict) -> None:
        global ACTIVE

        def on_status(message: str) -> None:
            with JOB_LOCK:
                job = JOBS[job_id]
                job["status"] = "running"
                job["progress"] = message

        try:
            result = run_capture(payload, on_status)
            with JOB_LOCK:
                job = JOBS[job_id]
                job["status"] = "done"
                job["progress"] = "Saved to your template inbox."
                job["folder"] = result["folder"]
                job["frameCount"] = result["frameCount"]
                job["contactSheet"] = result.get("contactSheet")
            log(f"capture done {job_id} {result['folder']}")
        except Exception as exc:
            log(f"capture failed {job_id}: {exc}\n{traceback.format_exc()}")
            with JOB_LOCK:
                job = JOBS[job_id]
                job["status"] = "error"
                job["progress"] = str(exc)
                job["error"] = str(exc)
        finally:
            with JOB_LOCK:
                ACTIVE = False


def main() -> None:
    INBOX.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    log(f"yt-motion-capture helper v{VERSION} on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
