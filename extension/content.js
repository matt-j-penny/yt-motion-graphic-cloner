const HOST_ID = "yt-motion-capture-host";
const TOGGLE_ID = "yt-motion-capture-toggle";
let cachedCss = "";
fetch(chrome.runtime.getURL("content.css"))
  .then((res) => res.text())
  .then((text) => {
    cachedCss = text;
    const style = shadowRoot?.querySelector("style");
    if (style) style.textContent = text;
    const launchStyle = launcherRoot?.querySelector("style");
    if (launchStyle) launchStyle.textContent = text;
  });
const RANGE_ID = "ytmc-range";
const START_ID = "ytmc-start-handle";
const END_ID = "ytmc-end-handle";
const NUDGE = 0.1;
const WARN_SECONDS = 15;

const state = {
  videoId: null,
  start: null,
  end: null,
  looping: false,
  jobId: null,
  pollTimer: null,
  helperOk: null,
  confirmLong: false,
  open: false,
};

let shadowRoot = null;
let launcherRoot = null;
let lastUrl = "";

function qs(sel) {
  return shadowRoot?.querySelector(sel);
}

function isWatchPage() {
  return location.pathname === "/watch" && Boolean(getVideoId());
}

function getVideoId() {
  return new URLSearchParams(location.search).get("v");
}

function getVideo() {
  return document.querySelector("#movie_player video, video.html5-main-video, ytd-player video");
}

function getTitle() {
  const node = document.querySelector(
    "ytd-watch-metadata h1 yt-formatted-string, #title h1 yt-formatted-string, h1.ytd-watch-metadata"
  );
  return (node?.textContent || document.title.replace(/ - YouTube$/, "")).trim();
}

function formatTime(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return "—";
  const sign = seconds < 0 ? "-" : "";
  const abs = Math.max(0, seconds);
  const m = Math.floor(abs / 60);
  const s = abs % 60;
  const whole = Math.floor(s);
  const frac = Math.round((s - whole) * 10);
  const shownWhole = frac === 10 ? whole + 1 : whole;
  const shownFrac = frac === 10 ? 0 : frac;
  return `${sign}${m}:${String(shownWhole).padStart(2, "0")}.${shownFrac}`;
}

function duration() {
  if (state.start == null || state.end == null) return null;
  return Math.max(0, state.end - state.start);
}

function helper(path, options) {
  return chrome.runtime.sendMessage({ type: "forward", path, options });
}

async function loadMarks(videoId) {
  const key = `marks:${videoId}`;
  const stored = await chrome.storage.local.get(key);
  const marks = stored[key];
  state.start = typeof marks?.start === "number" ? marks.start : null;
  state.end = typeof marks?.end === "number" ? marks.end : null;
  state.looping = false;
  state.confirmLong = false;
  state.open = false;
}

async function saveMarks() {
  if (!state.videoId) return;
  await chrome.storage.local.set({
    [`marks:${state.videoId}`]: { start: state.start, end: state.end },
  });
}

function currentTime() {
  const video = getVideo();
  return video ? video.currentTime : 0;
}

function seekTo(time) {
  const video = getVideo();
  if (!video || time == null) return;
  video.currentTime = Math.max(0, Math.min(time, video.duration || time));
}

function clampMark(time) {
  const video = getVideo();
  const max = video?.duration && Number.isFinite(video.duration) ? video.duration : time;
  return Math.max(0, Math.min(time, max));
}

function setStart(time) {
  state.start = clampMark(time);
  if (state.end != null && state.end <= state.start) state.end = null;
  state.confirmLong = false;
  saveMarks();
  render();
}

function setEnd(time) {
  state.end = clampMark(time);
  if (state.start != null && state.end <= state.start) {
    setStatus("End needs to be after start. Play a little further, then click End.", "err");
  }
  state.confirmLong = false;
  saveMarks();
  render();
}

function nudge(which, delta) {
  const value = which === "start" ? state.start : state.end;
  const next = clampMark((value ?? currentTime()) + delta);
  if (which === "start") setStart(next);
  else setEnd(next);
  seekTo(next);
}

function findTitleBox() {
  return (
    document.querySelector("ytd-watch-metadata #title") ||
    document.querySelector("#above-the-fold #title") ||
    document.querySelector("#title.ytd-watch-metadata")
  );
}

function captureIcon() {
  return `<svg viewBox="0 0 14 14" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.6" d="M2 5V3.2A1.2 1.2 0 0 1 3.2 2H5M9 2h1.8A1.2 1.2 0 0 1 12 3.2V5M12 9v1.8A1.2 1.2 0 0 1 10.8 12H9M5 12H3.2A1.2 1.2 0 0 1 2 10.8V9"/></svg>`;
}

