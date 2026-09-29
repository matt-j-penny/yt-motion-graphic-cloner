from __future__ import annotations

import json
from pathlib import Path

from config import CATALOG_JS, CATALOG_JSON, LIBRARY_DIR


def _load_catalog() -> list[dict]:
    if not CATALOG_JSON.exists():
        return []
    try:
        data = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def publish(entry: dict, html: str) -> Path:
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    CATALOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    dest = LIBRARY_DIR / f"{entry['id']}.html"
    dest.write_text(html, encoding="utf-8")
    catalog = [item for item in _load_catalog() if item.get("id") != entry["id"]]
    catalog.insert(0, entry)
    CATALOG_JSON.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    payload = json.dumps(catalog)
    CATALOG_JS.write_text(f"window.CAPTURED_TEMPLATES = {payload};\n", encoding="utf-8")
    return dest
