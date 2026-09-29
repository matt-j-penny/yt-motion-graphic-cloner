from pathlib import Path

HOST = "127.0.0.1"
PORT = 47821
VERSION = "0.4.0"

HOME = Path.home()
HYPERFRAMES_ROOT = HOME / "Documents/CC/Hyperframes"
INBOX = HYPERFRAMES_ROOT / "captures/inbox"
LIBRARY_DIR = HYPERFRAMES_ROOT / "Assets/templates/captured"
CATALOG_JSON = HYPERFRAMES_ROOT / "captures/captured-templates.json"
CATALOG_JS = HYPERFRAMES_ROOT / "captures/captured-templates.js"
LOG_DIR = HOME / "Library/Logs"
LOG_FILE = LOG_DIR / "yt-motion-capture.log"

MAX_SECONDS = 30
WARN_SECONDS = 15
TARGET_FRAMES = 36
MIN_FPS = 4
MAX_FPS = 12
FRAME_WIDTH = 960
SHEET_MAX_FRAMES = 120
CLAUDE_TIMEOUT = 600
DOWNLOAD_TIMEOUT = 300
FFMPEG_TIMEOUT = 120