function mountUI() {
  const title = findTitleBox();
  if (!title) return null;
  mountLauncher(title);
  return mountPanel(title);
}

function mountLauncher(title) {
  if (document.getElementById(TOGGLE_ID)) return;
  const heading = title.querySelector("h1") || title;
  title.style.display = "flex";
  title.style.alignItems = "flex-start";
  title.style.gap = "8px";
  if (heading !== title) {
    heading.style.flex = "1";
    heading.style.minWidth = "0";
  }
  const host = document.createElement("div");
  host.id = TOGGLE_ID;
  host.className = "launcher-host";
  if (heading.nextSibling) heading.insertAdjacentElement("afterend", host);
  else title.appendChild(host);
  launcherRoot = host.attachShadow({ mode: "open" });
  const styles = document.createElement("style");
  styles.textContent = cachedCss;
  const wrap = document.createElement("div");
  wrap.innerHTML = `<button class="launcher" data-act="toggle" type="button" aria-label="Mark a clip" title="Mark a clip">${captureIcon()}</button>`;
  launcherRoot.append(styles, wrap);
  launcherRoot.addEventListener("click", onClick);
  host.addEventListener("click", (event) => {
    event.stopPropagation();
  });
}

function mountPanel(title) {
  if (document.getElementById(HOST_ID)) return document.getElementById(HOST_ID);
  const host = document.createElement("div");
  host.id = HOST_ID;
  title.insertAdjacentElement("afterend", host);
  shadowRoot = host.attachShadow({ mode: "open" });
  const styles = document.createElement("style");
  styles.textContent = cachedCss;
  const wrap = document.createElement("div");
  wrap.className = "wrap";
  wrap.innerHTML = `
    <div class="bar">
      <div class="mark-group">
        <button class="mark" data-act="start" type="button">
          <span class="label">Start</span>
          <span class="time" data-role="start-time">—</span>
        </button>
        <button class="nudge" data-act="start-back" type="button" aria-label="Nudge start back">${chevron("left")}</button>
        <button class="nudge" data-act="start-fwd" type="button" aria-label="Nudge start forward">${chevron("right")}</button>
      </div>
      <div class="mark-group">
        <button class="mark" data-act="end" type="button">
          <span class="label">End</span>
          <span class="time" data-role="end-time">—</span>
        </button>
        <button class="nudge" data-act="end-back" type="button" aria-label="Nudge end back">${chevron("left")}</button>
        <button class="nudge" data-act="end-fwd" type="button" aria-label="Nudge end forward">${chevron("right")}</button>
      </div>
      <span class="dur" data-role="duration"></span>
      <button class="ghost icon" data-act="loop" type="button" aria-label="Loop this section" title="Loop">${loopIcon()}</button>
      <button class="primary" data-act="save" type="button">Make template</button>
    </div>
    <div class="status hidden" data-role="status"></div>
  `;
  shadowRoot.append(styles, wrap);
  wrap.addEventListener("click", onClick);
  return host;
}

function loopIcon() {
  return `<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" d="M3 7.2A5 5 0 0 1 11.2 4.4L13 6M13 2.8V6h-3.2M13 8.8A5 5 0 0 1 4.8 11.6L3 10M3 13.2V10h3.2"/></svg>`;
}

function chevron(dir) {
  const d = dir === "left" ? "M8.2 2.5 3.8 7l4.4 4.5" : "M5.8 2.5 10.2 7l-4.4 4.5";
  return `<svg viewBox="0 0 14 14" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" d="${d}"/></svg>`;
}

function onClick(event) {
  const act = event.target.closest("[data-act]")?.dataset.act;
  if (!act) return;
  event.preventDefault();
  event.stopPropagation();
  if (act === "toggle") togglePanel();
  if (act === "start") setStart(currentTime());
  if (act === "end") setEnd(currentTime());
  if (act === "start-back") nudge("start", -NUDGE);
  if (act === "start-fwd") nudge("start", NUDGE);
  if (act === "end-back") nudge("end", -NUDGE);
  if (act === "end-fwd") nudge("end", NUDGE);
  if (act === "loop") toggleLoop();
  if (act === "save") saveClip();
  if (act === "setup") chrome.runtime.sendMessage({ type: "open-setup" });
  if (act === "reveal") revealLast();
}

function togglePanel() {
  state.open = !state.open;
  if (!state.open) {
    state.looping = false;
  } else {
    checkHelper();
  }
  render();
}

