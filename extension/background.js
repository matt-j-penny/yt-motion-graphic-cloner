const HELPER = "http://127.0.0.1:47821";

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "forward") return;
  const path = message.path;
  const options = message.options || {};
  fetch(`${HELPER}${path}`, options)
    .then(async (response) => {
      const data = await response.json().catch(() => ({}));
      sendResponse({ ok: response.ok && data.ok !== false, status: response.status, data });
    })
    .catch(() => sendResponse({ ok: false, status: 0, data: { error: "helper-down" } }));
  return true;
});

chrome.commands.onCommand.addListener(async (command) => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !tab.url?.includes("youtube.com")) return;
  chrome.tabs.sendMessage(tab.id, { type: "command", command });
});

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "open-setup") {
    chrome.tabs.create({ url: chrome.runtime.getURL("setup.html") });
  }
  if (message?.type === "notify-done" && message.title) {
    chrome.notifications.create({
      type: "basic",
      iconUrl: "icons/icon128.png",
      title: "Clip saved",
      message: message.title,
    });
  }
});
