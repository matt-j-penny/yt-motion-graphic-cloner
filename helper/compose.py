from __future__ import annotations

import html
import json
import re
from pathlib import Path

AUTOPLAY = """  <!-- hf-autoplay --><script>(function(){if(window.self===window.top)return;if(window.__hyperframes)return;function play(){var rec=window.__timelines||{};var k=Object.keys(rec);if(!k.length){setTimeout(play,150);return;}k.forEach(function(id){var t=rec[id];if(!t||typeof t.eventCallback!=="function"||typeof t.restart!=="function")return;t.eventCallback("onComplete",function(){setTimeout(play,1200)});t.restart();});}setTimeout(play,200);}());</script>"""


def _rgb(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*[max(0, min(255, int(c))) for c in rgb])


def _js_string(value: str) -> str:
    return json.dumps(value)


def _slug(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (text or "template").lower()).strip("-")
    return text[:40] or "template"


def _shell(duration: float, bg: str, body_css: str, body_html: str, body_js: str, transparent: bool) -> str:
    page_bg = "transparent" if transparent else bg
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800&display=swap" rel="stylesheet" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{
        width: 1920px;
        height: 1080px;
        overflow: hidden;
        background: {page_bg};
      }}
      #root {{
        position: relative;
        width: 1920px;
        height: 1080px;
        overflow: hidden;
        background: {page_bg};
      }}
      .clip {{ position: absolute; inset: 0; }}
      {body_css}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{duration:.2f}" data-width="1920" data-height="1080">
      {body_html}
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      {body_js}
      window.__timelines["main"] = tl;
    </script>
{AUTOPLAY}
</body>
</html>
"""


def compose_kinetic(spec: dict) -> str:
    bg = _rgb(spec["bg"])
    fg = "#f8f4ec" if spec["light_text"] else "#111111"
    accent = _rgb(spec["accent"])
    words = spec["headline"].split()
    if len(words) > 8:
        words = words[:8]
    spans = "".join(
        f'<span class="word" id="w{i}">{html.escape(word)}</span>' for i, word in enumerate(words)
    )
    css = f"""
      .stage {{
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 120px;
      }}
      .headline {{
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 0.28em;
        max-width: 1500px;
        font-family: Inter, system-ui, sans-serif;
        font-size: 96px;
        font-weight: 800;
        letter-spacing: -0.04em;
        line-height: 1.05;
        color: {fg};
        text-align: center;
      }}
      .word {{ display: inline-block; }}
      .word:nth-child(odd) {{ color: {accent}; }}
    """
    body = f"""
      <section class="clip" data-start="0" data-duration="{spec['duration']:.2f}" data-track-index="0">
        <div class="stage" id="stage">
          <h1 class="headline" id="headline">{spans}</h1>
        </div>
      </section>
    """
    n = max(len(words), 1)
    stagger = min(0.16, 1.2 / n)
    hold = max(spec["duration"] - 1.4, 1.8)
    js = f"""
      const words = gsap.utils.toArray("#headline .word");
      tl.fromTo(words, {{ y: 48, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.55, stagger: {stagger:.2f}, ease: "power3.out" }}, 0.12);
      tl.to(words, {{ y: -36, opacity: 0, duration: 0.4, stagger: 0.04, ease: "power2.in" }}, {hold:.2f});
    """
    return _shell(spec["duration"], bg, css, body, js, transparent=False)


def compose_lower_third(spec: dict) -> str:
    accent = _rgb(spec["accent"])
    line1 = spec["headline"]
    line2 = spec["items"][0] if spec["items"] else ""
    css = """
      .lower {{
        left: 0; right: 0; bottom: 0; height: 320px;
        display: flex; justify-content: center; align-items: flex-end;
        padding: 0 160px 64px;
        background: linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(6,5,12,0.55) 40%, rgba(3,3,8,0.94) 100%);
      }}
      .copy {{
        font-family: Inter, system-ui, sans-serif;
        text-align: center;
        max-width: 1400px;
      }}
      .line1 {{
        display: block;
        color: #f8f4ec;
        font-size: 72px;
        font-weight: 700;
        line-height: 1.1;
      }}
      .line2 {{
        display: block;
        margin-top: 8px;
        color: ACCENT;
        font-size: 56px;
        font-weight: 600;
      }}
      .word {{ display: inline-block; white-space: pre; }}
    """.replace("ACCENT", accent)
    body = f"""
      <section class="clip lower" data-start="0" data-duration="{spec['duration']:.2f}" data-track-index="0">
        <div class="copy" id="copy">
          <span class="line1" id="line1"></span>
          <span class="line2" id="line2"></span>
        </div>
      </section>
    """
    js = f"""
      function words(el, text) {{
        const parts = text.split(" ").filter(Boolean);
        el.innerHTML = parts.map((w, i) => '<span class="word">' + w + (i < parts.length - 1 ? " " : "") + "</span>").join("");
        return el.querySelectorAll(".word");
      }}
      const l1 = words(document.getElementById("line1"), {_js_string(line1)});
      const l2 = words(document.getElementById("line2"), {_js_string(line2)});
      tl.fromTo("#copy", {{ y: 36, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.5, ease: "power2.out" }}, 0.15);
      tl.fromTo(l1, {{ y: 24, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.45, stagger: 0.12, ease: "power3.out" }}, 0.32);
      tl.fromTo(l2, {{ y: 24, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.45, stagger: 0.12, ease: "power3.out" }}, 0.9);
      tl.to("#copy", {{ y: 28, opacity: 0, duration: 0.4, ease: "power2.in" }}, {max(spec['duration'] - 0.7, 2):.2f});
    """
    return _shell(spec["duration"], "#000000", css, body, js, transparent=True)


def compose_stat(spec: dict) -> str:
    bg = _rgb(spec["bg"])
    fg = "#f8f4ec" if spec["light_text"] else "#111111"
    accent = _rgb(spec["accent"])
    blob = spec["headline"] + " " + " ".join(spec["items"])
    match = re.search(r"(\$?\d[\d,\.]*\s?%?)", blob)
    number = match.group(1) if match else spec["headline"]
    caption = spec["items"][0] if spec["items"] else spec["headline"]
    css = f"""
      .stage {{ inset: 0; display: grid; place-items: center; }}
      .card {{
        width: 720px;
        padding: 64px 72px 56px;
        border-radius: 28px;
        background: {bg};
        text-align: center;
        font-family: Inter, system-ui, sans-serif;
      }}
      .number {{
        font-size: 180px;
        font-weight: 800;
        letter-spacing: -0.06em;
        line-height: 0.9;
        color: {accent};
      }}
      .caption {{
        margin-top: 28px;
        font-size: 42px;
        font-weight: 600;
        color: {fg};
      }}
    """
    body = f"""
      <section class="clip" data-start="0" data-duration="{spec['duration']:.2f}" data-track-index="0">
        <div class="stage">
          <div class="card" id="card">
            <div class="number" id="number">{html.escape(number)}</div>
            <div class="caption" id="caption">{html.escape(caption)}</div>
          </div>
        </div>
      </section>
    """
    js = f"""
      tl.fromTo("#card", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.55, ease: "power3.out" }}, 0.1);
      tl.fromTo("#number", {{ y: 24, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.5, ease: "power3.out" }}, 0.28);
      tl.fromTo("#caption", {{ y: 16, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: "power2.out" }}, 0.5);
      tl.to("#card", {{ y: -28, opacity: 0, duration: 0.4, ease: "power2.in" }}, {max(spec['duration'] - 0.65, 2):.2f});
    """
    return _shell(spec["duration"], bg, css, body, js, transparent=not spec.get("takeover", True))


def compose_callout_stack(spec: dict) -> str:
    bg = _rgb(spec["bg"])
    fg = "#f4f7f4" if spec["light_text"] else "#111111"
    accent = _rgb(spec["accent"])
    items = spec["items"][:5] or ["Point one", "Point two"]
    item_html = "".join(
        f'<div class="item" id="item{i}"><span class="dot"></span><span class="label">{html.escape(item)}</span></div>'
        for i, item in enumerate(items)
    )
    css = f"""
      .stage {{
        inset: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 36px;
        font-family: Inter, system-ui, sans-serif;
      }}
      .hero {{
        display: flex;
        align-items: center;
        gap: 22px;
        padding: 28px 36px;
        border-radius: 18px;
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.12);
        max-width: 1100px;
      }}
      .doc {{
        width: 54px;
        height: 66px;
        border-radius: 8px;
        background: #e9eef1;
        position: relative;
        flex-shrink: 0;
      }}
      .doc:after {{
        content: "";
        position: absolute;
        right: 0;
        top: 0;
        border-width: 0 14px 14px 0;
        border-style: solid;
        border-color: {bg} {bg} transparent transparent;
      }}
      .hero-title {{
        font-size: 42px;
        font-weight: 700;
        color: {fg};
        line-height: 1.15;
      }}
      .list {{
        display: flex;
        flex-direction: column;
        gap: 18px;
        min-width: 520px;
      }}
      .item {{
        display: flex;
        align-items: center;
        gap: 16px;
        font-size: 36px;
        font-weight: 600;
        color: {fg};
      }}
      .dot {{
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: {accent};
        flex-shrink: 0;
      }}
    """
    body = f"""
      <section class="clip" data-start="0" data-duration="{spec['duration']:.2f}" data-track-index="0">
        <div class="stage" id="stage">
          <div class="hero" id="hero">
            <div class="doc"></div>
            <div class="hero-title">{html.escape(spec["headline"])}</div>
          </div>
          <div class="list" id="list">{item_html}</div>
        </div>
      </section>
    """
    n = len(items)
    last_in = 0.7 + n * 0.28
    out = max(spec["duration"] - 0.7, last_in + 0.8)
    js = f"""
      const items = gsap.utils.toArray("#list .item");
      tl.fromTo("#hero", {{ y: 28, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.55, ease: "power3.out" }}, 0.12);
      tl.fromTo(items, {{ x: -24, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.45, stagger: 0.22, ease: "power3.out" }}, 0.7);
      tl.to("#stage", {{ y: -24, opacity: 0, duration: 0.4, ease: "power2.in" }}, {out:.2f});
    """
    return _shell(spec["duration"], bg, css, body, js, transparent=False)


COMPOSERS = {
    "kinetic_title": compose_kinetic,
    "lower_third": compose_lower_third,
    "stat": compose_stat,
    "callout_stack": compose_callout_stack,
}


def compose_html(spec: dict) -> str:
    builder = COMPOSERS.get(spec.get("kind"), compose_kinetic)
    return builder(spec)


def catalog_entry(spec: dict, template_id: str, rel_path: str, source_title: str) -> dict:
    kind_names = {
        "kinetic_title": "Title reveal",
        "lower_third": "Lower third",
        "stat": "Stat card",
        "callout_stack": "Callout stack",
        "claude_rebuild": "Claude rebuild",
    }
    kind = spec.get("kind") or "kinetic_title"
    headline = spec.get("headline") or "Captured graphic"
    return {
        "id": template_id,
        "name": f"Captured: {headline[:48]}",
        "category": "mg",
        "duration": round(float(spec["duration"]), 2),
        "mediaMode": "overlay" if kind == "lower_third" else "standalone",
        "desc": f"First draft rebuilt from YouTube ({kind_names.get(kind, kind)}). Source: {source_title}. Swap the words to make it yours.",
        "features": ["captured from YouTube", kind_names.get(kind, kind), "editable copy"],
        "path": rel_path,
        "captured": True,
    }


def template_id_for(folder: Path, headline: str) -> str:
    stamp = folder.name.split("__")[0] if folder.name else "cap"
    return f"cap-{stamp}-{_slug(headline)}"