function openPanel() {
  if (state.open) return;
  state.open = true;
  checkHelper();
  render();
}

function toggleLoop() {
  if (state.start == null || state.end == null || state.end <= state.start) {
    setStatus("Set a start and end before looping.", "err");
    return;
  }
  state.looping = !state.looping;
  if (state.looping) {
    const video = getVideo();
    if (video && (video.currentTime < state.start || video.currentTime >= state.end)) {
      seekTo(state.start);
      video.play().catch(() => {});
    }
    setStatus("Looping this section.", "");
  } else {
    setStatus("", "");
  }
  render();
}

function onTimeUpdate() {
  if (!state.looping || state.start == null || state.end == null) return;
  const video = getVideo();
  if (!video) return;
  if (video.currentTime >= state.end - 0.03 || video.ended) {
    video.currentTime = state.start;
    video.play().catch(() => {});
  }
}

function setStatus(text, kind) {
  const el = qs("[data-role='status']");
  if (!el) return;
  el.className = `status${kind ? " " + kind : ""}${text ? "" : " hidden"}`;
  if (kind === "setup") {
    el.innerHTML = `${text} <button class="linkish" data-act="setup" type="button">Set up once</button>`;
  } else if (kind === "ok" && state.lastFolder) {
    el.innerHTML = `${text} <button class="linkish" data-act="reveal" type="button">Open folder</button>`;
  } else {
    el.textContent = text;
  }
}

function render() {
  if (!shadowRoot) return;
  const panel = document.getElementById(HOST_ID);
  if (panel) {
    if (state.open) panel.setAttribute("open", "");
    else panel.removeAttribute("open");
  }
  const launcher = launcherRoot?.querySelector(".launcher");
  launcher?.classList.toggle("on", state.open);
  launcher?.setAttribute("aria-pressed", state.open ? "true" : "false");
  const startBtn = qs("[data-act='start']");
  const endBtn = qs("[data-act='end']");
  const loopBtn = qs("[data-act='loop']");
  const saveBtn = qs("[data-act='save']");
  const dur = qs("[data-role='duration']");
  qs("[data-role='start-time']").textContent = formatTime(state.start);
  qs("[data-role='end-time']").textContent = formatTime(state.end);
  startBtn.classList.toggle("set", state.start != null);
  endBtn.classList.toggle("set", state.end != null);
  loopBtn.classList.toggle("on", state.looping);
  const len = duration();
  const ready = state.start != null && state.end != null && state.end > state.start;
  if (!ready) dur.textContent = "";
  else dur.textContent = `${len.toFixed(1)}s`;
  saveBtn.disabled = !ready || Boolean(state.jobId);
  saveBtn.classList.toggle("warn", Boolean(state.confirmLong));
  if (state.jobId) saveBtn.textContent = "Saving…";
  else if (state.confirmLong) saveBtn.textContent = `Save ${len.toFixed(1)}s anyway`;
  else saveBtn.textContent = "Make template";
  drawRange();
}

function drawRange() {
  document.getElementById(RANGE_ID)?.remove();
  document.getElementById(START_ID)?.remove();
  document.getElementById(END_ID)?.remove();
  if (!state.open) return;
  const bar = document.querySelector(".ytp-progress-bar");
  const video = getVideo();
  if (!bar || !video?.duration || !Number.isFinite(video.duration)) return;
  if (state.start == null && state.end == null) return;
  const startPct = ((state.start ?? 0) / video.duration) * 100;
  const endPct = ((state.end ?? state.start ?? 0) / video.duration) * 100;
  const range = document.createElement("div");
  range.id = RANGE_ID;
  range.style.cssText = `position:absolute;top:0;height:100%;left:${startPct}%;width:${Math.max(0, endPct - startPct)}%;background:rgba(124,58,237,.45);pointer-events:none;z-index:31;`;
  const mkHandle = (id, pct) => {
    const handle = document.createElement("div");
    handle.id = id;
    handle.style.cssText = `position:absolute;top:-3px;height:calc(100% + 6px);width:3px;left:${pct}%;background:#c4b5fd;pointer-events:none;z-index:32;border-radius:1px;`;
    return handle;
  };
  bar.append(range);
  if (state.start != null) bar.append(mkHandle(START_ID, startPct));
  if (state.end != null) bar.append(mkHandle(END_ID, endPct));
}

async function checkHelper() {
  const result = await helper("/health");
  const was = state.helperOk;
  state.helperOk = Boolean(result?.ok);
  if (!state.helperOk) {
    setStatus("The capture helper isn’t running.", "setup");
  } else if (was === false) {
    setStatus("Helper is ready. Mark a start and end.", "ok");
  } else if (!result.data?.ytdlp || !result.data?.ffmpeg) {
    setStatus("Helper is on, but yt-dlp or ffmpeg is missing.", "err");
  }
  return state.helperOk;
}

async function saveClip() {
  if (state.start == null || state.end == null || state.end <= state.start) {
    setStatus("Click Start, play to the last frame, then click End.", "err");
    return;
  }
  const len = duration();
  if (len > 30) {
    setStatus("Keep captures under 30 seconds.", "err");
    return;
  }
  if (len >= WARN_SECONDS && !state.confirmLong) {
    state.confirmLong = true;
    setStatus("That’s a long graphic. Click again if you still want it.", "");
    render();
    return;
  }
  const ok = await checkHelper();
  if (!ok) return;
  const payload = {
    url: `https://www.youtube.com/watch?v=${state.videoId}`,
    videoId: state.videoId,
    title: getTitle(),
    start: state.start,
    end: state.end,
    capturedAt: new Date().toISOString(),
  };
  const result = await helper("/capture", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!result?.ok) {
    const err = result?.data?.error || "Couldn’t start the capture.";
    if (result?.data?.error === "helper-down" || result?.status === 0) {
      setStatus("The capture helper isn’t running.", "setup");
      return;
    }
    setStatus(err, "err");
    return;
  }
  state.jobId = result.data.id;
  setStatus(result.data.progress || "Saving…", "busy");
  render();
  pollJob();
}

function pollJob() {
  clearInterval(state.pollTimer);
  state.pollTimer = setInterval(async () => {
    if (!state.jobId) return;
    const result = await helper(`/jobs/${state.jobId}`);
    if (!result?.ok) return;
    const job = result.data;
    setStatus(job.progress || "", job.status === "error" ? "err" : job.status === "done" ? "ok" : "busy");
    if (job.status === "done") {
      state.lastFolder = job.folder;
      state.jobId = null;
      clearInterval(state.pollTimer);
      setStatus(job.progress || "Saved to your template library.", "ok");
      chrome.runtime.sendMessage({ type: "notify-done", title: getTitle() });
      render();
    }
    if (job.status === "error") {
      state.jobId = null;
      clearInterval(state.pollTimer);
      render();
    }
  }, 800);
}

async function revealLast() {
  await helper("/reveal", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: state.lastFolder }),
  });
}

async function onWatchPage() {
  const videoId = getVideoId();
  if (!videoId) return;
  const changed = videoId !== state.videoId;
  state.videoId = videoId;
  mountUI();
  if (!shadowRoot) return;
  if (changed) await loadMarks(videoId);
  bindVideo();
  render();
  if (state.open) checkHelper();
}

function bindVideo() {
  const video = getVideo();
  if (!video || video.dataset.ytmcBound) return;
  video.dataset.ytmcBound = "1";
  video.addEventListener("timeupdate", onTimeUpdate);
  video.addEventListener("loadedmetadata", drawRange);
}

function teardown() {
  document.getElementById(TOGGLE_ID)?.remove();
  document.getElementById(HOST_ID)?.remove();
  document.getElementById(RANGE_ID)?.remove();
  document.getElementById(START_ID)?.remove();
  document.getElementById(END_ID)?.remove();
  shadowRoot = null;
  launcherRoot = null;
  state.looping = false;
  state.open = false;
  clearInterval(state.pollTimer);
}

function syncPage() {
  const url = location.href;
  if (url === lastUrl && document.getElementById(HOST_ID) && document.getElementById(TOGGLE_ID)) {
    if (isWatchPage()) bindVideo();
    return;
  }
  lastUrl = url;
  if (isWatchPage()) onWatchPage();
  else teardown();
}

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type !== "command") return;
  openPanel();
  if (message.command === "mark-start") setStart(currentTime());
  if (message.command === "mark-end") setEnd(currentTime());
  if (message.command === "toggle-loop") toggleLoop();
  if (message.command === "make-template") saveClip();
});

let redrawQueued = false;
const observer = new MutationObserver(() => {
  if (!isWatchPage()) return;
  if (!document.getElementById(HOST_ID) || !document.getElementById(TOGGLE_ID)) {
    onWatchPage();
    return;
  }
  if (redrawQueued) return;
  redrawQueued = true;
  requestAnimationFrame(() => {
    redrawQueued = false;
    drawRange();
  });
});
observer.observe(document.documentElement, { childList: true, subtree: true });
window.addEventListener("yt-navigate-finish", syncPage);
window.addEventListener("yt-page-data-updated", syncPage);
setInterval(syncPage, 1000);
syncPage();
